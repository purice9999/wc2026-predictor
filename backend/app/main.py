"""WC 2026 Predictor — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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

# Versiunea aplicației — sursă unică
APP_VERSION = "0.5.0"


def _freeze_all_known(fps, ensemble) -> None:
    """Îngheață predicțiile pentru toate meciurile cu echipe cunoscute (non-TBD).
    Operație idempotentă: nu suprascrie predicții deja salvate.
    """
    frozen_new = 0
    skipped = 0
    errors = 0
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
    logger.info(
        "Freeze predicții: %d noi, %d existente, %d erori.",
        frozen_new, skipped, errors,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("WC 2026 Predictor backend starting up…")
    dc, elo, xgb = load_or_train(settings)
    calibrator = load_or_train_calibrator(dc, settings)
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
    app.state.prediction_cache: dict = {}
    app.state.result_service = ResultService(settings.results_path)

    # Live tracking: predicții înghețate + rezultate reale
    # Eșuează elegant — nu blochează pornirea serverului
    try:
        fps = FrozenPredictionService(settings.frozen_predictions_path)
        app.state.frozen_predictions = fps
        _freeze_all_known(fps, app.state.ensemble)
    except Exception as exc:
        logger.warning("FrozenPredictions init failed (%s); tracking dezactivat.", exc)
        from app.services.frozen_predictions import FrozenPredictionService as _FPS
        app.state.frozen_predictions = _FPS.__new__(_FPS)
        app.state.frozen_predictions._data = {}
        app.state.frozen_predictions._path = Path(settings.frozen_predictions_path)
        import threading
        app.state.frozen_predictions._lock = threading.Lock()

    try:
        real_matches = get_real_results(force=False)
        app.state.real_results = match_real_to_fixture(real_matches, FIXTURES_BY_ID)
        logger.info(
            "Tracking: %d înghețate, %d rezultate reale.",
            app.state.frozen_predictions.count(), len(app.state.real_results),
        )
    except Exception as exc:
        logger.warning("Real results fetch failed (%s); tracking va returna date goale.", exc)
        app.state.real_results = {}

    logger.info("Ensemble ready: %s", app.state.ensemble.model_label)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_allow_all else settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (admin page assets)
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

app.include_router(matches.router)
app.include_router(predict_router.router)
app.include_router(results_router.router)
app.include_router(admin_router.router)
app.include_router(tracking_router.router)


@app.get("/admin", include_in_schema=False)
def admin_page() -> FileResponse:
    """Serve the match results admin page."""
    return FileResponse(str(_STATIC_DIR / "admin.html"))


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "version": APP_VERSION, "model": "DC+Isotonic"}
