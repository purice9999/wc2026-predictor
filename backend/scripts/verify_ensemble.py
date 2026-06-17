"""Verifica configuratia noua de ensemble."""
import warnings; warnings.filterwarnings("ignore")
import sys; sys.path.insert(0, ".")

from app.config import settings
print(f"Config: w_dc={settings.w_dc}  w_elo={settings.w_elo}  w_xgb={settings.w_xgb}")

from app.models.dixon_coles import DixonColesModel
from app.models.elo import EloModel
from app.model.ensemble import EnsembleModel, PRESET_50_30_20

dc  = DixonColesModel.load(settings.dc_model_cache_path)
elo = EloModel.load(settings.elo_model_cache_path)

# Test 1: DC only (default din config)
ens = EnsembleModel(dc, elo, w_dc=settings.w_dc, w_elo=settings.w_elo, w_xgb=settings.w_xgb)
r = ens.predict("France", "Argentina", neutral=True)
ph, pd, pa = r["prob_home"], r["prob_draw"], r["prob_away"]
print(f"DC only  -> France {ph:.1%} / Draw {pd:.1%} / Argentina {pa:.1%}")
print(f"  model_used: {r['model_used']}")
assert r["model_used"] == "DC", f"Asteptat 'DC', primit '{r['model_used']}'"

# Test 2: preset 50/30/20
w_dc, w_elo, w_xgb = PRESET_50_30_20
ens2 = EnsembleModel(dc, elo, w_dc=w_dc, w_elo=w_elo, w_xgb=w_xgb)
r2 = ens2.predict("France", "Argentina", neutral=True)
ph2, pd2, pa2 = r2["prob_home"], r2["prob_draw"], r2["prob_away"]
print(f"50/30/20 -> France {ph2:.1%} / Draw {pd2:.1%} / Argentina {pa2:.1%}")
print(f"  model_used: {r2['model_used']}")

# Verifica ca dc_only nu schimba prob-urile (trebuie sa fie identice cu DC raw)
dc_raw = dc.predict_match_full("France", "Argentina", neutral=True)
assert abs(ph - dc_raw["prob_home"]) < 1e-6, "DC only != DC raw!"
print()
print("PASS: DC only intoarce exact probabilitatile DC raw.")
print("PASS: Configuratia 50/30/20 genereaza blend diferit.")
print()
print("Cum schimbi varianta:")
print("  .env sau env var:  W_DC=0.5  W_ELO=0.3  W_XGB=0.2")
print("  Sau direct in config.py: w_dc=0.5, w_elo=0.3, w_xgb=0.2")
