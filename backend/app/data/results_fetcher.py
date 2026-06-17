"""
Trage rezultatele reale WC 2026 de la openfootball/worldcup.json.
Cache pe disc cu TTL de câteva ore; refresh manual prin POST /tracking/refresh.

Format openfootball (atât string cât și object pentru echipe):
  {"rounds": [{"matches": [
    {"date": "2026-06-11", "team1": "Mexico", "team2": "Poland",
     "score": {"ft": [2, 0]}}
  ]}]}
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

WC2026_URL = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
)
CACHE_PATH = Path(".cache/wc_real_results.json")
TTL_HOURS = 3

# Normalizare nume echipe openfootball → fixture names (cele 48 echipe WC 2026)
_OFB_NORM: dict[str, str] = {
    "usa": "United States",
    "united states": "United States",
    "us": "United States",
    "korea republic": "Korea Republic",
    "south korea": "Korea Republic",
    "korea, republic of": "Korea Republic",
    "republic of korea": "Korea Republic",
    "türkiye": "Türkiye",
    "turkey": "Türkiye",
    "côte d'ivoire": "Côte d'Ivoire",
    "ivory coast": "Côte d'Ivoire",
    "cote d'ivoire": "Côte d'Ivoire",
    "curaçao": "Curaçao",
    "curacao": "Curaçao",
    "cabo verde": "Cabo Verde",
    "cape verde": "Cabo Verde",
    "congo dr": "Congo DR",
    "dr congo": "Congo DR",
    "congo, the democratic republic": "Congo DR",
    "dem. rep. congo": "Congo DR",
    "democratic republic of congo": "Congo DR",
    "bosnia and herzegovina": "Bosnia and Herzegovina",
    "bosnia & herzegovina": "Bosnia and Herzegovina",
    "bosnia-herzegovina": "Bosnia and Herzegovina",
}

# Toate echipele WC 2026 din fixtures — pentru match by normalized name
_WC_TEAMS_LOWER: dict[str, str] = {
    t.lower(): t for t in [
        "Mexico", "Czechia", "Korea Republic", "South Africa", "Canada", "Switzerland",
        "Qatar", "Bosnia and Herzegovina", "Brazil", "Scotland", "Haiti", "Morocco",
        "United States", "Türkiye", "Australia", "Paraguay", "Germany", "Ecuador",
        "Côte d'Ivoire", "Curaçao", "Netherlands", "Tunisia", "Sweden", "Japan",
        "Belgium", "New Zealand", "Iran", "Egypt", "Spain", "Uruguay", "Saudi Arabia",
        "Cabo Verde", "France", "Norway", "Iraq", "Senegal", "Argentina", "Jordan",
        "Austria", "Algeria", "Portugal", "Colombia", "Uzbekistan", "Congo DR",
        "England", "Panama", "Ghana", "Croatia",
    ]
}


def _normalize_team(raw: str) -> Optional[str]:
    """Încearcă să normalizeze un nume de echipă openfootball la numele din fixtures."""
    if not raw:
        return None
    low = raw.strip().lower()
    # 1. Lookup direct în dict de norme specifice
    if low in _OFB_NORM:
        return _OFB_NORM[low]
    # 2. Exact match (case-insensitive) față de echipele WC 2026
    if low in _WC_TEAMS_LOWER:
        return _WC_TEAMS_LOWER[low]
    # 3. Fără accente + lowercase
    stripped = unicodedata.normalize("NFKD", low).encode("ascii", "ignore").decode()
    if stripped in _OFB_NORM:
        return _OFB_NORM[stripped]
    if stripped in _WC_TEAMS_LOWER:
        return _WC_TEAMS_LOWER[stripped]
    # 4. Fuzzy: vreun team WC conținut parțial
    for wc_low, wc_canonical in _WC_TEAMS_LOWER.items():
        if low in wc_low or wc_low in low:
            return wc_canonical
    return None


def _extract_team_name(t) -> str:
    """Extrage numele echipei dintr-un camp care poate fi string sau dict."""
    if isinstance(t, str):
        return t
    if isinstance(t, dict):
        return t.get("name") or t.get("key", "")
    return str(t)


def _parse_date(raw: str) -> Optional[date]:
    """Parsare flexibilă dată (ISO sau 'Jun 11')."""
    if not raw:
        return None
    raw = raw.strip()
    # ISO
    m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
    if m:
        return date.fromisoformat(m.group(1))
    # "Jun 11" sau "11 Jun 2026"
    for fmt in ("%b %d", "%d %b %Y", "%b %d %Y", "%d %b"):
        try:
            d = datetime.strptime(raw, fmt)
            return d.replace(year=2026).date()
        except ValueError:
            pass
    return None


def _fetch_fresh() -> dict:
    """Descarcă JSON de la openfootball și parsează meciurile cu scor."""
    logger.info("Fetching WC 2026 results from openfootball...")
    try:
        resp = requests.get(WC2026_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("openfootball fetch failed: %s", exc)
        return {"matches": [], "fetched_at": datetime.utcnow().isoformat(), "error": str(exc)}

    matches = []
    rounds = data.get("rounds") or data.get("matchdays") or []
    for rnd in rounds:
        rnd_name = rnd.get("name", "")
        for m in rnd.get("matches", []):
            score = m.get("score") or {}
            ft = score.get("ft")
            if not ft or len(ft) < 2:
                continue  # meci nejucat

            raw_t1 = _extract_team_name(m.get("team1", ""))
            raw_t2 = _extract_team_name(m.get("team2", ""))
            t1 = _normalize_team(raw_t1)
            t2 = _normalize_team(raw_t2)
            d = _parse_date(m.get("date", ""))

            if not (t1 and t2 and d):
                logger.debug("Cannot parse match: t1=%s t2=%s date=%s", raw_t1, raw_t2, m.get("date"))
                continue

            matches.append({
                "team1": t1,
                "team2": t2,
                "date": d.isoformat(),
                "home_score": int(ft[0]),
                "away_score": int(ft[1]),
                "round": rnd_name,
            })

    logger.info("openfootball: %d matches with scores parsed.", len(matches))
    return {"matches": matches, "fetched_at": datetime.utcnow().isoformat()}


def _is_stale(fetched_at_iso: str) -> bool:
    try:
        fetched = datetime.fromisoformat(fetched_at_iso)
        return (datetime.utcnow() - fetched) > timedelta(hours=TTL_HOURS)
    except Exception:
        return True


def get_real_results(force: bool = False) -> list[dict]:
    """
    Returnează lista meciurilor WC 2026 cu scoruri reale.
    Foloseşte cache pe disc; refresh dacă TTL expirat sau force=True.
    """
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not force and CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if not _is_stale(cached.get("fetched_at", "")):
                return cached.get("matches", [])
            logger.info("Results cache expired, refreshing...")
        except Exception:
            pass

    fresh = _fetch_fresh()
    CACHE_PATH.write_text(json.dumps(fresh, ensure_ascii=False, indent=2), encoding="utf-8")
    return fresh.get("matches", [])


def match_real_to_fixture(
    real_matches: list[dict],
    fixtures: dict,  # FIXTURES_BY_ID
) -> dict[str, dict]:
    """
    Asociază meciurile reale (openfootball) cu match_id-urile din fixtures.
    Returnează: {match_id: {home_score, away_score, actual_winner}}
    """
    results: dict[str, dict] = {}

    for m in real_matches:
        t1, t2 = m["team1"], m["team2"]
        d = date.fromisoformat(m["date"])

        best_id = None
        for fid, fx in fixtures.items():
            fh, fa = fx.get("home_team"), fx.get("away_team")
            fd = fx.get("date")
            if fh == "TBD" or fa == "TBD":
                continue
            # Potrivire cu ±1 zi toleranță
            date_ok = fd and abs((d - fd).days) <= 1
            teams_direct = fh == t1 and fa == t2
            teams_swapped = fh == t2 and fa == t1

            if date_ok and (teams_direct or teams_swapped):
                if teams_swapped:
                    # echipele inversate în sursă — inversăm și scorurile
                    m = {**m, "team1": t2, "team2": t1,
                         "home_score": m["away_score"], "away_score": m["home_score"]}
                best_id = fid
                break

        if not best_id:
            # A doua trecere: doar echipe (fără dată), dacă meciul e unic
            candidates = [
                fid for fid, fx in fixtures.items()
                if not (fx.get("home_team") == "TBD" or fx.get("away_team") == "TBD")
                and (
                    (fx["home_team"] == t1 and fx["away_team"] == t2) or
                    (fx["home_team"] == t2 and fx["away_team"] == t1)
                )
            ]
            if len(candidates) == 1:
                best_id = candidates[0]
                fx = fixtures[best_id]
                if fx["home_team"] == t2:  # inversate
                    m = {**m, "home_score": m["away_score"], "away_score": m["home_score"]}

        if best_id:
            hs, as_ = m["home_score"], m["away_score"]
            winner = "home" if hs > as_ else ("draw" if hs == as_ else "away")
            results[best_id] = {
                "home_score": hs,
                "away_score": as_,
                "actual_winner": winner,
            }

    logger.info("Matched %d/%d real results to fixtures.", len(results), len(real_matches))
    return results
