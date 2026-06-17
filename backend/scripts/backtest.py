"""
Backtest temporal cu zero data leakage — WC 2026 Predictor.

Design:
  - Split TEMPORAL: antrenare pe date < CUTOFF, testare pe date in [CUTOFF, TEST_END]
  - Fiecare model antrenat EXCLUSIV pe pre-cutoff data
  - La inferenta XGB: parametrii DC + ratings Elo + form/H2H stocate la finalul
    perioadei de train (nu se vad rezultatele din test set)
  - Friendlies excluse din test set (w_comp < 1.5 = zgomot pur)

Nota leakage documentata:
  DC este antrenat pe tot train set-ul, apoi parametrii sunt folositi ca features
  pentru XGB pe fiecare meci de training (in ordine cronologica). Aceasta inseamna
  ca features DC pentru primele meciuri de training "vad" DC parametrii influentiati
  de meciuri ulterioare din aceeasi fereastra de training. Acesta este un compromis
  comun in modele iterative — nu afecteaza evaluarea pe test set.

Utilizare:
  cd backend
  python scripts/backtest.py [--cutoff YYYY-MM-DD] [--test-end YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
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
from app.models.dixon_coles import DixonColesModel
from app.models.elo import EloModel
from app.models.xgboost_model import XGBoostPredictor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Cutoff implicit ──────────────────────────────────────────────────────────
# Dupa Euro 2024 (14 iul) + Copa 2024 (15 iul): cel mai curat punct de taiere
DEFAULT_CUTOFF   = date(2024, 7, 15)
# Inainte de WC 2026 (primul meci: ~11 iun 2026)
DEFAULT_TEST_END = date(2026, 6, 10)
# Excludem meciuri prietenie din test (prea mult zgomot)
MIN_COMP_WEIGHT  = 1.5

# ─── Variante ensemble ────────────────────────────────────────────────────────
ENSEMBLE_VARIANTS: list[tuple[str, float, float, float]] = [
    # (label, w_dc, w_elo, w_xgb)
    ("DC singur",              1.00, 0.00, 0.00),
    ("Elo singur",             0.00, 1.00, 0.00),
    ("XGB singur",             0.00, 0.00, 1.00),
    ("DC+Elo (65/35)",         0.65, 0.35, 0.00),
    ("DC+Elo+XGB 30/20/50",    0.30, 0.20, 0.50),  # current default
    ("DC+Elo+XGB 40/25/35",    0.40, 0.25, 0.35),
    ("DC+Elo+XGB 33/33/33",    0.33, 0.33, 0.33),
    ("DC+Elo+XGB 20/10/70",    0.20, 0.10, 0.70),
    ("DC+Elo+XGB 50/30/20",    0.50, 0.30, 0.20),
]


# ─── Metrici ──────────────────────────────────────────────────────────────────

def log_loss_mc(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-9) -> float:
    y_pred = np.clip(y_pred, eps, 1 - eps)
    return float(-np.mean(np.sum(y_true * np.log(y_pred), axis=1)))


def brier(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.sum((y_pred - y_true) ** 2, axis=1)))


def accuracy_1x2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.argmax(y_pred, axis=1) == np.argmax(y_true, axis=1)))


def ece(y_true: np.ndarray, y_pred: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error — pe toate cele 3 clase, flat."""
    flat_t = y_true.ravel()
    flat_p = y_pred.ravel()
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (flat_p >= lo) & (flat_p < hi)
        if not mask.any():
            continue
        frac = mask.mean()
        acc_b = flat_t[mask].mean()
        conf_b = flat_p[mask].mean()
        total += frac * abs(acc_b - conf_b)
    return float(total)


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "accuracy": round(accuracy_1x2(y_true, y_pred), 4),
        "log_loss": round(log_loss_mc(y_true, y_pred), 4),
        "brier":    round(brier(y_true, y_pred), 4),
        "ece":      round(ece(y_true, y_pred), 4),
    }


def one_hot(cls: int) -> list[int]:
    return [int(cls == i) for i in range(3)]


# ─── Predicții per model ──────────────────────────────────────────────────────

def predict_row_dc(row, dc: DixonColesModel) -> np.ndarray:
    r = dc.predict_match_full(row.home_team, row.away_team, bool(row.neutral))
    return np.array([r["prob_home"], r["prob_draw"], r["prob_away"]])


def predict_row_elo(row, elo: EloModel) -> np.ndarray:
    r = elo.predict(row.home_team, row.away_team, bool(row.neutral))
    return np.array([r["prob_home"], r["prob_draw"], r["prob_away"]])


def predict_row_xgb(row, xgb: XGBoostPredictor, dc: DixonColesModel, elo: EloModel) -> np.ndarray:
    r = xgb.predict(row.home_team, row.away_team, dc, elo, bool(row.neutral))
    return np.array([r["prob_home"], r["prob_draw"], r["prob_away"]])


def blend(p_dc, p_elo, p_xgb, w_dc, w_elo, w_xgb) -> np.ndarray:
    total = w_dc + w_elo + w_xgb
    p = (w_dc * p_dc + w_elo * p_elo + w_xgb * p_xgb) / total
    return p / p.sum()


# ─── Main backtest ────────────────────────────────────────────────────────────

def run_backtest(
    cutoff: date = DEFAULT_CUTOFF,
    test_end: date = DEFAULT_TEST_END,
) -> list[dict]:

    logger.info("=" * 60)
    logger.info("BACKTEST TEMPORAL — WC 2026 Predictor")
    logger.info("  Train: tot ce e < %s", cutoff)
    logger.info("  Test:  [%s, %s]", cutoff, test_end)
    logger.info("  Min competition weight in test: %.1f", MIN_COMP_WEIGHT)
    logger.info("=" * 60)

    # 1 — Date
    raw = download_results(settings.data_cache_path, force=False)
    df_all = preprocess_data(raw)

    df_train = df_all[df_all["date_dt"] < cutoff].copy()
    df_test  = df_all[
        (df_all["date_dt"] >= cutoff) &
        (df_all["date_dt"] <= test_end) &
        (df_all["w_comp"] >= MIN_COMP_WEIGHT)
    ].copy()

    logger.info(
        "Train: %d meciuri (%s – %s)",
        len(df_train), df_train["date_dt"].min(), df_train["date_dt"].max(),
    )
    logger.info(
        "Test:  %d meciuri competitive (%s – %s)",
        len(df_test), df_test["date_dt"].min(), df_test["date_dt"].max(),
    )

    if len(df_test) < 50:
        logger.error("Test set prea mic (%d < 50). Alege un cutoff mai vechi.", len(df_test))
        sys.exit(1)

    # 2 — Antrenare pe train split
    logger.info("Antrenare Dixon-Coles pe train split…")
    dc = DixonColesModel()
    dc.fit(df_train)

    logger.info("Antrenare Elo pe train split…")
    elo = EloModel()
    elo.fit(df_train)

    logger.info("Antrenare XGBoost pe train split…")
    xgb = XGBoostPredictor()
    try:
        xgb.fit(df_train, dc, elo)
        xgb_ok = True
        logger.info("XGBoost antrenat cu succes (%d features).", len(xgb._feature_importance))
    except Exception as exc:
        logger.error("XGBoost FAILED: %s — variantele cu XGB vor fi omise.", exc)
        xgb_ok = False

    # 3 — Predictii pe test split
    logger.info("Calculez predictii pe %d meciuri de test…", len(df_test))
    y_true_list = []
    p_dc_list   = []
    p_elo_list  = []
    p_xgb_list  = []
    failed       = 0

    for row in df_test.itertuples(index=False):
        hs, as_ = int(row.home_score), int(row.away_score)
        true_cls = 0 if hs > as_ else (1 if hs == as_ else 2)
        y_true_list.append(one_hot(true_cls))

        try:
            p_dc_list.append(predict_row_dc(row, dc))
        except Exception:
            p_dc_list.append(np.array([1/3, 1/3, 1/3]))
            failed += 1

        try:
            p_elo_list.append(predict_row_elo(row, elo))
        except Exception:
            p_elo_list.append(np.array([1/3, 1/3, 1/3]))

        if xgb_ok:
            try:
                p_xgb_list.append(predict_row_xgb(row, xgb, dc, elo))
            except Exception:
                p_xgb_list.append(np.array([1/3, 1/3, 1/3]))
        else:
            p_xgb_list.append(np.array([1/3, 1/3, 1/3]))

    if failed:
        logger.warning("%d predicții DC au eșuat (echipe fără date) — fallback 1/3.", failed)

    y_true = np.array(y_true_list, dtype=np.float64)
    p_dc   = np.array(p_dc_list,   dtype=np.float64)
    p_elo  = np.array(p_elo_list,  dtype=np.float64)
    p_xgb  = np.array(p_xgb_list,  dtype=np.float64)

    # 4 — Calcul metrici pentru fiecare variantă
    results = []
    for label, w_dc, w_elo, w_xgb in ENSEMBLE_VARIANTS:
        if w_xgb > 0 and not xgb_ok:
            continue
        p_blend = np.array([
            blend(p_dc[i], p_elo[i], p_xgb[i], w_dc, w_elo, w_xgb)
            for i in range(len(y_true))
        ])
        m = metrics(y_true, p_blend)
        results.append({
            "variant":  label,
            "w_dc":     w_dc,
            "w_elo":    w_elo,
            "w_xgb":    w_xgb,
            **m,
        })
        logger.info(
            "%-28s  acc=%.1f%%  ll=%.4f  brier=%.4f  ece=%.4f",
            label, m["accuracy"] * 100, m["log_loss"], m["brier"], m["ece"],
        )

    # Sortam dupa log-loss (criteriu principal)
    results.sort(key=lambda x: x["log_loss"])

    # 5 — Statistici test set (distributie rezultate)
    outcomes = np.argmax(y_true, axis=1)
    n_test = len(y_true)
    n_h = int((outcomes == 0).sum())
    n_d = int((outcomes == 1).sum())
    n_a = int((outcomes == 2).sum())

    logger.info("-" * 60)
    logger.info("Test set: %d meciuri — H:%d (%.0f%%)  D:%d (%.0f%%)  A:%d (%.0f%%)",
                n_test, n_h, 100*n_h/n_test, n_d, 100*n_d/n_test, n_a, 100*n_a/n_test)

    meta = {
        "cutoff":         str(cutoff),
        "test_end":       str(test_end),
        "n_train":        len(df_train),
        "n_test":         n_test,
        "n_home":         n_h,
        "n_draw":         n_d,
        "n_away":         n_a,
        "xgb_ok":         xgb_ok,
        "min_comp_weight": MIN_COMP_WEIGHT,
    }
    return results, meta


def build_markdown(results: list[dict], meta: dict) -> str:
    lines = [
        "# Backtest Results — WC 2026 Predictor",
        "",
        "## Configurare split",
        "",
        f"| Parametru | Valoare |",
        f"|-----------|---------|",
        f"| Cutoff (end train) | {meta['cutoff']} |",
        f"| Test end | {meta['test_end']} |",
        f"| Meciuri train | {meta['n_train']:,} |",
        f"| Meciuri test | {meta['n_test']:,} (competitive, w_comp ≥ {meta['min_comp_weight']}) |",
        f"| Distributie test (H/D/A) | {meta['n_home']}/{meta['n_draw']}/{meta['n_away']} = "
        f"{100*meta['n_home']/meta['n_test']:.0f}%/{100*meta['n_draw']/meta['n_test']:.0f}%/"
        f"{100*meta['n_away']/meta['n_test']:.0f}% |",
        f"| XGBoost antrenat | {'DA' if meta['xgb_ok'] else 'NU (eroare)'} |",
        "",
        "## Metodologie anti-leakage",
        "",
        "- **Split strict temporal**: modelele văd ZERO din test set la antrenare.",
        "- **Dixon-Coles**: antrenat exclusiv pe train split.",
        "- **Elo**: updatat cronologic pe train split; ratingurile de inferenta = stare la finalul trainului.",
        "- **XGBoost features la training**: Elo + form/H2H construite cronologic (match N foloseste"
        " doar date din matches 1..N-1). ✅",
        "- **XGBoost features la inferenta (test set)**: DC params + Elo ratings + form/H2H ="
        " stare la finalul perioadei de train. Forma este **stala** (nu se actualizeaza pe test set)"
        " — limitare a holdout simplu vs walk-forward.",
        "- **Nota leakage minora documentata**: parametrii DC sunt antrenati pe tot train set-ul,"
        " apoi folositi ca features per meci in XGB (XGB vede DC params influentati de meciuri"
        " ulterioare din aceeasi fereastra de training). Compromis comun — nu afecteaza evaluarea"
        " pe test set.",
        "- **Prietenii excluse** din test set (w_comp < 1.5).",
        "",
        "## Tabel comparativ — sortat dupa Log-Loss (↑ mai mic = mai bun)",
        "",
        "| Varianta | Ponderi (DC/Elo/XGB) | Accuracy | Log-Loss | Brier | ECE |",
        "|----------|---------------------|----------|----------|-------|-----|",
    ]

    best_ll = results[0]["log_loss"]  # deja sortat
    for r in results:
        marker = " ⬅ BEST" if r["log_loss"] == best_ll else ""
        lines.append(
            f"| {r['variant']}{marker} "
            f"| {r['w_dc']:.0%} / {r['w_elo']:.0%} / {r['w_xgb']:.0%} "
            f"| {r['accuracy']:.1%} "
            f"| **{r['log_loss']:.4f}** "
            f"| {r['brier']:.4f} "
            f"| {r['ece']:.4f} |"
        )

    # Sectiuni de analiza
    dc_row  = next((r for r in results if r["variant"] == "DC singur"), None)
    elo_row = next((r for r in results if r["variant"] == "Elo singur"), None)
    xgb_row = next((r for r in results if r["variant"] == "XGB singur"), None)
    dc_elo  = next((r for r in results if r["variant"] == "DC+Elo (65/35)"), None)
    current = next((r for r in results if r["variant"] == "DC+Elo+XGB 30/20/50"), None)

    lines += [
        "",
        "## Analiza componente individuale",
        "",
    ]

    if dc_row and elo_row:
        better_base = "DC" if dc_row["log_loss"] < elo_row["log_loss"] else "Elo"
        lines.append(
            f"- **DC vs Elo**: DC log-loss={dc_row['log_loss']:.4f}, "
            f"Elo log-loss={elo_row['log_loss']:.4f} → **{better_base}** mai bun individual."
        )

    if dc_elo and dc_row and elo_row:
        base_best = min(dc_row["log_loss"], elo_row["log_loss"])
        impr = base_best - dc_elo["log_loss"]
        direction = "IMBUNATATIRE" if impr > 0 else "INRAUTATIRE"
        lines.append(
            f"- **DC+Elo blend** vs cel mai bun individual: "
            f"delta log-loss = {impr:+.4f} → {direction}."
        )

    if current and dc_elo:
        impr = dc_elo["log_loss"] - current["log_loss"]
        direction = "IMBUNATATIRE" if impr > 0 else "INRAUTATIRE"
        lines.append(
            f"- **XGBoost adauga valoare?** DC+Elo (65/35) log-loss={dc_elo['log_loss']:.4f} "
            f"vs DC+Elo+XGB (30/20/50) log-loss={current['log_loss']:.4f} "
            f"→ delta={impr:+.4f} ({direction})."
        )

    best_variant = results[0]
    lines += [
        "",
        "## Recomandare",
        "",
        f"Cel mai mic log-loss: **{best_variant['variant']}** "
        f"(ponderi DC={best_variant['w_dc']:.0%} / Elo={best_variant['w_elo']:.0%} / "
        f"XGB={best_variant['w_xgb']:.0%})",
        f"  - Log-Loss: {best_variant['log_loss']:.4f}",
        f"  - Accuracy: {best_variant['accuracy']:.1%}",
        f"  - Brier: {best_variant['brier']:.4f}",
        f"  - ECE: {best_variant['ece']:.4f}",
        "",
        "> **Nota**: Aceste numere reprezinta BASELINE-ul inaintea sub-fazelor B/C/D.",
        "> Orice modificare a modelului trebuie sa reduca log-loss-ul variantei curente active",
        "> (DC+Elo+XGB 30/20/50) inainte de a fi adoptata ca default.",
        "",
        "---",
        f"*Generat: {date.today()} | Train cutoff: {meta['cutoff']} | Test: {meta['n_test']} meciuri competitive*",
    ]

    return "\n".join(lines)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest temporal WC2026 Predictor")
    parser.add_argument(
        "--cutoff", default=str(DEFAULT_CUTOFF),
        help=f"Data sfarsit antrenare (default: {DEFAULT_CUTOFF})",
    )
    parser.add_argument(
        "--test-end", default=str(DEFAULT_TEST_END),
        help=f"Data sfarsit test (default: {DEFAULT_TEST_END})",
    )
    parser.add_argument(
        "--output", default="BACKTEST_RESULTS.md",
        help="Fisier output Markdown (relativ la backend/)",
    )
    args = parser.parse_args()

    results, meta = run_backtest(
        cutoff=date.fromisoformat(args.cutoff),
        test_end=date.fromisoformat(args.test_end),
    )

    md = build_markdown(results, meta)

    out_path = Path(args.output)
    out_path.write_text(md, encoding="utf-8")
    logger.info("Salvat → %s", out_path.resolve())

    # Print tabel in consola
    print("\n" + "=" * 65)
    print("  BACKTEST RESULTS")
    print("=" * 65)
    print(f"  Train: {meta['n_train']:,} meciuri  |  Test: {meta['n_test']:,} meciuri competitive")
    print(f"  Cutoff: {meta['cutoff']}  ->  {meta['test_end']}")
    print(f"  H/D/A in test: {meta['n_home']}/{meta['n_draw']}/{meta['n_away']}")
    print("-" * 65)
    print(f"  {'Varianta':<30} {'Acc':>6} {'LogLoss':>8} {'Brier':>7} {'ECE':>7}")
    print("-" * 65)
    for r in results:
        marker = " *" if r == results[0] else "  "
        print(f"{marker} {r['variant']:<30} {r['accuracy']:>5.1%} {r['log_loss']:>8.4f} {r['brier']:>7.4f} {r['ece']:>7.4f}")
    print("=" * 65)
    print(f"  * = cel mai mic log-loss")
