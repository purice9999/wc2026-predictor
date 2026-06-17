"""Download, clean, and cache the martj42 international football results dataset."""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from app.data.tournament_config import (
    COMPETITION_WEIGHTS,
    DATA_URL,
    DEFAULT_COMPETITION_WEIGHT,
    TEAM_NAME_MAPPING,
    TIME_DECAY_RATE,
    TRAINING_YEARS,
)

logger = logging.getLogger(__name__)


def download_results(cache_path: str, force: bool = False) -> pd.DataFrame:
    cache = Path(cache_path)
    cache.parent.mkdir(parents=True, exist_ok=True)

    if not force and cache.exists():
        age_hours = (datetime.now().timestamp() - cache.stat().st_mtime) / 3600
        if age_hours < 24:
            logger.info("Loading results from cache (%.1f h old).", age_hours)
            return pd.read_csv(cache, low_memory=False)

    logger.info("Downloading results from GitHub…")
    try:
        r = requests.get(DATA_URL, timeout=30)
        r.raise_for_status()
        cache.write_bytes(r.content)
        logger.info("Saved %d bytes to %s.", len(r.content), cache)
    except requests.RequestException as exc:
        if cache.exists():
            logger.warning("Download failed (%s); using stale cache.", exc)
        else:
            raise RuntimeError(f"Cannot download data and no cache exists: {exc}") from exc

    return pd.read_csv(cache, low_memory=False)


def _competition_weight(tournament: str) -> float:
    for key, w in COMPETITION_WEIGHTS.items():
        if key.lower() in tournament.lower():
            return w
    return DEFAULT_COMPETITION_WEIGHT


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["date_dt"] = df["date"].dt.date

    today = date.today()
    cutoff = today - timedelta(days=TRAINING_YEARS * 365)
    df = df[(df["date_dt"] >= cutoff) & (df["date_dt"] <= today)]

    df["home_score"] = pd.to_numeric(df["home_score"], errors="coerce")
    df["away_score"] = pd.to_numeric(df["away_score"], errors="coerce")
    df = df.dropna(subset=["home_score", "away_score"])
    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)

    df["home_team"] = df["home_team"].map(lambda n: TEAM_NAME_MAPPING.get(n, n))
    df["away_team"] = df["away_team"].map(lambda n: TEAM_NAME_MAPPING.get(n, n))
    df = df.dropna(subset=["home_team", "away_team"])

    df["neutral"] = df["neutral"].astype(bool).astype(float)

    df["w_time"] = df["date_dt"].apply(
        lambda d: math.exp(-TIME_DECAY_RATE * max((today - d).days, 0))
    )
    df["w_comp"] = df["tournament"].apply(_competition_weight)
    df["weight"] = df["w_time"] * df["w_comp"]
    df["weight"] = df["weight"] / df["weight"].mean()

    return df.reset_index(drop=True)


def get_training_data(cache_path: str) -> pd.DataFrame:
    raw = download_results(cache_path)
    return preprocess_data(raw)
