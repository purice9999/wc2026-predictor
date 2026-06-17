"""
Sub-faza D: Calibrare cu gardă anti-overfit.

Model calibrat: DC hibrid xG blend=0.70 (cel mai bun din Sub-faza B).

Metodologie anti-overfit:
  - Test set (1.459 meciuri, 2024-09-02 → 2026-06-10) împărțit TEMPORAL în:
      calibration set  = prima jumătate cronologică (fit calibrators)
      validation set   = a doua jumătate cronologică (măsurare exclusivă)
  - Calibratorii NU văd niciodată validation set la fit.
  - Dacă îmbunătățirile pe ECE apar doar pe calibration set → overfit, CALIBRATION=none.

Calibratori testați:
  1. Nicio calibrare (uncalibrated)
  2. Isotonic regression (per clasă, re-normalizat)
  3. Platt scaling (logistic regression per clasă, re-normalizat)

Metrici: accuracy, log-loss, Brier, ECE@10, ECE@15.

Utilizare:
  cd backend && python scripts/backtest_subfaza_d.py
"""

from __future__ import annotations

import logging
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.data.historical import download_results, preprocess_data
from app.data.xg_fetcher import fetch_all_xg
from app.data.xg_hybrid import apply_xg_hybrid
from app.models.dixon_coles import DixonColesModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

CUTOFF   = date(2024, 7, 15)
TEST_END = date(2026, 6, 10)
MIN_COMP = 1.5
XG_BLEND = 0.70


# ─── Metrici ──────────────────────────────────────────────────────────────────

def log_loss_mc(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-9) -> float:
    y_pred = np.clip(y_pred, eps, 1 - eps)
    return float(-np.mean(np.sum(y_true * np.log(y_pred), axis=1)))


def brier(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.sum((y_pred - y_true) ** 2, axis=1)))


def accuracy_1x2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.argmax(y_pred, axis=1) == np.argmax(y_true, axis=1)))


def ece_score(y_true: np.ndarray, y_pred: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error — flat pe toate cele 3 clase."""
    flat_t = y_true.ravel()
    flat_p = y_pred.ravel()
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (flat_p >= lo) & (flat_p < hi)
        if not mask.any():
            continue
        total += mask.mean() * abs(float(flat_t[mask].mean()) - float(flat_p[mask].mean()))
    return float(total)


def compute_all(y_true: np.ndarray, y_pred: np.ndarray, label: str) -> dict:
    return {
        "label":    label,
        "n":        len(y_true),
        "accuracy": round(accuracy_1x2(y_true, y_pred), 4),
        "log_loss": round(log_loss_mc(y_true, y_pred), 4),
        "brier":    round(brier(y_true, y_pred), 4),
        "ece_10":   round(ece_score(y_true, y_pred, n_bins=10), 4),
        "ece_15":   round(ece_score(y_true, y_pred, n_bins=15), 4),
    }


# ─── Calibratori ──────────────────────────────────────────────────────────────

class IsotonicCalibrator:
    """Isotonic regression per clasă, cu re-normalizare."""

    def __init__(self):
        from sklearn.isotonic import IsotonicRegression
        self.regs = [IsotonicRegression(out_of_bounds="clip") for _ in range(3)]

    def fit(self, y_pred: np.ndarray, y_true: np.ndarray) -> "IsotonicCalibrator":
        for k in range(3):
            self.regs[k].fit(y_pred[:, k], y_true[:, k])
        return self

    def predict(self, y_pred: np.ndarray) -> np.ndarray:
        cal = np.stack([self.regs[k].predict(y_pred[:, k]) for k in range(3)], axis=1)
        cal = np.clip(cal, 1e-9, 1.0)
        return cal / cal.sum(axis=1, keepdims=True)


class PlattCalibrator:
    """Platt scaling per clasă (logistic regression pe probabilitati brute), re-normalizat."""

    def __init__(self):
        from sklearn.linear_model import LogisticRegression
        # C mare = minima regularizare (Platt classic)
        self.regs = [LogisticRegression(C=1e4, solver="lbfgs", max_iter=1000) for _ in range(3)]

    def fit(self, y_pred: np.ndarray, y_true: np.ndarray) -> "PlattCalibrator":
        for k in range(3):
            # Antrenare: probabilitatile brute ca feature, tinta binara one-vs-rest
            self.regs[k].fit(y_pred[:, k].reshape(-1, 1), y_true[:, k].astype(int))
        return self

    def predict(self, y_pred: np.ndarray) -> np.ndarray:
        cal = np.stack(
            [self.regs[k].predict_proba(y_pred[:, k].reshape(-1, 1))[:, 1] for k in range(3)],
            axis=1,
        )
        cal = np.clip(cal, 1e-9, 1.0)
        return cal / cal.sum(axis=1, keepdims=True)


# ─── Predictii DC ─────────────────────────────────────────────────────────────

def predict_dc_batch(df: pd.DataFrame, dc: DixonColesModel) -> tuple[np.ndarray, np.ndarray]:
    y_true_rows, y_pred_rows = [], []
    for row in df.itertuples(index=False):
        hs, as_ = int(row.home_score), int(row.away_score)
        cls = 0 if hs > as_ else (1 if hs == as_ else 2)
        y_true_rows.append([int(cls == i) for i in range(3)])
        try:
            r = dc.predict_match_full(row.home_team, row.away_team, bool(row.neutral))
            y_pred_rows.append([r["prob_home"], r["prob_draw"], r["prob_away"]])
        except Exception:
            y_pred_rows.append([1 / 3, 1 / 3, 1 / 3])
    return np.array(y_true_rows, float), np.array(y_pred_rows, float)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 65)
    logger.info("SUB-FAZA D — Calibrare cu gardă anti-overfit")
    logger.info("  Model: DC hibrid xG blend=%.2f", XG_BLEND)
    logger.info("  Split calibrare: test set împărțit temporal 50/50")
    logger.info("=" * 65)

    # 1 — Date
    raw   = download_results(settings.data_cache_path, force=False)
    df_all = preprocess_data(raw)
    df_train = df_all[df_all["date_dt"] < CUTOFF].copy()
    df_test  = df_all[
        (df_all["date_dt"] >= CUTOFF) &
        (df_all["date_dt"] <= TEST_END) &
        (df_all["w_comp"]  >= MIN_COMP)
    ].sort_values("date_dt").reset_index(drop=True)

    logger.info("Train: %d  |  Test total: %d", len(df_train), len(df_test))

    # 2 — xG
    xg_df    = fetch_all_xg(cache_dir=".cache/xg", force=False)
    df_train = apply_xg_hybrid(df_train, xg_df, blend_weight=XG_BLEND)

    # 3 — Antrenare DC hibrid pe train split
    logger.info("Antrenare DC hibrid blend=%.2f pe train split…", XG_BLEND)
    dc = DixonColesModel()
    dc.fit(df_train)

    # 4 — Predictii pe test set complet (sortat cronologic)
    logger.info("Generez predictii pe %d meciuri de test…", len(df_test))
    y_true_all, y_pred_all = predict_dc_batch(df_test, dc)

    # 5 — Split TEMPORAL al test set-ului (50/50 dupa count)
    n_total = len(df_test)
    n_cal   = n_total // 2
    n_val   = n_total - n_cal

    y_true_cal  = y_true_all[:n_cal]
    y_pred_cal  = y_pred_all[:n_cal]
    y_true_val  = y_true_all[n_cal:]
    y_pred_val  = y_pred_all[n_cal:]

    date_cal_start = str(df_test.iloc[0]["date_dt"])
    date_cal_end   = str(df_test.iloc[n_cal - 1]["date_dt"])
    date_val_start = str(df_test.iloc[n_cal]["date_dt"])
    date_val_end   = str(df_test.iloc[-1]["date_dt"])

    logger.info(
        "Calibration set: %d meciuri (%s → %s)",
        n_cal, date_cal_start, date_cal_end,
    )
    logger.info(
        "Validation set:  %d meciuri (%s → %s)",
        n_val, date_val_start, date_val_end,
    )

    # 6 — Antrenare calibratori pe calibration set
    logger.info("Antrenez Isotonic Regression pe calibration set…")
    iso = IsotonicCalibrator()
    iso.fit(y_pred_cal, y_true_cal)

    logger.info("Antrenez Platt Scaling pe calibration set…")
    platt = PlattCalibrator()
    platt.fit(y_pred_cal, y_true_cal)

    # 7 — Aplicare pe validation set
    y_pred_val_iso   = iso.predict(y_pred_val)
    y_pred_val_platt = platt.predict(y_pred_val)

    # 8 — Metrici pe CALIBRATION SET (sa vedem cat "invata")
    logger.info("Calculez metrici pe calibration set…")
    cal_uncal = compute_all(y_true_cal,  y_pred_cal,                      "Uncalibrated [CAL]")
    cal_iso   = compute_all(y_true_cal,  iso.predict(y_pred_cal),         "Isotonic     [CAL]")
    cal_platt = compute_all(y_true_cal,  platt.predict(y_pred_cal),       "Platt        [CAL]")

    # 9 — Metrici pe VALIDATION SET (testul real)
    logger.info("Calculez metrici pe validation set…")
    val_uncal = compute_all(y_true_val,  y_pred_val,                      "Uncalibrated [VAL]")
    val_iso   = compute_all(y_true_val,  y_pred_val_iso,                  "Isotonic     [VAL]")
    val_platt = compute_all(y_true_val,  y_pred_val_platt,                "Platt        [VAL]")

    all_results = [cal_uncal, cal_iso, cal_platt, val_uncal, val_iso, val_platt]

    # 10 — Log si print
    logger.info("=" * 65)
    for r in all_results:
        logger.info(
            "%-25s  ll=%.4f  brier=%.4f  ece10=%.4f  ece15=%.4f",
            r["label"], r["log_loss"], r["brier"], r["ece_10"], r["ece_15"],
        )

    # ─── Verdicts ────────────────────────────────────────────────────────────
    delta_iso_ll   = val_iso["log_loss"]   - val_uncal["log_loss"]
    delta_platt_ll = val_platt["log_loss"] - val_uncal["log_loss"]
    delta_iso_ece  = val_iso["ece_10"]     - val_uncal["ece_10"]
    delta_platt_ece= val_platt["ece_10"]   - val_uncal["ece_10"]

    # Overfit check: am imbunatatit pe CAL dar nu pe VAL?
    iso_overfit   = cal_iso["ece_10"]   < cal_uncal["ece_10"] and val_iso["ece_10"]   >= val_uncal["ece_10"]
    platt_overfit = cal_platt["ece_10"] < cal_uncal["ece_10"] and val_platt["ece_10"] >= val_uncal["ece_10"]

    return {
        "results": all_results,
        "splits": {
            "n_cal": n_cal,
            "n_val": n_val,
            "cal_dates": f"{date_cal_start} → {date_cal_end}",
            "val_dates": f"{date_val_start} → {date_val_end}",
        },
        "deltas": {
            "iso_ll": delta_iso_ll, "iso_ece": delta_iso_ece,
            "platt_ll": delta_platt_ll, "platt_ece": delta_platt_ece,
        },
        "overfit": {"iso": iso_overfit, "platt": platt_overfit},
        "cal_results": [cal_uncal, cal_iso, cal_platt],
        "val_results": [val_uncal, val_iso, val_platt],
    }


# ─── Markdown ─────────────────────────────────────────────────────────────────

def build_markdown_section(data: dict) -> str:
    sp  = data["splits"]
    dl  = data["deltas"]
    ov  = data["overfit"]
    val = data["val_results"]
    cal = data["cal_results"]

    rows_val = "\n".join(
        f"| {r['label']} | {r['accuracy']:.1%} | **{r['log_loss']:.4f}** "
        f"| {r['brier']:.4f} | {r['ece_10']:.4f} | {r['ece_15']:.4f} |"
        for r in val
    )
    rows_cal = "\n".join(
        f"| {r['label']} | {r['log_loss']:.4f} | {r['ece_10']:.4f} | {r['ece_15']:.4f} |"
        for r in cal
    )

    # Verdicts
    def verdict_ece(delta, overfit_flag):
        if overfit_flag:
            return "**OVERFIT** — imbunatatire pe cal, regres pe val."
        if delta < -0.001:
            return f"IMBUNATATIRE pe val: delta ECE@10={delta:+.4f}"
        if delta > 0.001:
            return f"INRAUTATIRE pe val: delta ECE@10={delta:+.4f}"
        return f"Neglijabila (delta={delta:+.4f})"

    def verdict_ll(delta):
        if delta < -0.001:
            return f"IMBUNATATIRE: delta ll={delta:+.4f}"
        if delta > 0.001:
            return f"INRAUTATIRE: delta ll={delta:+.4f}"
        return f"Neglijabila (delta={delta:+.4f})"

    iso_ece_v   = verdict_ece(dl["iso_ece"],   ov["iso"])
    platt_ece_v = verdict_ece(dl["platt_ece"], ov["platt"])
    iso_ll_v    = verdict_ll(dl["iso_ll"])
    platt_ll_v  = verdict_ll(dl["platt_ll"])

    # Recomandare finala
    val_uncal = val[0]
    val_iso   = val[1]
    val_platt = val[2]
    best_ll   = min(r["log_loss"] for r in val)
    best_method = "none (uncalibrated)"
    if val_iso["log_loss"] == best_ll and val_iso["log_loss"] < val_uncal["log_loss"] - 0.001:
        best_method = "isotonic"
    elif val_platt["log_loss"] == best_ll and val_platt["log_loss"] < val_uncal["log_loss"] - 0.001:
        best_method = "platt"

    if best_method == "none (uncalibrated)":
        rec = (
            "**Recomandare: `CALIBRATION=none` (default).**  \n"
            "Calibrarea nu generalizează pe validation set — diferențele sunt sub pragul de 0.001.  \n"
            "Lăsați modelul necalibrat."
        )
    else:
        rec = (
            f"**Recomandare: `CALIBRATION={best_method}`**  \n"
            f"Îmbunătățire reală pe validation set (ll={val[1 if best_method=='isotonic' else 2]['log_loss']:.4f}).  \n"
            f"Setați `CALIBRATION={best_method}` în `.env`."
        )

    return f"""

---

## Sub-faza D — Calibrare (gardă anti-overfit)

### Configurare

| Parametru | Valoare |
|-----------|---------|
| Model calibrat | DC hibrid xG blend={XG_BLEND} (cel mai bun din Sub-faza B) |
| Calibration set | {sp['n_cal']} meciuri ({sp['cal_dates']}) |
| Validation set | {sp['n_val']} meciuri ({sp['val_dates']}) |
| Split | temporal 50/50, calibratorii NU văd validation set la fit |

### Calibration set — ce "învaț" calibratorii (overfit check)

| Varianta | Log-Loss | ECE@10 | ECE@15 |
|----------|----------|--------|--------|
{rows_cal}

### Validation set — testul real (date nevăzute)

| Varianta | Accuracy | Log-Loss | Brier | ECE@10 | ECE@15 |
|----------|----------|----------|-------|--------|--------|
{rows_val}

### Analiză

**Isotonic Regression:**
- ECE@10 pe validation: {iso_ece_v}
- Log-Loss pe validation: {iso_ll_v}
- Overfit? {'DA' if ov['iso'] else 'NU'}

**Platt Scaling:**
- ECE@10 pe validation: {platt_ece_v}
- Log-Loss pe validation: {platt_ll_v}
- Overfit? {'DA' if ov['platt'] else 'NU'}

**Stabilitate ECE** (10 vs 15 bins): Dacă concluzia diferă între ECE@10 și ECE@15, \
rezultatul e sensibil la granularitate — nu te baza pe ECE singur.

### Verdict

{rec}

*Generat: {date.today()} | Model: DC hibrid xG blend={XG_BLEND}*"""


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    data = main()

    # Print tabel final
    print()
    print("=" * 75)
    sp = data["splits"]
    cal_dates_safe = sp['cal_dates'].replace('→', '->')
    val_dates_safe = sp['val_dates'].replace('→', '->')
    print(f"  Sub-faza D | cal={sp['n_cal']} ({cal_dates_safe}) | val={sp['n_val']} ({val_dates_safe})")
    print("=" * 75)
    print(f"  {'Varianta':<27} {'Acc':>5} {'LogLoss':>8} {'Brier':>7} {'ECE@10':>7} {'ECE@15':>7}")
    print("-" * 75)
    print("  --- CALIBRATION SET (antrenare calibratori) ---")
    for r in data["cal_results"]:
        print(f"  {r['label']:<27} {'':>5} {r['log_loss']:>8.4f} {r['brier']:>7.4f} {r['ece_10']:>7.4f} {r['ece_15']:>7.4f}")
    print("  --- VALIDATION SET (evaluare reala) ---")
    for r in data["val_results"]:
        print(f"  {r['label']:<27} {r['accuracy']:>4.1%} {r['log_loss']:>8.4f} {r['brier']:>7.4f} {r['ece_10']:>7.4f} {r['ece_15']:>7.4f}")
    print("=" * 75)

    print()
    dl = data["deltas"]
    ov = data["overfit"]
    print("  ISOTONIC  — val ECE@10 delta:", f"{dl['iso_ece']:+.4f}",
          "| ll delta:", f"{dl['iso_ll']:+.4f}",
          "| overfit:", "DA" if ov["iso"] else "NU")
    print("  PLATT     — val ECE@10 delta:", f"{dl['platt_ece']:+.4f}",
          "| ll delta:", f"{dl['platt_ll']:+.4f}",
          "| overfit:", "DA" if ov["platt"] else "NU")

    md_section = build_markdown_section(data)
    out = Path("BACKTEST_RESULTS.md")
    existing = out.read_text(encoding="utf-8") if out.exists() else ""
    out.write_text(existing + md_section, encoding="utf-8")

    root_out = Path("../BACKTEST_RESULTS.md")
    if root_out.exists():
        existing_root = root_out.read_text(encoding="utf-8")
        root_out.write_text(existing_root + md_section, encoding="utf-8")

    logger.info("Sectiune Sub-faza D adaugata la BACKTEST_RESULTS.md.")
