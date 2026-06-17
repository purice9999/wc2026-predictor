"""Diagnozez cele 43 de meciuri StatsBomb nematched."""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")

import pandas as pd
from app.config import settings
from app.data.historical import download_results, preprocess_data
from app.data.xg_fetcher import fetch_all_xg

xg_df = fetch_all_xg(cache_dir=".cache/xg", force=False)
raw   = download_results(settings.data_cache_path, force=False)
df    = preprocess_data(raw)

# Construiesc lookup dupa (date, home, away)
df_keys = set(zip(df["date_dt"].astype(str), df["home_team"], df["away_team"]))

xg_df["date_s"] = xg_df["date"].dt.date.astype(str)
matched   = []
unmatched = []
for _, r in xg_df.iterrows():
    key = (r["date_s"], r["home_team"], r["away_team"])
    if key in df_keys:
        matched.append(key)
    else:
        unmatched.append(r)

print(f"Matched:   {len(matched)}")
print(f"Unmatched: {len(unmatched)}")
print()

if unmatched:
    um_df = pd.DataFrame(unmatched).reset_index(drop=True)
    print("=== UNMATCHED ===")
    print(um_df[["date_s", "home_team", "away_team", "competition"]].to_string(index=False))
    print()

    # Verific daca exista in df cu denumiri diferite (cauta dupa data)
    print("=== CAUTARE FUZZY (dupa data) ===")
    for _, r in um_df.iterrows():
        same_date = df[df["date_dt"].astype(str) == r["date_s"]]
        if not same_date.empty:
            for _, m in same_date.iterrows():
                if (r["home_team"].lower() in m["home_team"].lower() or
                    m["home_team"].lower() in r["home_team"].lower() or
                    r["away_team"].lower() in m["away_team"].lower() or
                    m["away_team"].lower() in r["away_team"].lower()):
                    print(f"  SB:  '{r['home_team']}' vs '{r['away_team']}'  [{r['date_s']}]")
                    print(f"  DF:  '{m['home_team']}' vs '{m['away_team']}'")
                    print()
                    break
