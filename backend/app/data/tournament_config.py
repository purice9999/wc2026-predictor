"""
FIFA World Cup 2026 — tournament configuration.
Edit this file to update group assignments, bracket structure, or model weights.
"""

from __future__ import annotations

GROUPS: dict[str, list[str]] = {
    # Order: [seed1, seed2, seed3, seed4] — determines round-robin matchups in fixtures.py
    "A": ["Mexico",        "Czechia",                "Korea Republic", "South Africa"],
    "B": ["Canada",        "Switzerland",            "Qatar",          "Bosnia and Herzegovina"],
    "C": ["Brazil",        "Scotland",               "Haiti",          "Morocco"],
    "D": ["United States", "Türkiye",                "Australia",      "Paraguay"],
    "E": ["Germany",       "Ecuador",                "Côte d'Ivoire",  "Curaçao"],
    "F": ["Netherlands",   "Tunisia",                "Sweden",         "Japan"],
    "G": ["Belgium",       "New Zealand",            "Iran",           "Egypt"],
    "H": ["Spain",         "Uruguay",                "Saudi Arabia",   "Cabo Verde"],
    "I": ["France",        "Norway",                 "Iraq",           "Senegal"],
    "J": ["Argentina",     "Jordan",                 "Austria",        "Algeria"],
    "K": ["Portugal",      "Colombia",               "Uzbekistan",     "Congo DR"],
    "L": ["England",       "Panama",                 "Ghana",          "Croatia"],
}

TOURNAMENT_TEAMS: list[str] = [t for teams in GROUPS.values() for t in teams]

TEAM_NAME_MAPPING: dict[str, str] = {
    "South Korea": "Korea Republic",
    "Turkey": "Türkiye",
    "Ivory Coast": "Côte d'Ivoire",
    "DR Congo": "Congo DR",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Cape Verde": "Cabo Verde",
    "Curacao": "Curaçao",
    "Czech Republic": "Czechia",
    "United States": "United States",
}

# ---------------------------------------------------------------------------
# Competition weights — higher = more influence on model
# Friendlies are given low weight to reduce noise; competitive matches dominate
# ---------------------------------------------------------------------------
COMPETITION_WEIGHTS: dict[str, float] = {
    "FIFA World Cup": 5.0,
    "FIFA World Cup qualification": 4.0,
    "UEFA Euro": 4.0,
    "UEFA Euro qualification": 3.0,
    "Copa América": 4.0,
    "Copa América qualification": 2.5,
    "Africa Cup of Nations": 3.5,
    "Africa Cup of Nations qualification": 2.5,
    "AFC Asian Cup": 3.5,
    "AFC Asian Cup qualification": 2.5,
    "CONCACAF Gold Cup": 3.0,
    "CONCACAF Nations League": 2.5,
    "CONCACAF Championship": 2.5,
    "UEFA Nations League": 2.5,
    "Confederations Cup": 3.0,
    "OFC Nations Cup": 2.5,
    "CONMEBOL–UEFA Cup of Champions": 3.0,
    "Friendly": 0.4,         # heavily discounted — reduce noise
}
DEFAULT_COMPETITION_WEIGHT: float = 1.5

# Faster decay → more weight on recent form (half-life ≈ 8.7 months)
TIME_DECAY_RATE: float = 0.00275
TRAINING_YEARS: int = 6    # wider window; decay handles the rest

# Reduced shrinkage → more differentiation between strong and weak teams
SHRINKAGE_BASE: float = 1.2
SHRINKAGE_BONUS: float = 20.0
SHRINKAGE_MIN_WEIGHT: float = 5.0

SHOTS_CONVERSION_RATE: float = 0.30
MAX_GOALS: int = 10
N_SIMULATIONS: int = 10_000

BRACKET_SECTIONS: dict[str, list[str]] = {
    "S1": ["A", "B", "C"],
    "S2": ["D", "E", "F"],
    "S3": ["G", "H", "I"],
    "S4": ["J", "K", "L"],
}

DATA_URL: str = (
    "https://raw.githubusercontent.com/martj42/international_results"
    "/master/results.csv"
)
DATA_CACHE_PATH: str = ".cache/results.csv"
MODEL_CACHE_PATH: str = ".cache/dc_model.pkl"
ELO_CACHE_PATH: str = ".cache/elo_model.pkl"

STAGES: list[str] = [
    "group_stage", "round_of_32", "round_of_16",
    "quarterfinals", "semifinals", "final", "champion",
]
STAGE_ORDER: dict[str, int] = {s: i for i, s in enumerate(STAGES)}
STAGE_LABELS: dict[str, str] = {
    "group_stage": "Group Stage",
    "round_of_32": "Round of 32",
    "round_of_16": "Round of 16",
    "quarterfinals": "Quarter-Finals",
    "semifinals": "Semi-Finals",
    "final": "Final",
    "champion": "Champion",
}
