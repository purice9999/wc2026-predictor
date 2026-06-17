"""Bidirectional team name mapping: dataset names ↔ WC 2026 canonical names."""

from __future__ import annotations

from app.data.tournament_config import TEAM_NAME_MAPPING as _BASE

# dataset name → WC canonical name  (e.g. "South Korea" → "Korea Republic")
DATASET_TO_WC: dict[str, str] = {k: v for k, v in _BASE.items() if k != v}

# WC canonical name → dataset name  (e.g. "Korea Republic" → "South Korea")
WC_TO_DATASET: dict[str, str] = {v: k for k, v in DATASET_TO_WC.items()}


def to_dataset_name(wc_name: str) -> str:
    """Return the name used in the martj42 dataset for a WC canonical team name."""
    return WC_TO_DATASET.get(wc_name, wc_name)


def to_wc_name(dataset_name: str) -> str:
    """Return the WC canonical name for a dataset team name."""
    return DATASET_TO_WC.get(dataset_name, dataset_name)
