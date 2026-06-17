"""
Store de predicții înghețate (anti-cheating).

Principiu: o predicție salvată nu se mai suprascrie niciodată.
Predicția trebuie să existe ÎNAINTE de jucarea meciului.

La startup, backend-ul generează predicții pentru toate meciurile cu echipe cunoscute
(group stage completat + knockout imediat următor).
La /predict/{id}, predicția se îngheță automat dacă nu există deja.

Fișier: .cache/frozen_predictions.json
Format: {match_id: {home_team, away_team, date, stage, frozen_at, prob_home,
                    prob_draw, prob_away, predicted_winner, most_likely_score,
                    btts_yes, over_2_5}}
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FrozenPredictionService:
    """Thread-safe store de predicții înghețate pe disc."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
                logger.info("FrozenPredictions: %d înghețate din %s", len(self._data), self._path)
            except Exception as exc:
                logger.warning("Frozen predictions load failed (%s); start fresh.", exc)
                self._data = {}

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def get(self, match_id: str) -> Optional[dict]:
        return self._data.get(match_id)

    def has(self, match_id: str) -> bool:
        return match_id in self._data

    def freeze(self, match_id: str, fixture: dict, prediction: dict) -> bool:
        """
        Îngheață predicția pentru un meci. Returnează True dacă s-a salvat,
        False dacă predicția era deja înghețată (nu se suprascrie).
        """
        with self._lock:
            if match_id in self._data:
                return False  # deja înghețată

            ph = prediction.get("prob_home", 0.0)
            pd = prediction.get("prob_draw", 0.0)
            pa = prediction.get("prob_away", 0.0)
            # Predicted winner = outcome cu probabilitate maximă
            probs = {"home": ph, "draw": pd, "away": pa}
            predicted_winner = max(probs, key=probs.get)

            self._data[match_id] = {
                "match_id": match_id,
                "home_team": fixture.get("home_team"),
                "away_team": fixture.get("away_team"),
                "date": str(fixture.get("date", "")),
                "stage": fixture.get("stage", ""),
                "group": fixture.get("group"),
                "frozen_at": datetime.now(timezone.utc).isoformat(),
                "model_used": prediction.get("model_used", ""),
                "prob_home": round(ph, 4),
                "prob_draw": round(pd, 4),
                "prob_away": round(pa, 4),
                "predicted_winner": predicted_winner,
                "most_likely_score": prediction.get("most_likely_score", {}),
                "btts_yes": round(prediction.get("btts_yes", 0.0), 4),
                "over_2_5": round(prediction.get("over_2_5", 0.0), 4),
                "xg_home": prediction.get("xg_home"),
                "xg_away": prediction.get("xg_away"),
            }
            self._save()
            return True

    def all(self) -> dict[str, dict]:
        return dict(self._data)

    def count(self) -> int:
        return len(self._data)
