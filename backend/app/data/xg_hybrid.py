"""Sub-faza B: semnal hibrid xG + goluri pentru Dixon-Coles.

Pentru meciurile cu xG real (StatsBomb), tinta de antrenare DC devine:
    home_g_dc = blend * home_xg + (1 - blend) * home_score

Meciurile fara xG raman neschimbate (home_g_dc = home_score).

Cand use_xg_hybrid=False, aceasta functie nu e apelata si DC primeste
exact aceleasi date ca inainte — comportament identic cu baseline-ul.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def apply_xg_hybrid(
    df: pd.DataFrame,
    xg_df: pd.DataFrame,
    blend_weight: float = 0.7,
) -> pd.DataFrame:
    """Adauga coloanele home_g_dc / away_g_dc la DataFrame-ul de antrenament.

    Parametri
    ----------
    df           : DataFrame antrenament (preprocesat, din preprocess_data)
    xg_df        : DataFrame xG (din fetch_all_xg, 250 meciuri StatsBomb)
    blend_weight : ponderea xG in amestec (0.7 = 70% xG + 30% goluri)

    Returneaza df cu coloanele noi:
      home_g_dc  — tinta efectiva pentru Poisson log-likelihood in DC
      away_g_dc
      home_xg    — xG real StatsBomb (NaN daca nu avem)
      away_xg
      has_xg     — flag bool
    """
    from app.data.xg_fetcher import merge_xg_into_df

    df = merge_xg_into_df(df, xg_df, xg_weight=blend_weight)

    w = blend_weight
    w_g = 1.0 - w

    df["home_g_dc"] = np.where(
        df["has_xg"],
        w * df["home_xg"] + w_g * df["home_score"].astype(float),
        df["home_score"].astype(float),
    )
    df["away_g_dc"] = np.where(
        df["has_xg"],
        w * df["away_xg"] + w_g * df["away_score"].astype(float),
        df["away_score"].astype(float),
    )

    n_hybrid = int(df["has_xg"].sum())
    logger.info(
        "xG hybrid aplicat: %d meciuri cu blend %.0f%%xG + %.0f%%goluri  "
        "(%d raman 100%% goluri).",
        n_hybrid, w * 100, w_g * 100, len(df) - n_hybrid,
    )
    return df
