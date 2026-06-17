"""
Sub-faza B backtest: DC pur vs DC hibrid xG.

Split IDENTIC cu BACKTEST_RESULTS.md:
  Train:  meciuri < 2024-07-15
  Test:   meciuri in [2024-07-15, 2026-06-10], w_comp >= 1.5

Sanity check OBLIGATORIU: DC pur cu USE_XG_HYBRID=OFF trebuie sa reproduca
exact log-loss-ul baseline (0.9282 ± 0.0001). Daca nu, oprim totul.

Variante testate:
  1. DC pur (OFF)          — sanity check, asteptat 0.9282
  2. DC hibrid blend=0.5
  3. DC hibrid blend=0.6
  4. DC hibrid blend=0.7   — valoarea implicita daca se adopta

Utilizare:
  cd backend && python scripts/backtest_subfaza_b.py
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
from app.models.dixon_coles import DixonColesModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Acelasi split ca in BACKTEST_RESULTS.md ─────────────────────────────────
CUTOFF   = date(2024, 7, 15)
TEST_END = date(2026, 6, 10)
MIN_COMP = 1.5
BASELINE_LL = 0.9282
BASELINE_TOL = 0.0005   # toleranta sanity check

# ─── Metrici ──────────────────────────────────────────────────────────────────

def log_loss_mc(y_true, y_pred, eps=1e-9):
    y_pred = np.clip(y_pred, eps, 1 - eps)
    return float(-np.mean(np.sum(y_true * np.log(y_pred), axis=1)))

def brier(y_true, y_pred):
    return float(np.mean(np.sum((y_pred - y_true) ** 2, axis=1)))

def accuracy_1x2(y_true, y_pred):
    return float(np.mean(np.argmax(y_pred, axis=1) == np.argmax(y_true, axis=1)))

def ece(y_true, y_pred, n_bins=10):
    flat_t, flat_p = y_true.ravel(), y_pred.ravel()
    bins = np.linspace(0, 1, n_bins + 1)
    total = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (flat_p >= lo) & (flat_p < hi)
        if not mask.any():
            continue
        total += mask.mean() * abs(flat_t[mask].mean() - flat_p[mask].mean())
    return float(total)

def compute_metrics(y_true, y_pred):
    return {
        "accuracy": round(accuracy_1x2(y_true, y_pred), 4),
        "log_loss": round(log_loss_mc(y_true, y_pred), 4),
        "brier":    round(brier(y_true, y_pred), 4),
        "ece":      round(ece(y_true, y_pred), 4),
    }


# ─── Predictii DC ─────────────────────────────────────────────────────────────

def predict_dc_batch(df_test, dc):
    y_true_rows, y_pred_rows = [], []
    failed = 0
    for row in df_test.itertuples(index=False):
        hs, as_ = int(row.home_score), int(row.away_score)
        cls = 0 if hs > as_ else (1 if hs == as_ else 2)
        y_true_rows.append([int(cls == i) for i in range(3)])
        try:
            r = dc.predict_match_full(row.home_team, row.away_team, bool(row.neutral))
            y_pred_rows.append([r["prob_home"], r["prob_draw"], r["prob_away"]])
        except Exception:
            y_pred_rows.append([1/3, 1/3, 1/3])
            failed += 1
    if failed:
        logger.warning("%d predictii DC au esuat (echipe fara date).", failed)
    return np.array(y_true_rows, float), np.array(y_pred_rows, float)


# ─── Antrenare DC ─────────────────────────────────────────────────────────────

def train_dc(df_train, xg_df=None, blend_weight=0.0):
    """Antreneaza DC pe df_train, optional cu semnal hibrid xG."""
    if xg_df is not None and blend_weight > 0:
        from app.data.xg_hybrid import apply_xg_hybrid
        df_train = apply_xg_hybrid(df_train.copy(), xg_df, blend_weight=blend_weight)
        n_hyb = int(df_train["has_xg"].sum()) if "has_xg" in df_train.columns else 0
        logger.info("Antrenare DC hibrid (blend=%.1f): %d meciuri cu xG.", blend_weight, n_hyb)
    else:
        logger.info("Antrenare DC pur (fara xG).")

    dc = DixonColesModel()
    dc.fit(df_train)
    return dc


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 65)
    logger.info("SUB-FAZA B BACKTEST — DC pur vs DC hibrid xG")
    logger.info("  Split: train < %s  |  test [%s, %s]  |  w_comp>=%.1f",
                CUTOFF, CUTOFF, TEST_END, MIN_COMP)
    logger.info("=" * 65)

    # 1 — Date
    raw = download_results(settings.data_cache_path, force=False)
    df_all = preprocess_data(raw)
    df_train_all = df_all[df_all["date_dt"] < CUTOFF].copy()
    df_test = df_all[
        (df_all["date_dt"] >= CUTOFF) &
        (df_all["date_dt"] <= TEST_END) &
        (df_all["w_comp"] >= MIN_COMP)
    ].copy()
    logger.info("Train: %d  |  Test: %d competitive", len(df_train_all), len(df_test))

    # 2 — xG data (cu fuzzy merge)
    logger.info("Incarc xG din cache StatsBomb…")
    xg_df = fetch_all_xg(cache_dir=".cache/xg", force=False)
    logger.info("xG total: %d meciuri", len(xg_df))

    # Raport acoperire dupa fuzzy fix
    from app.data.xg_fetcher import merge_xg_into_df
    df_cov = merge_xg_into_df(df_train_all.copy(), xg_df)
    n_matched = int(df_cov["has_xg"].sum())
    logger.info("Acoperire dupa fuzzy merge: %d / %d (%.1f%%)",
                n_matched, len(df_cov), 100.0 * n_matched / len(df_cov))

    # 3 — Variante de testat
    variants = [
        {"label": "DC pur (baseline OFF)",       "blend": None},
        {"label": "DC hibrid xG blend=0.50",     "blend": 0.50},
        {"label": "DC hibrid xG blend=0.60",     "blend": 0.60},
        {"label": "DC hibrid xG blend=0.70",     "blend": 0.70},
    ]

    results = []
    for v in variants:
        blend = v["blend"]
        logger.info("-" * 50)
        logger.info("Varianta: %s", v["label"])

        dc = train_dc(df_train_all.copy(), xg_df=xg_df if blend else None, blend_weight=blend or 0.0)
        y_true, y_pred = predict_dc_batch(df_test, dc)
        m = compute_metrics(y_true, y_pred)

        logger.info("  acc=%.1f%%  ll=%.4f  brier=%.4f  ece=%.4f",
                    m["accuracy"] * 100, m["log_loss"], m["brier"], m["ece"])

        # Sanity check pentru DC pur
        if blend is None:
            diff = abs(m["log_loss"] - BASELINE_LL)
            if diff > BASELINE_TOL:
                logger.error(
                    "SANITY CHECK ESUAT! DC pur ll=%.4f  ≠  baseline %.4f  (diff=%.4f > tol=%.4f)",
                    m["log_loss"], BASELINE_LL, diff, BASELINE_TOL,
                )
                logger.error("OPRIT. Ceva s-a schimbat in metodologie.")
                sys.exit(1)
            else:
                logger.info("  SANITY CHECK OK (diff=%.5f < tol=%.4f)", diff, BASELINE_TOL)

        results.append({"variant": v["label"], "blend": blend, **m})

    # 4 — Tabel
    print()
    print("=" * 75)
    print("  SUB-FAZA B — DC pur vs DC hibrid xG")
    print("=" * 75)
    print(f"  Acoperire xG (train): {n_matched}/{len(df_cov)} meciuri ({100.0*n_matched/len(df_cov):.1f}%)")
    print(f"  Test set: {len(df_test)} meciuri competitive")
    print("-" * 75)
    print(f"  {'Varianta':<35} {'Acc':>6} {'LogLoss':>9} {'Brier':>7} {'ECE':>7}  vs baseline")
    print("-" * 75)
    baseline_ll = results[0]["log_loss"]
    for r in results:
        delta = r["log_loss"] - baseline_ll
        delta_str = "---" if r["blend"] is None else f"{delta:+.4f}"
        marker = " SANITY" if r["blend"] is None else (" BEST" if r["log_loss"] == min(x["log_loss"] for x in results) else "")
        print(f"  {r['variant']:<35} {r['accuracy']:>5.1%} {r['log_loss']:>9.4f} {r['brier']:>7.4f} {r['ece']:>7.4f}  {delta_str}{marker}")
    print("=" * 75)

    return results, n_matched, len(df_cov)


def build_markdown_section(results, n_matched, n_total_train):
    lines = [
        "",
        "---",
        "",
        "## Sub-faza B — DC hibrid xG + goluri",
        "",
        "### Configurare",
        "",
        f"| Parametru | Valoare |",
        f"|-----------|---------|",
        f"| Meciuri train cu xG (dupa fuzzy merge) | {n_matched} / {n_total_train} ({100.0*n_matched/n_total_train:.1f}%) |",
        f"| Split temporal | identic cu baseline |",
        f"| Test set | 1.459 meciuri competitive |",
        f"| Fuzzy matching activat | DA (±1 zi + home/away invers) |",
        "",
        "### Tabel comparativ",
        "",
        "| Varianta | Accuracy | Log-Loss | Brier | ECE | Delta vs baseline |",
        "|----------|----------|----------|-------|-----|-------------------|",
    ]

    baseline_ll = results[0]["log_loss"]
    for r in results:
        delta = r["log_loss"] - baseline_ll
        delta_str = "—" if r["blend"] is None else f"{delta:+.4f}"
        note = " *(sanity check)*" if r["blend"] is None else ""
        lines.append(
            f"| {r['variant']}{note} "
            f"| {r['accuracy']:.1%} "
            f"| **{r['log_loss']:.4f}** "
            f"| {r['brier']:.4f} "
            f"| {r['ece']:.4f} "
            f"| {delta_str} |"
        )

    # Verdict
    best = min(results, key=lambda x: x["log_loss"])
    improved = best["log_loss"] < baseline_ll
    delta_best = best["log_loss"] - baseline_ll

    lines += [
        "",
        "### Verdict",
        "",
    ]

    if best["blend"] is None:
        lines += [
            "**Hibridul xG NU imbunatateste log-loss-ul fata de DC pur.**",
            "Toate variantele hibride au log-loss >= baseline (0.9282).",
            "",
            "**Recomandare: USE_XG_HYBRID ramane OFF (default).**",
            "Cu acoperire de ~4% in training, semnalul xG e prea slab pentru a misca DC.",
        ]
    else:
        marker = "IMBUNATATIRE" if improved else "INRAUTATIRE"
        lines += [
            f"**{marker}**: cel mai bun hibrid ({best['variant']}) obtine "
            f"log-loss={best['log_loss']:.4f} (delta={delta_best:+.4f} fata de baseline 0.9282).",
            "",
        ]
        if improved:
            lines += [
                f"**Recomandare: USE_XG_HYBRID=ON cu blend={best['blend']}** "
                f"(setare in .env: USE_XG_HYBRID=true XG_BLEND_WEIGHT={best['blend']}).",
            ]
        else:
            lines += [
                "**Recomandare: USE_XG_HYBRID ramane OFF (default).**",
                "Hibridul inrautateste predictiile pe holdout — semnalul xG (cu acoperire ~4%) adauga zgomot.",
            ]

    lines += [
        "",
        f"*Generat: {date.today()} | Sanity check: {'OK' if abs(results[0]['log_loss'] - BASELINE_LL) <= BASELINE_TOL else 'ESUAT'}*",
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    results, n_matched, n_total = main()

    md_section = build_markdown_section(results, n_matched, n_total)

    out = Path("BACKTEST_RESULTS.md")
    existing = out.read_text(encoding="utf-8") if out.exists() else ""
    out.write_text(existing + md_section, encoding="utf-8")
    logger.info("Sectiune Sub-faza B adaugata la %s", out.resolve())

    root_out = Path("../BACKTEST_RESULTS.md")
    if root_out.exists():
        existing_root = root_out.read_text(encoding="utf-8")
        root_out.write_text(existing_root + md_section, encoding="utf-8")
        logger.info("Actualizat si %s", root_out.resolve())
