"""Raport acoperire xG — Sub-faza A."""
import sys
import warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")

import pandas as pd
from app.data.xg_fetcher import fetch_all_xg, merge_xg_into_df, coverage_report
from app.data.historical import download_results, preprocess_data
from app.config import settings

xg_df = fetch_all_xg(cache_dir=".cache/xg", force=False)
print(f"xG loaded: {len(xg_df)} meciuri")
comp_counts = xg_df["competition"].value_counts()
for comp, cnt in comp_counts.items():
    print(f"  {comp}: {cnt}")

raw = download_results(settings.data_cache_path, force=False)
df = preprocess_data(raw)
print(f"\nDate istorice: {len(df)} meciuri total")

df_merged = merge_xg_into_df(df, xg_df)

report = coverage_report(df_merged)
print("\n=== RAPORT ACOPERIRE xG ===")
print(f"  Total meciuri antrenament:  {report['total_matches']:,}")
print(f"  Meciuri cu xG:              {report['matches_with_xg']:,}")
print(f"  Acoperire bruta:            {report['raw_coverage_pct']:.1f}%")
print(f"  Acoperire ponderata:        {report['weighted_coverage_pct']:.1f}%")

sub = df_merged[df_merged["has_xg"]] if "has_xg" in df_merged.columns else pd.DataFrame()
if not sub.empty:
    print(f"\n  Interval xG: {sub['date_dt'].min()} -- {sub['date_dt'].max()}")
    # sample xG values
    print("\nSample xG (primele 5 meciuri cu xG):")
    cols = ["date_dt", "home_team", "away_team", "home_score", "away_score", "home_xg", "away_xg"]
    print(sub[cols].head(5).to_string(index=False))
