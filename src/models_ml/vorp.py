from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import settings

POSITIONS = ["QB", "RB", "WR", "TE"]


def _replacement_index(position: str, league_size: int, roster_slots: dict[str, int]) -> int:
    n_starters = league_size * int(roster_slots.get(position, 0))
    flex_slots = league_size * int(roster_slots.get("FLEX", 0))
    if position in {"RB", "WR"}:
        n_starters += int(flex_slots / 2)
    return max(n_starters + settings.REPLACEMENT_BUFFER, 1)


def calculate_vorp(
    projections_df: pd.DataFrame,
    league_size: int,
    roster_slots: dict,
    scoring_format: str,
    adp_df: pd.DataFrame,
) -> pd.DataFrame:
    if projections_df.empty:
        return pd.DataFrame(
            columns=[
                "player_id",
                "position",
                "projected_pts",
                "replacement_pts",
                "vorp",
                "pos_rank",
                "overall_rank",
                "adp",
                "adp_rank",
                "adp_delta",
                "scoring_format",
                "league_size",
            ]
        )

    output_parts: list[pd.DataFrame] = []
    for position in POSITIONS:
        pos_df = (
            projections_df[projections_df["position"] == position]
            .copy()
            .sort_values("projected_pts", ascending=False)
            .reset_index(drop=True)
        )
        if pos_df.empty:
            continue

        replacement_rank = _replacement_index(position, league_size=league_size, roster_slots=roster_slots)
        idx = min(len(pos_df), replacement_rank) - 1
        replacement_pts = float(pos_df.loc[idx, "projected_pts"])

        pos_df["replacement_pts"] = replacement_pts
        pos_df["vorp"] = pos_df["projected_pts"] - replacement_pts
        pos_df["pos_rank"] = np.arange(1, len(pos_df) + 1)
        output_parts.append(pos_df)

    if not output_parts:
        return pd.DataFrame()

    result = pd.concat(output_parts, ignore_index=True)
    result = result.sort_values("vorp", ascending=False).reset_index(drop=True)
    result["overall_rank"] = np.arange(1, len(result) + 1)

    if adp_df is not None and not adp_df.empty:
        merge_cols = [c for c in ["player_id", "adp", "adp_rank"] if c in adp_df.columns]
        result = result.merge(adp_df[merge_cols].drop_duplicates("player_id"), on="player_id", how="left")
    else:
        result["adp"] = np.nan
        result["adp_rank"] = np.nan

    result["adp_delta"] = result["adp_rank"] - result["overall_rank"]
    result["scoring_format"] = scoring_format
    result["league_size"] = league_size
    result["vorp"] = result["vorp"].astype(float)

    return result
