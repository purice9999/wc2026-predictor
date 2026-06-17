"""Diagnostica detaliata pentru cele 43 de meciuri nematched."""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
from app.config import settings
from app.data.historical import download_results, preprocess_data
from app.data.xg_fetcher import fetch_all_xg

xg_df = fetch_all_xg(cache_dir=".cache/xg", force=False)
raw   = download_results(settings.data_cache_path, force=False)
df    = preprocess_data(raw)

xg_df["date_s"] = xg_df["date"].dt.date.astype(str)
df_key_set = set(zip(df["date_dt"].astype(str), df["home_team"], df["away_team"]))

unmatched = [r for _, r in xg_df.iterrows()
             if (r["date_s"], r["home_team"], r["away_team"]) not in df_key_set]

print(f"Unmatched: {len(unmatched)}")
print()

# Pentru fiecare unmatch, gaseste meciuri din df in aceeasi zi
print("=== DIAGNOSTICA DETALIATA ===")
fixed = {}   # (sb_home, sb_away) -> (df_home, df_away)

for r in unmatched:
    sb_home = r["home_team"]
    sb_away = r["away_team"]
    date_s  = r["date_s"]
    comp    = r["competition"]

    same_date = df[df["date_dt"].astype(str) == date_s]

    # Cauta meci similar
    found = False
    for _, m in same_date.iterrows():
        score_h = (sb_home.lower().strip() in m["home_team"].lower() or
                   m["home_team"].lower() in sb_home.lower())
        score_a = (sb_away.lower().strip() in m["away_team"].lower() or
                   m["away_team"].lower() in sb_away.lower())
        # match pe ambele echipe (cel putin partial)
        if score_h and score_a:
            if sb_home != m["home_team"] or sb_away != m["away_team"]:
                fixed[(sb_home, sb_away)] = (m["home_team"], m["away_team"])
                print(f"  [{comp}] {date_s}")
                print(f"    SB:  [{repr(sb_home)}] vs [{repr(sb_away)}]")
                print(f"    DF:  [{repr(m['home_team'])}] vs [{repr(m['away_team'])}]")
            found = True
            break

    if not found:
        # Verifica daca meciurile exista in df cu ordinea echipelor inversata
        for _, m in same_date.iterrows():
            if (sb_home.lower() in m["away_team"].lower() and
                    sb_away.lower() in m["home_team"].lower()):
                print(f"  [{comp}] {date_s} INVERSAT!")
                print(f"    SB:  {sb_home} vs {sb_away}")
                print(f"    DF:  {m['home_team']} vs {m['away_team']}")
                found = True
                break

    if not found:
        # Meciul nu exista deloc in df in ziua respectiva
        print(f"  [{comp}] {date_s} NOT IN DF AT ALL: {sb_home} vs {sb_away}")

print()
print(f"Total mapari de corectat: {len(fixed)}")
print()
# Rezumat distinctiv
all_sb_names = set()
for sb_h, sb_a in [key for key in fixed]:
    all_sb_names.add(sb_h)
    all_sb_names.add(sb_a)
df_names_used = set()
for df_h, df_a in fixed.values():
    df_names_used.add(df_h)
    df_names_used.add(df_a)

print("Adaugiri necesare in SB_TO_WC:")
for (sb_h, sb_a), (df_h, df_a) in fixed.items():
    if sb_h != df_h:
        print(f"  '{sb_h}': '{df_h}',")
    if sb_a != df_a:
        print(f"  '{sb_a}': '{df_a}',")
