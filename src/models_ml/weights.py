from __future__ import annotations

import pandas as pd


def compute_source_weights(
    projections_df: pd.DataFrame,
    actuals_df: pd.DataFrame,
) -> dict[str, float]:
    if projections_df.empty or actuals_df.empty:
        return {}

    merged = projections_df.merge(
        actuals_df[["player_id", "season", "fantasy_pts_ppr"]],
        on=["player_id", "season"],
        how="inner",
    )
    if merged.empty:
        return {}

    merged["abs_err"] = (merged["projected_pts"] - merged["fantasy_pts_ppr"]).abs()
    mae = merged.groupby("source", as_index=False)["abs_err"].mean()
    mae = mae[mae["abs_err"] > 0]
    if mae.empty:
        return {}

    mae["weight"] = 1.0 / mae["abs_err"]
    total = mae["weight"].sum()
    if total <= 0:
        return {}
    mae["weight"] = mae["weight"] / total
    return dict(zip(mae["source"], mae["weight"]))
