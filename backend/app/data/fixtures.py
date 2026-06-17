"""
FIFA World Cup 2026 — complete fixture calendar (104 matches).

Each fixture dict:
  match_id  str         unique ID (e.g. "A1", "R32-01", "FINAL")
  date      date        match date (venue local date)
  time      str         kick-off time, approximate ET (HH:MM)
  home_team str         first team / "TBD"
  away_team str         second team / "TBD"
  group     str | None
  stage     str         "Group Stage" | "Round of 32" | … | "Final"
  matchday  int | None  1-3 for group stage
  stadium   str
  city      str

Round-robin pattern (FIFA WC 2026 confirmed from real schedule):
  MD1 match1: seed1 vs seed4
  MD1 match2: seed3 vs seed2
  MD2 match1: seed2 vs seed4
  MD2 match2: seed1 vs seed3
  MD3 match1: seed2 vs seed1  ← simultaneous
  MD3 match2: seed4 vs seed3  ← simultaneous

GROUPS list order: [seed1, seed2, seed3, seed4]
"""

from __future__ import annotations

from datetime import date

from app.data.tournament_config import GROUPS

# ---------------------------------------------------------------------------
# Per-group schedule: (matchday, home_idx, away_idx, date, time, stadium, city)
# Indices reference positions in GROUPS[group] = [seed1, seed2, seed3, seed4]
# Times are approximate ET (Eastern Time, US)
# ---------------------------------------------------------------------------
_GSCHED: dict[str, list[tuple]] = {
    "A": [  # Mexico, Czechia, Korea Republic, South Africa
        (1, 0, 3, date(2026, 6, 11), "15:00", "Estadio Azteca",        "Mexico City"),
        (1, 2, 1, date(2026, 6, 11), "22:00", "Estadio Akron",          "Guadalajara"),
        (2, 1, 3, date(2026, 6, 18), "12:00", "Mercedes-Benz Stadium",  "Atlanta"),
        (2, 0, 2, date(2026, 6, 18), "21:00", "Estadio Akron",          "Guadalajara"),
        (3, 1, 0, date(2026, 6, 24), "21:00", "Estadio Azteca",         "Mexico City"),
        (3, 3, 2, date(2026, 6, 24), "21:00", "Estadio BBVA",           "Monterrey"),
    ],
    "B": [  # Canada, Switzerland, Qatar, Bosnia and Herzegovina
        (1, 0, 3, date(2026, 6, 12), "15:00", "BMO Field",       "Toronto"),
        (1, 2, 1, date(2026, 6, 13), "15:00", "Levi's Stadium",  "Santa Clara"),
        (2, 1, 3, date(2026, 6, 18), "15:00", "SoFi Stadium",    "Los Angeles"),
        (2, 0, 2, date(2026, 6, 18), "18:00", "BC Place",        "Vancouver"),
        (3, 1, 0, date(2026, 6, 24), "15:00", "BC Place",        "Vancouver"),
        (3, 3, 2, date(2026, 6, 24), "15:00", "Lumen Field",     "Seattle"),
    ],
    "C": [  # Brazil, Scotland, Haiti, Morocco
        (1, 0, 3, date(2026, 6, 13), "18:00", "MetLife Stadium",         "East Rutherford"),
        (1, 2, 1, date(2026, 6, 13), "21:00", "Gillette Stadium",        "Foxborough"),
        (2, 1, 3, date(2026, 6, 19), "18:00", "Gillette Stadium",        "Foxborough"),
        (2, 0, 2, date(2026, 6, 19), "21:00", "Lincoln Financial Field", "Philadelphia"),
        (3, 1, 0, date(2026, 6, 24), "18:00", "Hard Rock Stadium",       "Miami Gardens"),
        (3, 3, 2, date(2026, 6, 24), "18:00", "Mercedes-Benz Stadium",   "Atlanta"),
    ],
    "D": [  # United States, Türkiye, Australia, Paraguay
        (1, 0, 3, date(2026, 6, 12), "21:00", "SoFi Stadium",  "Los Angeles"),
        (1, 2, 1, date(2026, 6, 13), "00:00", "BC Place",       "Vancouver"),
        (2, 1, 3, date(2026, 6, 19), "00:00", "Levi's Stadium", "Santa Clara"),
        (2, 0, 2, date(2026, 6, 19), "15:00", "Lumen Field",    "Seattle"),
        (3, 1, 0, date(2026, 6, 25), "22:00", "SoFi Stadium",  "Los Angeles"),
        (3, 3, 2, date(2026, 6, 25), "22:00", "Levi's Stadium", "Santa Clara"),
    ],
    "E": [  # Germany, Ecuador, Côte d'Ivoire, Curaçao
        (1, 0, 3, date(2026, 6, 14), "13:00", "NRG Stadium",            "Houston"),
        (1, 2, 1, date(2026, 6, 14), "19:00", "Lincoln Financial Field", "Philadelphia"),
        (2, 1, 3, date(2026, 6, 20), "20:00", "Arrowhead Stadium",       "Kansas City"),
        (2, 0, 2, date(2026, 6, 20), "16:00", "BMO Field",               "Toronto"),
        (3, 1, 0, date(2026, 6, 25), "16:00", "MetLife Stadium",         "East Rutherford"),
        (3, 3, 2, date(2026, 6, 25), "16:00", "Lincoln Financial Field", "Philadelphia"),
    ],
    "F": [  # Netherlands, Tunisia, Sweden, Japan
        (1, 0, 3, date(2026, 6, 14), "16:00", "AT&T Stadium", "Arlington"),
        (1, 2, 1, date(2026, 6, 14), "22:00", "Estadio BBVA", "Monterrey"),
        (2, 1, 3, date(2026, 6, 20), "00:00", "Estadio BBVA", "Monterrey"),
        (2, 0, 2, date(2026, 6, 20), "13:00", "NRG Stadium",  "Houston"),
        (3, 1, 0, date(2026, 6, 25), "19:00", "Arrowhead Stadium", "Kansas City"),
        (3, 3, 2, date(2026, 6, 25), "19:00", "AT&T Stadium", "Arlington"),
    ],
    "G": [  # Belgium, New Zealand, Iran, Egypt
        (1, 0, 3, date(2026, 6, 15), "15:00", "BC Place",     "Vancouver"),
        (1, 2, 1, date(2026, 6, 15), "21:00", "SoFi Stadium", "Los Angeles"),
        (2, 1, 3, date(2026, 6, 21), "21:00", "BC Place",     "Vancouver"),
        (2, 0, 2, date(2026, 6, 21), "15:00", "SoFi Stadium", "Los Angeles"),
        (3, 1, 0, date(2026, 6, 26), "23:00", "BC Place",     "Vancouver"),
        (3, 3, 2, date(2026, 6, 26), "23:00", "Lumen Field",  "Seattle"),
    ],
    "H": [  # Spain, Uruguay, Saudi Arabia, Cabo Verde
        (1, 0, 3, date(2026, 6, 15), "12:00", "Mercedes-Benz Stadium", "Atlanta"),
        (1, 2, 1, date(2026, 6, 15), "18:00", "Hard Rock Stadium",     "Miami Gardens"),
        (2, 1, 3, date(2026, 6, 21), "18:00", "Hard Rock Stadium",     "Miami Gardens"),
        (2, 0, 2, date(2026, 6, 21), "12:00", "Mercedes-Benz Stadium", "Atlanta"),
        (3, 1, 0, date(2026, 6, 26), "20:00", "Estadio Akron",         "Guadalajara"),
        (3, 3, 2, date(2026, 6, 26), "20:00", "NRG Stadium",           "Houston"),
    ],
    "I": [  # France, Norway, Iraq, Senegal
        (1, 0, 3, date(2026, 6, 16), "15:00", "MetLife Stadium",         "East Rutherford"),
        (1, 2, 1, date(2026, 6, 16), "18:00", "Gillette Stadium",        "Foxborough"),
        (2, 1, 3, date(2026, 6, 22), "20:00", "MetLife Stadium",         "East Rutherford"),
        (2, 0, 2, date(2026, 6, 22), "17:00", "Lincoln Financial Field", "Philadelphia"),
        (3, 1, 0, date(2026, 6, 26), "15:00", "Gillette Stadium",        "Foxborough"),
        (3, 3, 2, date(2026, 6, 26), "15:00", "BMO Field",               "Toronto"),
    ],
    "J": [  # Argentina, Jordan, Austria, Algeria
        (1, 0, 3, date(2026, 6, 16), "21:00", "Arrowhead Stadium", "Kansas City"),
        (1, 2, 1, date(2026, 6, 16), "00:00", "Levi's Stadium",    "Santa Clara"),
        (2, 1, 3, date(2026, 6, 22), "23:00", "Levi's Stadium",    "Santa Clara"),
        (2, 0, 2, date(2026, 6, 22), "13:00", "AT&T Stadium",      "Arlington"),
        (3, 1, 0, date(2026, 6, 27), "22:00", "AT&T Stadium",      "Arlington"),
        (3, 3, 2, date(2026, 6, 27), "22:00", "Arrowhead Stadium", "Kansas City"),
    ],
    "K": [  # Portugal, Colombia, Uzbekistan, Congo DR
        (1, 0, 3, date(2026, 6, 17), "13:00", "NRG Stadium",           "Houston"),
        (1, 2, 1, date(2026, 6, 17), "22:00", "Estadio Azteca",        "Mexico City"),
        (2, 1, 3, date(2026, 6, 23), "22:00", "Estadio Akron",         "Guadalajara"),
        (2, 0, 2, date(2026, 6, 23), "13:00", "NRG Stadium",           "Houston"),
        (3, 1, 0, date(2026, 6, 27), "19:30", "Hard Rock Stadium",     "Miami Gardens"),
        (3, 3, 2, date(2026, 6, 27), "19:30", "Mercedes-Benz Stadium", "Atlanta"),
    ],
    "L": [  # England, Panama, Ghana, Croatia
        (1, 0, 3, date(2026, 6, 17), "16:00", "AT&T Stadium",          "Arlington"),
        (1, 2, 1, date(2026, 6, 17), "19:00", "BMO Field",             "Toronto"),
        (2, 1, 3, date(2026, 6, 23), "19:00", "BMO Field",             "Toronto"),
        (2, 0, 2, date(2026, 6, 23), "16:00", "Gillette Stadium",      "Foxborough"),
        (3, 1, 0, date(2026, 6, 27), "17:00", "MetLife Stadium",       "East Rutherford"),
        (3, 3, 2, date(2026, 6, 27), "17:00", "Lincoln Financial Field", "Philadelphia"),
    ],
}


def _group_fixtures() -> list[dict]:
    """Generate all 72 group-stage fixtures from the verified real schedule."""
    fixtures: list[dict] = []
    for g, sched in _GSCHED.items():
        teams = GROUPS[g]
        for idx, (md, hi, ai, dt, kick_off, stadium, city) in enumerate(sched, start=1):
            fixtures.append({
                "match_id":  f"{g}{idx}",
                "date":      dt,
                "time":      kick_off,
                "home_team": teams[hi],
                "away_team": teams[ai],
                "group":     g,
                "stage":     "Group Stage",
                "matchday":  md,
                "stadium":   stadium,
                "city":      city,
            })
    return fixtures


# ---------------------------------------------------------------------------
# Knockout stage — dates from official FIFA schedule
# Round of 32: June 28–July 3 | R16: July 4–7 | QF: July 9–11
# SF: July 14–15 | 3rd place: July 18 | Final: July 19
# ---------------------------------------------------------------------------
_KNOCKOUT: list[dict] = [
    # --- Round of 32 (June 28 – July 3) ---
    {"match_id": "R32-01", "date": date(2026, 6, 28), "time": "15:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "SoFi Stadium",           "city": "Los Angeles"},
    {"match_id": "R32-02", "date": date(2026, 6, 29), "time": "16:30", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "Gillette Stadium",        "city": "Foxborough"},
    {"match_id": "R32-03", "date": date(2026, 6, 29), "time": "20:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "Estadio BBVA",            "city": "Monterrey"},
    {"match_id": "R32-04", "date": date(2026, 6, 29), "time": "13:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "NRG Stadium",             "city": "Houston"},
    {"match_id": "R32-05", "date": date(2026, 6, 30), "time": "17:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "MetLife Stadium",         "city": "East Rutherford"},
    {"match_id": "R32-06", "date": date(2026, 6, 30), "time": "13:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "AT&T Stadium",            "city": "Arlington"},
    {"match_id": "R32-07", "date": date(2026, 6, 30), "time": "20:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "Estadio Azteca",          "city": "Mexico City"},
    {"match_id": "R32-08", "date": date(2026, 7,  1), "time": "12:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "Mercedes-Benz Stadium",   "city": "Atlanta"},
    {"match_id": "R32-09", "date": date(2026, 7,  1), "time": "15:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "Levi's Stadium",          "city": "Santa Clara"},
    {"match_id": "R32-10", "date": date(2026, 7,  1), "time": "16:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "Lumen Field",             "city": "Seattle"},
    {"match_id": "R32-11", "date": date(2026, 7,  2), "time": "19:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "BMO Field",               "city": "Toronto"},
    {"match_id": "R32-12", "date": date(2026, 7,  2), "time": "15:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "SoFi Stadium",            "city": "Los Angeles"},
    {"match_id": "R32-13", "date": date(2026, 7,  2), "time": "23:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "BC Place",                "city": "Vancouver"},
    {"match_id": "R32-14", "date": date(2026, 7,  3), "time": "18:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "Hard Rock Stadium",       "city": "Miami Gardens"},
    {"match_id": "R32-15", "date": date(2026, 7,  3), "time": "21:30", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "Arrowhead Stadium",       "city": "Kansas City"},
    {"match_id": "R32-16", "date": date(2026, 7,  3), "time": "14:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 32", "matchday": None, "stadium": "AT&T Stadium",            "city": "Arlington"},
    # --- Round of 16 (July 4–7) ---
    {"match_id": "R16-1",  "date": date(2026, 7,  4), "time": "17:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 16", "matchday": None, "stadium": "Lincoln Financial Field", "city": "Philadelphia"},
    {"match_id": "R16-2",  "date": date(2026, 7,  4), "time": "13:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 16", "matchday": None, "stadium": "NRG Stadium",             "city": "Houston"},
    {"match_id": "R16-3",  "date": date(2026, 7,  5), "time": "16:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 16", "matchday": None, "stadium": "MetLife Stadium",         "city": "East Rutherford"},
    {"match_id": "R16-4",  "date": date(2026, 7,  5), "time": "20:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 16", "matchday": None, "stadium": "Estadio Azteca",          "city": "Mexico City"},
    {"match_id": "R16-5",  "date": date(2026, 7,  6), "time": "15:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 16", "matchday": None, "stadium": "AT&T Stadium",            "city": "Arlington"},
    {"match_id": "R16-6",  "date": date(2026, 7,  6), "time": "20:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 16", "matchday": None, "stadium": "Lumen Field",             "city": "Seattle"},
    {"match_id": "R16-7",  "date": date(2026, 7,  7), "time": "12:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 16", "matchday": None, "stadium": "Mercedes-Benz Stadium",   "city": "Atlanta"},
    {"match_id": "R16-8",  "date": date(2026, 7,  7), "time": "16:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Round of 16", "matchday": None, "stadium": "BC Place",                "city": "Vancouver"},
    # --- Quarter-Finals (July 9–11) ---
    {"match_id": "QF-1",   "date": date(2026, 7,  9), "time": "16:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Quarter-Finals", "matchday": None, "stadium": "Gillette Stadium",     "city": "Foxborough"},
    {"match_id": "QF-2",   "date": date(2026, 7, 10), "time": "15:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Quarter-Finals", "matchday": None, "stadium": "SoFi Stadium",         "city": "Los Angeles"},
    {"match_id": "QF-3",   "date": date(2026, 7, 11), "time": "17:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Quarter-Finals", "matchday": None, "stadium": "Hard Rock Stadium",    "city": "Miami Gardens"},
    {"match_id": "QF-4",   "date": date(2026, 7, 11), "time": "21:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Quarter-Finals", "matchday": None, "stadium": "Arrowhead Stadium",    "city": "Kansas City"},
    # --- Semi-Finals (July 14–15) ---
    {"match_id": "SF-1",   "date": date(2026, 7, 14), "time": "15:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Semi-Finals",    "matchday": None, "stadium": "AT&T Stadium",         "city": "Arlington"},
    {"match_id": "SF-2",   "date": date(2026, 7, 15), "time": "15:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Semi-Finals",    "matchday": None, "stadium": "Mercedes-Benz Stadium", "city": "Atlanta"},
    # --- Third Place & Final ---
    {"match_id": "3RD",    "date": date(2026, 7, 18), "time": "17:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Third Place",    "matchday": None, "stadium": "Hard Rock Stadium",    "city": "Miami Gardens"},
    {"match_id": "FINAL",  "date": date(2026, 7, 19), "time": "15:00", "home_team": "TBD", "away_team": "TBD", "group": None, "stage": "Final",          "matchday": None, "stadium": "MetLife Stadium",      "city": "East Rutherford"},
]

FIXTURES: list[dict] = _group_fixtures() + _KNOCKOUT

# O(1) lookup by match_id
FIXTURES_BY_ID: dict[str, dict] = {f["match_id"]: f for f in FIXTURES}
