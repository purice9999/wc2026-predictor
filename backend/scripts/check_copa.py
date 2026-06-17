"""Check Copa America 2024 in historical dataset."""
import sys, io, warnings
warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, ".")

from app.config import settings
from app.data.historical import download_results
import pandas as pd

raw = download_results(settings.data_cache_path, force=False)
copa = raw[
    raw["tournament"].str.contains("Copa", case=False, na=False) &
    (raw["date"] >= "2024-06-01") &
    (raw["date"] <= "2024-07-31")
].sort_values("date")

print(f"Copa America 2024 in martj42: {len(copa)} meciuri")
if not copa.empty:
    print(copa[["date","home_team","away_team","home_score","away_score","tournament"]].to_string(index=False))
else:
    # Poate ca tournament se numeste altfel
    all_tourn = raw[raw["date"] >= "2024-06-01"]["tournament"].unique()
    print("Turnee in jun-iul 2024:")
    for t in sorted(all_tourn):
        print(f"  {t}")
