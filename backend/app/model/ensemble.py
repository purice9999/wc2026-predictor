"""Ensemble predictor: Dixon-Coles + Elo + XGBoost.

Ponderile H/D/A sunt controlate prin config (w_dc / w_elo / w_xgb).
Goal markets (xG, BTTS, O/U, scoreline) vin întotdeauna 100% din Dixon-Coles,
singurul model care produce o distribuție completă de scoruri.

Configurații recomandate (din backtest 2024-07-15 → 2026-06-10, 1 459 meciuri):
  dc_only (1/0/0)   → ll=0.9282  acc=58.4%  ← default curent
  50/30/20          → ll=0.9336  acc=57.8%
  40/25/35          → ll=0.9356  acc=56.8%
  30/20/50 (vechi)  → ll=0.9474  acc=55.4%

Cum schimbi varianta:
  .env (sau variabile de mediu):  W_DC=0.5  W_ELO=0.3  W_XGB=0.2
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.models.calibration import CalibratorType
from app.models.dixon_coles import DixonColesModel
from app.models.elo import EloModel

if TYPE_CHECKING:
    from app.models.xgboost_model import XGBoostPredictor

logger = logging.getLogger(__name__)

# Presets utile pentru .env / experimente
PRESET_DC_ONLY   = (1.00, 0.00, 0.00)
PRESET_50_30_20  = (0.50, 0.30, 0.20)
PRESET_40_25_35  = (0.40, 0.25, 0.35)
PRESET_33_33_33  = (0.33, 0.33, 0.33)
PRESET_OLD       = (0.30, 0.20, 0.50)


class EnsembleModel:
    """Predictor cu blend configurabil DC + Elo + XGB."""

    def __init__(
        self,
        dc: DixonColesModel,
        elo: EloModel,
        w_dc: float = 1.0,
        w_elo: float = 0.0,
        w_xgb: float = 0.0,
        xgb: "XGBoostPredictor | None" = None,
        calibrator: CalibratorType = None,
    ) -> None:
        total = w_dc + w_elo + w_xgb
        if total <= 0:
            raise ValueError("Cel puțin o pondere trebuie să fie > 0.")
        self.dc   = dc
        self.elo  = elo
        self.xgb  = xgb
        self.w_dc  = w_dc  / total
        self.w_elo = w_elo / total
        self.w_xgb = w_xgb / total
        self.calibrator = calibrator

        self._has_xgb = (
            w_xgb > 0
            and xgb is not None
            and getattr(xgb, "is_fitted", False)
        )
        self._dc_only = (w_elo == 0.0 and w_xgb == 0.0)
        self._calibrated = calibrator is not None and getattr(calibrator, "is_fitted", False)

        cal_suffix = f"+{type(calibrator).__name__.replace('Calibrator', '')}" if self._calibrated else ""
        if self._dc_only:
            self.model_label = f"DC{cal_suffix}"
        elif self._has_xgb:
            self.model_label = f"DC+Elo+XGB ({self.w_dc:.0%}/{self.w_elo:.0%}/{self.w_xgb:.0%}){cal_suffix}"
        else:
            self.model_label = f"DC+Elo ({self.w_dc:.0%}/{self.w_elo:.0%}){cal_suffix}"

        logger.info(
            "EnsembleModel: %s  (w_dc=%.2f  w_elo=%.2f  w_xgb=%.2f  calibrated=%s)",
            self.model_label, self.w_dc, self.w_elo, self.w_xgb, self._calibrated,
        )

    def predict(self, team1: str, team2: str, neutral: bool = True) -> dict:
        dc_r = self.dc.predict_match_full(team1, team2, neutral)

        # Fast-path: DC pur — nu apelam Elo sau XGB deloc
        if self._dc_only:
            result = {**dc_r}
            result["elo_home"] = self.elo._get_rating(team1)
            result["elo_away"] = self.elo._get_rating(team2)
            result["model_used"] = self.model_label
            self._apply_calibration(result)
            result["value_bet"]  = self._value_bet(team1, team2,
                                                    result["prob_home"], result["prob_draw"],
                                                    result["prob_away"], dc_r)
            result["explanation"] = self._explain(team1, team2, result)
            return result

        # Blend generic
        elo_r = self.elo.predict(team1, team2, neutral)

        if self._has_xgb:
            try:
                xgb_r = self.xgb.predict(team1, team2, self.dc, self.elo, neutral)
                ph = self.w_dc * dc_r["prob_home"] + self.w_elo * elo_r["prob_home"] + self.w_xgb * xgb_r["prob_home"]
                pd = self.w_dc * dc_r["prob_draw"] + self.w_elo * elo_r["prob_draw"] + self.w_xgb * xgb_r["prob_draw"]
                pa = self.w_dc * dc_r["prob_away"] + self.w_elo * elo_r["prob_away"] + self.w_xgb * xgb_r["prob_away"]
            except Exception as exc:
                logger.warning("XGB predict failed (%s); falling back to DC+Elo.", exc)
                ph, pd, pa = self._blend_two(dc_r, elo_r)
        else:
            ph, pd, pa = self._blend_two(dc_r, elo_r)

        total = ph + pd + pa
        result = {**dc_r}
        result["prob_home"]  = round(ph / total, 4)
        result["prob_draw"]  = round(pd / total, 4)
        result["prob_away"]  = round(pa / total, 4)
        result["elo_home"]   = elo_r["elo_home"]
        result["elo_away"]   = elo_r["elo_away"]
        result["model_used"] = self.model_label
        self._apply_calibration(result)
        result["value_bet"]  = self._value_bet(team1, team2,
                                               result["prob_home"], result["prob_draw"],
                                               result["prob_away"], dc_r)
        result["explanation"] = self._explain(team1, team2, result)
        return result

    def _apply_calibration(self, result: dict) -> None:
        """Aplica calibratorul la prob_home/prob_draw/prob_away, in-place."""
        if not self._calibrated:
            return
        ph, pd, pa = self.calibrator.predict_one(
            result["prob_home"], result["prob_draw"], result["prob_away"]
        )
        # Rotunjim primele doua si calculam a treia ca rest, garantand suma=1.0 exact
        ph = round(ph, 4)
        pd = round(pd, 4)
        pa = round(1.0 - ph - pd, 4)
        result["prob_home"] = ph
        result["prob_draw"] = pd
        result["prob_away"] = pa
        result["calibrated"] = True

    def _blend_two(self, dc: dict, elo: dict) -> tuple[float, float, float]:
        """Blend DC + Elo (w_xgb ignorat)."""
        scale = self.w_dc + self.w_elo
        w_d = self.w_dc / scale
        w_e = self.w_elo / scale
        return (
            w_d * dc["prob_home"] + w_e * elo["prob_home"],
            w_d * dc["prob_draw"] + w_e * elo["prob_draw"],
            w_d * dc["prob_away"] + w_e * elo["prob_away"],
        )

    @staticmethod
    def _value_bet(
        home: str, away: str,
        ph: float, pd: float, pa: float,
        dc_r: dict,
    ) -> str | None:
        markets = [
            (ph,                f"{home} Win (1)", 0.56),
            (pa,                f"{away} Win (2)", 0.56),
            (dc_r["btts_yes"],  "BTTS Yes",        0.55),
            (dc_r["over_2_5"],  "Over 2.5 Goals",  0.55),
            (dc_r["under_2_5"], "Under 2.5 Goals", 0.62),
        ]
        bets = [(p, label) for p, label, thresh in markets if p >= thresh]
        if not bets:
            return None
        best = max(bets, key=lambda x: x[0])
        return f"{best[1]} — model prob {best[0]:.0%}"

    def _explain(self, home: str, away: str, r: dict) -> str:
        ph, pa = r["prob_home"], r["prob_away"]
        ms = r["most_likely_score"]
        top_prob = r["top_scorelines"][0]["prob"] if r["top_scorelines"] else 0.0

        if ph > pa + 0.15:
            outcome = f"{home} clar favorit ({ph:.0%})"
        elif pa > ph + 0.15:
            outcome = f"{away} clar favorit ({pa:.0%})"
        elif abs(ph - pa) < 0.05:
            outcome = f"Meci echilibrat — {home} {ph:.0%} vs {away} {pa:.0%}"
        elif ph >= pa:
            outcome = f"{home} ușor favorit ({ph:.0%} vs {pa:.0%})"
        else:
            outcome = f"{away} ușor favorit ({pa:.0%} vs {ph:.0%})"

        btts = (
            "BTTS probabil"
            if r["btts_yes"] > 0.50
            else f"Poartă neviolată posibilă ({max(r['cs_home'], r['cs_away']):.0%})"
        )
        model = f"[{r['model_used']}]"

        return (
            f"{outcome}. "
            f"xG: {r['xg_home']:.2f}–{r['xg_away']:.2f}. "
            f"Scor probabil: {ms['home']}–{ms['away']} ({top_prob:.1%}). "
            f"{btts}. Peste 2.5: {r['over_2_5']:.0%}. "
            f"{model}"
        )
