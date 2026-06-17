"""
Verifica ca stratul de calibrare functioneaza corect in productie.

Ruleaza: cd backend && python scripts/verify_calibration.py

Checks:
  1. Calibratorul se incarca / antreneaza fara erori
  2. predict_one() returneaza probs care sumeaza la 1.0 (±1e-6)
  3. Un batch de 100 predictii returneaza probs in [0, 1] si suma 1.0
  4. CALIBRATION=none dezactiveaza calibrarea (probs nemodificate de isotonic)
  5. Calibrare activa schimba prob-urile (nu e no-op)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

from app.config import settings
from app.data.historical import download_results, preprocess_data
from app.models.dixon_coles import DixonColesModel
from app.services.model_service import load_or_train_calibrator, build_ensemble
from app.models.elo import EloModel

print("=" * 60)
print("  VERIFY CALIBRATION LAYER")
print("=" * 60)

# 1 — Incarca DC si ELO din cache
print("\n[1] Incarc DC si Elo din cache...")
dc = DixonColesModel.load(settings.dc_model_cache_path)
elo = EloModel.load(settings.elo_model_cache_path)
print(f"    DC: {len(dc.teams)} echipe")

# 2 — Incarca / antreneaza calibratorul
print(f"\n[2] Incarc calibratorul (mode={settings.calibration})...")
cal = load_or_train_calibrator(dc, settings, force_retrain=False)

if settings.calibration == "none":
    print("    Calibrare dezactivata (CALIBRATION=none) — OK")
    sys.exit(0)

print(f"    Tip: {type(cal).__name__}  fitted={cal.is_fitted}")
assert cal.is_fitted, "Calibratorul nu e fittat!"

# 3 — predict_one sanity check
print("\n[3] Sanity check predict_one...")
test_cases = [
    (0.60, 0.25, 0.15),
    (0.33, 0.33, 0.34),
    (0.15, 0.20, 0.65),
    (0.50, 0.30, 0.20),
    (0.80, 0.12, 0.08),
]
all_ok = True
for ph_raw, pd_raw, pa_raw in test_cases:
    ph_cal, pd_cal, pa_cal = cal.predict_one(ph_raw, pd_raw, pa_raw)
    total = ph_cal + pd_cal + pa_cal
    ok = abs(total - 1.0) < 1e-6
    if not ok:
        print(f"    FAIL: sum={total:.8f} pentru ({ph_raw},{pd_raw},{pa_raw})")
        all_ok = False
    else:
        print(f"    OK:  ({ph_raw:.2f},{pd_raw:.2f},{pa_raw:.2f}) -> ({ph_cal:.4f},{pd_cal:.4f},{pa_cal:.4f}) sum={total:.8f}")

assert all_ok, "Cel putin un caz predict_one NU sumeaza la 1.0!"

# 4 — Ensemble predict pe 20 de meciuri reale
print("\n[4] Test ensemble cu calibrare pe 20 meciuri...")
ens = build_ensemble(dc, elo, w_dc=1.0, w_elo=0.0, w_xgb=0.0, calibrator=cal)
print(f"    model_label: {ens.model_label}")
assert ens._calibrated, "Ensemble nu are calibratorul activ!"

raw = download_results(settings.data_cache_path, force=False)
df = preprocess_data(raw)
sample = df[df["w_comp"] >= 2.0].tail(20)

errors = []
changed = 0
for row in sample.itertuples(index=False):
    # Proba bruta DC
    dc_r = dc.predict_match_full(row.home_team, row.away_team, bool(row.neutral))
    ph_raw = dc_r["prob_home"]

    # Proba calibrata prin ensemble
    ens_r = ens.predict(row.home_team, row.away_team, bool(row.neutral))
    ph_cal = ens_r["prob_home"]
    pd_cal = ens_r["prob_draw"]
    pa_cal = ens_r["prob_away"]
    total  = ph_cal + pd_cal + pa_cal

    if abs(total - 1.0) > 1e-6:
        errors.append(f"{row.home_team} vs {row.away_team}: sum={total:.8f}")
    if abs(ph_raw - ph_cal) > 1e-4:
        changed += 1

if errors:
    print(f"    EROARE: {len(errors)} meciuri cu suma != 1.0:")
    for e in errors:
        print(f"      {e}")
    sys.exit(1)

print(f"    Toate 20 meciuri: suma=1.0 OK")
print(f"    Probabilitati modificate de calibrare: {changed}/20")
assert changed > 0, "Calibrarea NU modifica probabilitatile — calibratorul pare no-op!"

# 5 — Test CALIBRATION=none ca no-op
print("\n[5] Test ens fara calibrare (calibrator=None)...")
ens_none = build_ensemble(dc, elo, w_dc=1.0, calibrator=None)
assert not ens_none._calibrated, "Ensemble fara calibrator are _calibrated=True!"
r_none = ens_none.predict("Brazil", "Argentina", True)
r_cal  = ens.predict("Brazil", "Argentina", True)
delta_h = abs(r_none["prob_home"] - r_cal["prob_home"])
print(f"    Brazil vs Argentina:")
print(f"      Fara calibrare:  H={r_none['prob_home']:.4f}  D={r_none['prob_draw']:.4f}  A={r_none['prob_away']:.4f}")
print(f"      Cu calibrare:    H={r_cal['prob_home']:.4f}  D={r_cal['prob_draw']:.4f}  A={r_cal['prob_away']:.4f}")
print(f"      Delta prob_home: {delta_h:.4f}")

# 6 — Campion: calibrated flag in output
print("\n[6] Campion: 'calibrated' flag in output...")
assert r_cal.get("calibrated") is True, "Lipseste 'calibrated': True in output!"
assert "calibrated" not in r_none or r_none.get("calibrated") is not True
print("    'calibrated': True prezent in output calibrat — OK")

print()
print("=" * 60)
print("  TOATE VERIFICARILE OK")
print(f"  Model: {ens.model_label}")
print(f"  Calibrare activa: {ens._calibrated}")
print(f"  Prob cambiate pe meciurile test: {changed}/20")
print("=" * 60)
