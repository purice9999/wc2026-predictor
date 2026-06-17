"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    cors_allow_all: bool = True

    # Cache paths (relative to backend/)
    cache_dir: str = ".cache"
    data_cache_path: str = ".cache/results.csv"
    dc_model_cache_path: str = ".cache/dc_model.pkl"
    elo_model_cache_path: str = ".cache/elo_model.pkl"
    xgb_model_cache_path: str = ".cache/xgb_model.pkl"
    predictions_log_path: str = ".cache/predictions_log.jsonl"
    results_path: str = ".cache/match_results.json"

    # Model training
    retrain: bool = False           # set RETRAIN=true in .env to force retrain
    n_simulations: int = 10_000
    training_years: int = 4

    # Sub-faza B: semnal hibrid xG + goluri in Dixon-Coles
    # OFF by default — DC pur (baseline backtest: ll=0.9282, acc=58.4%)
    # ON: pentru meciurile cu xG, tinta DC = xg_blend_weight*xG + (1-xg_blend_weight)*goals
    use_xg_hybrid:   bool  = False
    xg_blend_weight: float = 0.7   # proportia xG; 0.3 = goluri

    # Ensemble blend weights (must be non-negative; auto-normalised to sum=1)
    # Backtest 2024-07-15→2026-06-10 (1 459 competitive matches):
    #   dc_only (1/0/0):   ll=0.9282  acc=58.4%  ← best
    #   50/30/20:           ll=0.9336  acc=57.8%
    #   40/25/35:           ll=0.9356  acc=56.8%
    #   30/20/50 (old):     ll=0.9474  acc=55.4%  ← was default, now disabled
    # To switch variant: set W_DC / W_ELO / W_XGB in .env or environment
    w_dc:  float = 1.0   # Dixon-Coles weight
    w_elo: float = 0.0   # Elo weight
    w_xgb: float = 0.0   # XGBoost weight

    # Sub-faza D: calibrare post-hoc (isotonic / platt / none)
    # Backtest validation: isotonic imbunatateste ll 0.8941->0.8840, ECE 0.051->0.023
    calibration: str = "isotonic"
    calibration_holdout_months: int = 12
    calibrator_cache_path: str = ".cache/calibrator.pkl"

    # Live tracking
    frozen_predictions_path: str = ".cache/frozen_predictions.json"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
