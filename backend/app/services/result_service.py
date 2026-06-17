from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class ResultService:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}
        if self._path.exists():
            try:
                with open(self._path, encoding="utf-8") as fh:
                    self._data = json.load(fh)
            except Exception:
                self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    def record(
        self,
        match_id: str,
        home_team: str,
        away_team: str,
        stage: str,
        home_score: int,
        away_score: int,
        prediction: dict | None,
    ) -> dict:
        actual = "home" if home_score > away_score else ("draw" if home_score == away_score else "away")
        prob_home = prob_draw = prob_away = 0.0
        predicted = None
        correct = None
        if prediction:
            prob_home = float(prediction.get("prob_home", 0))
            prob_draw = float(prediction.get("prob_draw", 0))
            prob_away = float(prediction.get("prob_away", 0))
            if prob_home >= prob_draw and prob_home >= prob_away:
                predicted = "home"
            elif prob_away >= prob_home and prob_away >= prob_draw:
                predicted = "away"
            else:
                predicted = "draw"
            correct = actual == predicted
        entry = {
            "match_id": match_id,
            "home_team": home_team,
            "away_team": away_team,
            "stage": stage,
            "home_score": home_score,
            "away_score": away_score,
            "actual_winner": actual,
            "predicted_winner": predicted,
            "correct": correct,
            "prob_home": round(prob_home, 4),
            "prob_draw": round(prob_draw, 4),
            "prob_away": round(prob_away, 4),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._data[match_id] = entry
            self._save()
        return entry

    def get(self, match_id: str) -> dict | None:
        return self._data.get(match_id)

    def all(self) -> list[dict]:
        return sorted(self._data.values(), key=lambda x: x["recorded_at"])

    def delete(self, match_id: str) -> bool:
        with self._lock:
            if match_id in self._data:
                del self._data[match_id]
                self._save()
                return True
            return False

    def accuracy(self) -> dict:
        entries = [e for e in self._data.values() if e.get("correct") is not None]
        correct = sum(1 for e in entries if e["correct"])
        return {
            "total": len(self._data),
            "with_prediction": len(entries),
            "correct": correct,
            "accuracy": round(correct / len(entries), 4) if entries else 0.0,
        }
