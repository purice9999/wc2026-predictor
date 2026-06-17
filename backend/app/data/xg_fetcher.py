"""
Sub-faza A: Fetcher de date xG din StatsBomb Open Data.

Sursa: StatsBomb Open Data (gratuit, fara rate-limit agresiv)
Competitii acoperite (fereastra 2020-2026):
  - FIFA World Cup 2022        (comp=43, season=106) — 64 meciuri
  - UEFA Euro 2020             (comp=55, season=43)  — 51 meciuri
  - UEFA Euro 2024             (comp=55, season=282) — 51 meciuri
  - Copa America 2024          (comp=223,season=282) — 32 meciuri
  - Africa Cup of Nations 2023 (comp=1267,season=107)— 52 meciuri
Total estimat: ~250 meciuri cu xG in fereastra de antrenament (6 ani).

Cache: .cache/xg/  — parquet per competitie/sezon + index global.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# ── Competitii tinta (in fereastra de antrenament) ────────────────────────────
TARGET_COMPS: list[tuple[int, int, str]] = [
    (43,   106, "FIFA World Cup 2022"),
    (55,    43, "UEFA Euro 2020"),
    (55,   282, "UEFA Euro 2024"),
    (223,  282, "Copa America 2024"),
    (1267, 107, "AFCON 2023"),
]

# ── Normalizare denumiri echipe StatsBomb → canonical WC 2026 ─────────────────
SB_TO_WC: dict[str, str] = {
    "Cape Verde Islands":  "Cabo Verde",
    "Czech Republic":      "Czechia",
    "South Korea":         "Korea Republic",
    "Turkey":              "Türkiye",
    "Ivory Coast":         "Côte d'Ivoire",
    "Côte d'Ivoire":  "Côte d'Ivoire",
    "Congo DR":            "Congo DR",
    "Bosnia-Herzegovina":  "Bosnia and Herzegovina",
    "Curacao":             "Curaçao",
    "USA":                 "United States",
    "DR Congo":            "Congo DR",
    "Korea DPR":           "Korea DPR",
    "North Macedonia":     "North Macedonia",
}

DELAY_SEC: float = 1.5   # politicos fata de StatsBomb servers


def _norm(name: str) -> str:
    """Normalizeaza numele echipei la canonical WC 2026."""
    return SB_TO_WC.get(name, name)


def _cache_path(cache_dir: Path, comp_id: int, season_id: int) -> Path:
    return cache_dir / f"xg_comp{comp_id}_s{season_id}.parquet"


def _fetch_one_competition(
    comp_id: int,
    season_id: int,
    label: str,
    cache_dir: Path,
    force: bool = False,
) -> pd.DataFrame:
    """Descarca xG pentru o competitie/sezon; cacheaza rezultatul."""
    cache_file = _cache_path(cache_dir, comp_id, season_id)

    if not force and cache_file.exists():
        df = pd.read_parquet(cache_file)
        logger.info("  [cache] %s — %d meciuri cu xG.", label, len(df))
        return df

    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from statsbombpy import sb as _sb

        logger.info("  Descarc meciuri %s…", label)
        matches = _sb.matches(competition_id=comp_id, season_id=season_id)
        logger.info("  %d meciuri gasite.", len(matches))

        rows = []
        for _, row in matches.iterrows():
            mid = int(row["match_id"])
            ht_raw = str(row["home_team"])
            at_raw = str(row["away_team"])
            match_date = str(row.get("match_date", ""))

            ht = _norm(ht_raw)
            at = _norm(at_raw)

            try:
                time.sleep(DELAY_SEC)
                events = _sb.events(match_id=mid)
                shots = events[events["type"] == "Shot"]
                if "shot_statsbomb_xg" not in shots.columns or shots.empty:
                    logger.debug("  No xG for match %d (%s vs %s)", mid, ht, at)
                    continue

                team_xg = shots.groupby("team")["shot_statsbomb_xg"].sum()
                # mapam echipele la canonical
                home_xg = float(team_xg.get(ht_raw, team_xg.get(ht, 0.0)))
                away_xg = float(team_xg.get(at_raw, team_xg.get(at, 0.0)))

                rows.append({
                    "match_id_sb": mid,
                    "date": match_date[:10],
                    "home_team": ht,
                    "away_team": at,
                    "home_xg":  round(home_xg, 4),
                    "away_xg":  round(away_xg, 4),
                    "competition": label,
                })
            except Exception as exc:
                logger.warning("  Eroare meci %d: %s", mid, exc)

        df = pd.DataFrame(rows)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache_file, index=False)
            logger.info("  Salvat %d meciuri cu xG → %s", len(df), cache_file.name)
        else:
            logger.warning("  Nicio inregistrare xG pentru %s.", label)
        return df

    except ImportError:
        logger.error("  statsbombpy nu e instalat.")
        return pd.DataFrame()
    except Exception as exc:
        logger.error("  Eroare competitie %s: %s", label, exc)
        return pd.DataFrame()


def fetch_all_xg(cache_dir: str = ".cache/xg", force: bool = False) -> pd.DataFrame:
    """Descarca xG din toate competitiile tinta; returneaza DataFrame unificat.

    Coloane: date, home_team, away_team, home_xg, away_xg, competition
    """
    cdir = Path(cache_dir)
    cdir.mkdir(parents=True, exist_ok=True)
    index_file = cdir / "xg_all.parquet"

    if not force and index_file.exists():
        df = pd.read_parquet(index_file)
        logger.info("xG index loaded from cache: %d meciuri.", len(df))
        return df

    logger.info("=== Sub-faza A: Descarc date xG (StatsBomb) ===")
    pieces = []
    for comp_id, season_id, label in TARGET_COMPS:
        piece = _fetch_one_competition(comp_id, season_id, label, cdir, force=force)
        if not piece.empty:
            pieces.append(piece)

    if not pieces:
        logger.warning("Nicio data xG descarcata.")
        return pd.DataFrame(columns=["date", "home_team", "away_team",
                                     "home_xg", "away_xg", "competition"])

    all_xg = pd.concat(pieces, ignore_index=True)
    all_xg = all_xg.drop_duplicates(subset=["date", "home_team", "away_team"])
    all_xg.to_parquet(index_file, index=False)
    logger.info("=== xG total: %d meciuri salvate in %s ===", len(all_xg), index_file)
    return all_xg


def merge_xg_into_df(
    df: pd.DataFrame,
    xg_df: pd.DataFrame,
    xg_weight: float = 0.7,
) -> pd.DataFrame:
    """Ataseza coloanele home_xg / away_xg la DataFrame-ul de antrenament.

    Matching fuzzy — incearca in ordinea urmatoare pana gaseste:
      1. (date, home, away)  — exact
      2. (date, away, home)  — echipe inversate (turnee neutre: StatsBomb vs martj42 difera)
      3. (date+1, home, away) — offset UTC vs local (Copa America in SUA)
      4. (date+1, away, home) — offset + invers
      5. (date-1, home, away) — simetric
      6. (date-1, away, home)

    Cand echipele sunt inversate, home_xg si away_xg se inverseaza corespunzator.

    Returneaza df cu coloanele noi:
      home_xg  — xG statsbomb (NaN daca nu avem)
      away_xg
      has_xg   — bool flag
    """
    if xg_df.empty:
        df["home_xg"] = float("nan")
        df["away_xg"] = float("nan")
        df["has_xg"]  = False
        return df

    from datetime import timedelta

    xg_df = xg_df.copy()
    xg_df["date_dt"] = pd.to_datetime(xg_df["date"]).dt.date

    # Construiesc doua lookup-uri: exact si inversat
    # Valoare: (home_xg, away_xg)
    lookup_exact:    dict[tuple, tuple] = {}
    lookup_swapped:  dict[tuple, tuple] = {}
    for _, r in xg_df.iterrows():
        d, h, a = r["date_dt"], r["home_team"], r["away_team"]
        hxg, axg = r["home_xg"], r["away_xg"]
        lookup_exact[(d, h, a)]   = (hxg, axg)
        lookup_swapped[(d, a, h)] = (axg, hxg)  # inversat, cu xG corespunzator

    _one_day = timedelta(days=1)

    def _fuzzy_lookup(row):
        d, h, a = row["date_dt"], row["home_team"], row["away_team"]
        for delta in (0, 1, -1):
            dd = d + _one_day * delta
            v = lookup_exact.get((dd, h, a)) or lookup_swapped.get((dd, h, a))
            if v:
                return v
        return None

    pairs = df.apply(_fuzzy_lookup, axis=1)
    df = df.copy()
    df["home_xg"] = pairs.apply(lambda x: x[0] if x else float("nan"))
    df["away_xg"] = pairs.apply(lambda x: x[1] if x else float("nan"))
    df["has_xg"]  = df["home_xg"].notna()

    n_matched = int(df["has_xg"].sum())
    logger.info("xG merge: %d / %d meciuri matched (fuzzy).", n_matched, len(df))
    return df


def coverage_report(df: pd.DataFrame) -> dict:
    """Raport de acoperire xG pe fereastra de antrenament."""
    total = len(df)
    has_xg = int(df["has_xg"].sum()) if "has_xg" in df.columns else 0
    pct = 100.0 * has_xg / total if total > 0 else 0.0

    by_comp: dict[str, int] = {}
    if "has_xg" in df.columns and "w_comp" in df.columns:
        # weighted coverage (meciuri de mare importanta)
        w_total  = float(df["weight"].sum())
        w_xg     = float(df.loc[df["has_xg"], "weight"].sum())
        w_pct    = 100.0 * w_xg / w_total if w_total > 0 else 0.0
    else:
        w_pct = 0.0

    report = {
        "total_matches":  total,
        "matches_with_xg": has_xg,
        "raw_coverage_pct": round(pct, 2),
        "weighted_coverage_pct": round(w_pct, 2),
    }
    return report
