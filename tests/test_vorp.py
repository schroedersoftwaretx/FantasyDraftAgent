from __future__ import annotations

import numpy as np
import pandas as pd

from src.models_ml.vorp import calculate_vorp


def _make_projection_df() -> pd.DataFrame:
    rows = []
    for i in range(10):
        rows.append({"player_id": f"QB{i}", "name": f"QB Player {i}", "position": "QB", "projected_pts": 350 - i * 5})
    for i in range(20):
        rows.append({"player_id": f"RB{i}", "name": f"RB Player {i}", "position": "RB", "projected_pts": 300 - i * 4})
    for i in range(20):
        rows.append({"player_id": f"WR{i}", "name": f"WR Player {i}", "position": "WR", "projected_pts": 290 - i * 3.5})
    for i in range(10):
        rows.append({"player_id": f"TE{i}", "name": f"TE Player {i}", "position": "TE", "projected_pts": 240 - i * 4})
    return pd.DataFrame(rows)


def _make_adp_df(proj_df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player_id": proj_df["player_id"],
            "adp": np.arange(1, len(proj_df) + 1, dtype=float),
            "adp_rank": np.arange(1, len(proj_df) + 1, dtype=int),
        }
    )


def test_calculate_vorp_returns_row_per_player() -> None:
    proj_df = _make_projection_df()
    result = calculate_vorp(
        projections_df=proj_df,
        league_size=4,
        roster_slots={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1},
        scoring_format="ppr",
        adp_df=_make_adp_df(proj_df),
    )
    assert len(result) == len(proj_df)


def test_replacement_points_match_threshold_player() -> None:
    proj_df = _make_projection_df()
    result = calculate_vorp(
        projections_df=proj_df,
        league_size=4,
        roster_slots={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1},
        scoring_format="ppr",
        adp_df=_make_adp_df(proj_df),
    )
    qb_sorted = proj_df[proj_df["position"] == "QB"].sort_values("projected_pts", ascending=False).reset_index(drop=True)
    # league_size*QB slots + replacement buffer(2) = 6th QB in this synthetic test.
    expected_qb_replacement = qb_sorted.loc[5, "projected_pts"]
    actual_qb_replacement = result[result["position"] == "QB"]["replacement_pts"].iloc[0]
    assert actual_qb_replacement == expected_qb_replacement


def test_vorp_values_are_finite() -> None:
    proj_df = _make_projection_df()
    result = calculate_vorp(
        projections_df=proj_df,
        league_size=4,
        roster_slots={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1},
        scoring_format="ppr",
        adp_df=_make_adp_df(proj_df),
    )
    assert np.isfinite(result["vorp"]).all()


def test_overall_rank_unique_and_starts_at_one() -> None:
    proj_df = _make_projection_df()
    result = calculate_vorp(
        projections_df=proj_df,
        league_size=4,
        roster_slots={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1},
        scoring_format="ppr",
        adp_df=_make_adp_df(proj_df),
    )
    assert result["overall_rank"].min() == 1
    assert result["overall_rank"].is_unique
