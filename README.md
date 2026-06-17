# WC 2026 Predictor — Full-Stack App

Probabilistic predictions for the 2026 FIFA World Cup.
**Educational statistics project — not a betting tool.**

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + uvicorn (Python) |
| Model | Dixon-Coles bivariate Poisson + Isotonic calibration |
| Frontend | React + Vite + TypeScript + Tailwind CSS |
| Charts | Recharts |
| Animations | Framer Motion |
| Data fetching | TanStack Query (React Query) |

## Running locally

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python run.py
# → http://localhost:8000
# → http://localhost:8000/docs (Swagger UI)
```

First startup downloads ~3 MB of historical data and trains the model (~1–2 min).
Subsequent startups load from `cache/` (instant).

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### Both simultaneously (root level)

```bash
# From project root (requires Node + npm):
npm install        # installs concurrently
npm run dev        # starts both backend and frontend
```

## Project structure

```
wc2026-predictor/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app + CORS
│   │   ├── config.py          Settings via pydantic-settings
│   │   ├── data/              tournament_config.py + fixtures.py
│   │   ├── models/            Dixon-Coles, Elo, simulation, calibration
│   │   ├── routers/           matches, predict, slip, tournament, history
│   │   ├── schemas/           Pydantic response models
│   │   └── services/          Business logic layer
│   ├── .cache/                Generated at runtime: model pickles, calibrator, results
│   └── requirements.txt
└── frontend/
    └── src/
        ├── api/               Typed API client
        ├── components/        UI components (layout, home, analysis, slip, tournament)
        ├── hooks/             TanStack Query hooks
        ├── pages/             React Router pages
        └── types/             TypeScript interfaces
```

## Deploy

- **Backend:** Render / Railway (set `WEB_CONCURRENCY=1`, mount `cache/` as persistent disk)
- **Frontend:** Vercel / Netlify (set `VITE_API_URL` env var to backend URL)
