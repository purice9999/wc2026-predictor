"""WC 2026 Predictor — FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.data.fixtures import FIXTURES_BY_ID
from app.data.results_fetcher import get_real_results, match_real_to_fixture
from app.routers import admin as admin_router
from app.routers import matches
from app.routers import predict as predict_router
from app.routers import results as results_router
from app.routers import tracking as tracking_router
from app.services.frozen_predictions import FrozenPredictionService
from app.services.model_service import build_ensemble, load_or_train, load_or_train_calibrator
from app.services.result_service import ResultService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent.parent / "static"

APP_VERSION = "0.5.0"


def _freeze_all_known(fps, ensemble) -> None:
    """Idempotent: skip already-frozen, wrap each predict in try/except."""
    frozen_new = skipped = errors = 0
    for fid, fx in FIXTURES_BY_ID.items():
        if fx.get("home_team") == "TBD" or fx.get("away_team") == "TBD":
            continue
        if fps.has(fid):
            skipped += 1
            continue
        try:
            pred = ensemble.predict(fx["home_team"], fx["away_team"], neutral=True)
            if fps.freeze(fid, fx, pred):
                frozen_new += 1
        except Exception as exc:
            logger.debug("Freeze skip %s: %s", fid, exc)
            errors += 1
    logger.info("Freeze: %d noi, %d existente, %d erori.", frozen_new, skipped, errors)


async def _background_init(app: FastAPI) -> None:
    """Load model and supporting data in background — server responds to HTTP immediately."""
    loop = asyncio.get_running_loop()
    try:
        logger.info("WC 2026 Predictor — background init starting…")

        dc, elo, xgb = await loop.run_in_executor(None, load_or_train, settings)
        calibrator = await loop.run_in_executor(None, load_or_train_calibrator, dc, settings)

        app.state.dc_model = dc
        app.state.elo_model = elo
        app.state.xgb_model = xgb
        app.state.calibrator = calibrator
        app.state.ensemble = build_ensemble(
            dc, elo,
            w_dc=settings.w_dc, w_elo=settings.w_elo, w_xgb=settings.w_xgb,
            xgb=xgb,
            calibrator=calibrator,
        )
        app.state.prediction_cache = {}
        app.state.result_service = ResultService(settings.results_path)

        try:
            fps = FrozenPredictionService(settings.frozen_predictions_path)
            app.state.frozen_predictions = fps
            await loop.run_in_executor(None, _freeze_all_known, fps, app.state.ensemble)
        except Exception as exc:
            logger.warning("FrozenPredictions init failed (%s); tracking dezactivat.", exc)
            fps = FrozenPredictionService.__new__(FrozenPredictionService)
            fps._data = {}
            fps._path = Path(settings.frozen_predictions_path)
            fps._lock = threading.Lock()
            app.state.frozen_predictions = fps

        try:
            real_matches = await loop.run_in_executor(None, get_real_results, False)
            app.state.real_results = match_real_to_fixture(real_matches, FIXTURES_BY_ID)
            logger.info(
                "Tracking: %d înghețate, %d rezultate reale.",
                app.state.frozen_predictions.count(), len(app.state.real_results),
            )
        except Exception as exc:
            logger.warning("Real results fetch failed (%s).", exc)
            app.state.real_results = {}

        app.state.ready = True
        logger.info("Background init complete: %s", app.state.ensemble.model_label)

    except Exception as exc:
        logger.error("Background init FAILED: %s", exc, exc_info=True)
        app.state.ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-set safe defaults so state attrs always exist
    app.state.ready = False
    app.state.ensemble = None
    app.state.result_service = None
    app.state.prediction_cache = {}
    app.state.real_results = {}
    # Minimal frozen predictions stub so /tracking doesn't crash during init
    fps_stub = FrozenPredictionService.__new__(FrozenPredictionService)
    fps_stub._data = {}
    fps_stub._path = Path(settings.frozen_predictions_path)
    fps_stub._lock = threading.Lock()
    app.state.frozen_predictions = fps_stub

    # Kick off model loading in background — lifespan yields immediately
    asyncio.create_task(_background_init(app))

    yield
    logger.info("Backend shutting down.")


app = FastAPI(
    title="WC 2026 Predictor API",
    description=(
        "REST API for FIFA World Cup 2026 probabilistic match predictions. "
        "Educational statistics project — not a betting tool."
    ),
    version=f"{APP_VERSION}-dc-isotonic",
    lifespan=lifespan,
)

# Gate: return 503 for all non-meta endpoints while model is loading
_ALWAYS_OPEN = {"/health", "/docs", "/openapi.json", "/redoc", "/admin"}
_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Retry-After": "30",
}

@app.middleware("http")
async def startup_gate(request: Request, call_next):
    if not getattr(request.app.state, "ready", False):
        path = request.url.path
        if not any(path == p or path.startswith("/static") for p in _ALWAYS_OPEN):
            return JSONResponse(
                status_code=503,
                content={"status": "loading", "message": "Model initializing — retry in 30s"},
                headers=_CORS_HEADERS,
            )
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_allow_all else settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

app.include_router(matches.router)
app.include_router(predict_router.router)
app.include_router(results_router.router)
app.include_router(admin_router.router)
app.include_router(tracking_router.router)


@app.get("/admin", include_in_schema=False)
def admin_page() -> FileResponse:
    return FileResponse(str(_STATIC_DIR / "admin.html"))


@app.get("/health", tags=["health"])
def health() -> dict:
    ready = getattr(app.state, "ready", False)
    ensemble = getattr(app.state, "ensemble", None)
    return {
        "status": "ok" if ready else "loading",
        "version": APP_VERSION,
        "model": ensemble.model_label if ensemble else "initializing",
    }
