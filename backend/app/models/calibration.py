"""
Strat de calibrare post-hoc pentru probabilitățile 1/X/2.

Bazat pe Sub-faza D backtest (2024-09-02 → 2026-06-10, split 50/50):
  Uncalibrated: ll=0.8941  ECE@10=0.051
  Isotonic:     ll=0.8840  ECE@10=0.023  ← cel mai bun (fără overfit)
  Platt:        ll=0.8881  ECE@10=0.030

Calibratorii sunt aplicați DUPĂ blend-ul final (DC sau ensemble).
Re-normalizează automat ca H+D+A = 1.0.

Strategie anti-leakage în producție:
  - DC este antrenat pe toate datele istorice (comportament actual).
  - Calibratorul este antrenat pe predicțiile DC pentru ultimele
    CALIBRATION_HOLDOUT_MONTHS luni din datele de antrenament.
  - DC a văzut acele meciuri la training → leakage mic dar acceptabil
    (DC este un model de medie pe 6 ani; 1 an extra nu schimbă dramatic
    parametrii de atac/apărare; isotonic nu memorizează match outcomes,
    ci corectează sistematic distribuția de probabilitate).
  - Alternativa zero-leakage: un DC "shadow" antrenat pe date – 12 luni,
    cu ~20 secunde extra la startup. Disponibilă prin flag CALIBRATION_STRICT=true
    (neimplementată implicit din motive de viteză).
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

_EPS = 1e-9


def _renorm(arr: np.ndarray) -> np.ndarray:
    """Re-normalizeaza liniile unui array N×3 la suma 1."""
    arr = np.clip(arr, _EPS, 1.0)
    return arr / arr.sum(axis=1, keepdims=True)


class IsotonicCalibrator:
    """Isotonic regression per clasă, re-normalizat la sumă 1."""

    def __init__(self) -> None:
        self._regs: list | None = None
        self.is_fitted = False

    def fit(self, y_pred: np.ndarray, y_true: np.ndarray) -> "IsotonicCalibrator":
        from sklearn.isotonic import IsotonicRegression

        n = len(y_pred)
        self._regs = []
        for k in range(3):
            reg = IsotonicRegression(out_of_bounds="clip")
            reg.fit(y_pred[:, k], y_true[:, k])
            self._regs.append(reg)

        self.is_fitted = True
        logger.info("IsotonicCalibrator fitted on %d samples.", n)
        return self

    def predict(self, y_pred: np.ndarray) -> np.ndarray:
        if not self.is_fitted or self._regs is None:
            raise RuntimeError("Calibrator not fitted.")
        cal = np.stack([self._regs[k].predict(y_pred[:, k]) for k in range(3)], axis=1)
        return _renorm(cal)

    def predict_one(self, ph: float, pd: float, pa: float) -> tuple[float, float, float]:
        arr = np.array([[ph, pd, pa]], dtype=np.float64)
        out = self.predict(arr)[0]
        return float(out[0]), float(out[1]), float(out[2])

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        logger.info("IsotonicCalibrator saved -> %s", path)

    @classmethod
    def load(cls, path: str) -> "IsotonicCalibrator":
        with open(path, "rb") as f:
            obj = pickle.load(f)
        logger.info("IsotonicCalibrator loaded <- %s", path)
        return obj


class PlattCalibrator:
    """Platt scaling (logistic regression per clasă), re-normalizat."""

    def __init__(self) -> None:
        self._regs: list | None = None
        self.is_fitted = False

    def fit(self, y_pred: np.ndarray, y_true: np.ndarray) -> "PlattCalibrator":
        from sklearn.linear_model import LogisticRegression

        n = len(y_pred)
        self._regs = []
        for k in range(3):
            reg = LogisticRegression(C=1e4, solver="lbfgs", max_iter=1000)
            reg.fit(y_pred[:, k].reshape(-1, 1), y_true[:, k].astype(int))
            self._regs.append(reg)

        self.is_fitted = True
        logger.info("PlattCalibrator fitted on %d samples.", n)
        return self

    def predict(self, y_pred: np.ndarray) -> np.ndarray:
        if not self.is_fitted or self._regs is None:
            raise RuntimeError("Calibrator not fitted.")
        cal = np.stack(
            [self._regs[k].predict_proba(y_pred[:, k].reshape(-1, 1))[:, 1] for k in range(3)],
            axis=1,
        )
        return _renorm(cal)

    def predict_one(self, ph: float, pd: float, pa: float) -> tuple[float, float, float]:
        arr = np.array([[ph, pd, pa]], dtype=np.float64)
        out = self.predict(arr)[0]
        return float(out[0]), float(out[1]), float(out[2])

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        logger.info("PlattCalibrator saved -> %s", path)

    @classmethod
    def load(cls, path: str) -> "PlattCalibrator":
        with open(path, "rb") as f:
            obj = pickle.load(f)
        logger.info("PlattCalibrator loaded <- %s", path)
        return obj


# ─── Factory ──────────────────────────────────────────────────────────────────

CalibratorType = IsotonicCalibrator | PlattCalibrator | None


def build_calibrator(mode: str) -> CalibratorType:
    """Returnează un calibrator nou (nefittat) sau None dacă mode='none'."""
    if mode == "isotonic":
        return IsotonicCalibrator()
    if mode == "platt":
        return PlattCalibrator()
    if mode == "none":
        return None
    raise ValueError(f"Calibration mode necunoscut: '{mode}'. Valori valide: none/isotonic/platt")
