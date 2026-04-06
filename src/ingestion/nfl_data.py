from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.nfl_team import NFLTeam
from src.models.player import Player
from src.models.position import Position
from src.models.season_stats import SeasonStats

logger = logging.getLogger(__name__)
VALID_POSITIONS = {"QB", "RB", "WR", "TE"}


def load_historical_stats(seasons: list[int]) -> pd.DataFrame:
    import nfl_data_py as nfl

    weekly_parts: list[pd.DataFrame] = []
    seasonal_parts: list[pd.DataFrame] = []
    for season in seasons:
        try:
            weekly_parts.append(nfl.import_weekly_data([season]))
            seasonal_parts.append(nfl.import_seasonal_data([season]))
        except Exception as exc:
            logger.warning("Skipping season %s due to nfl_data_py fetch error: %s", season, exc)

    if not weekly_parts:
        return pd.DataFrame()

    weekly = pd.concat(weekly_parts, ignore_index=True).copy()
    seasonal = pd.concat(seasonal_parts, ignore_index=True).copy() if seasonal_parts else pd.DataFrame()
    weekly_cols = set(weekly.columns)

    if "position" in weekly.columns:
        weekly = weekly[weekly["position"].isin(VALID_POSITIONS)]
    if "position" in seasonal.columns:
        seasonal = seasonal[seasonal["position"].isin(VALID_POSITIONS)]

    if weekly.empty:
        return pd.DataFrame()

    for col in [
        "snap_pct",
        "fantasy_points_ppr",
        "fantasy_points",
        "targets",
        "carries",
        "air_yards_share",
        "target_share",
    ]:
        if col not in weekly.columns:
            weekly[col] = 0.0

    if "snap_pct" in weekly_cols:
        weekly["played_week"] = weekly["week"].where(weekly["snap_pct"].fillna(0) > 0)
        games_agg = ("played_week", "nunique")
    else:
        games_agg = ("week", "nunique")

    grouped = weekly.groupby(["player_id", "season"], as_index=False).agg(
        games_played=games_agg,
        fantasy_pts_ppr=("fantasy_points_ppr", "sum"),
        fantasy_pts_std=("fantasy_points", "sum"),
        targets=("targets", "sum"),
        carries=("carries", "sum"),
        air_yards=("air_yards_share", "mean"),
        snap_pct=("snap_pct", "mean"),
        target_share=("target_share", "mean"),
    )
    grouped = grouped.fillna(0.0)
    grouped["pts_per_game"] = grouped["fantasy_pts_ppr"] / grouped["games_played"].replace(0, pd.NA)
    grouped["pts_per_game"] = grouped["pts_per_game"].fillna(0.0)

    weekly_meta_cols = [
        c for c in ["player_id", "player_display_name", "player_name", "position", "recent_team"] if c in weekly.columns
    ]
    weekly_order_cols = [c for c in ["season", "week"] if c in weekly.columns]
    weekly_meta = weekly[weekly_meta_cols + weekly_order_cols].copy()
    if weekly_order_cols:
        weekly_meta = weekly_meta.sort_values(weekly_order_cols)
    else:
        weekly_meta = weekly_meta.sort_values("player_id")
    player_meta = weekly_meta.drop_duplicates("player_id", keep="last")[weekly_meta_cols]

    seasonal_meta_cols = [c for c in ["player_id", "status", "age"] if c in seasonal.columns]
    if seasonal_meta_cols:
        seasonal_order_cols = [c for c in ["season"] if c in seasonal.columns]
        seasonal_meta = seasonal[seasonal_meta_cols + seasonal_order_cols].copy()
        if seasonal_order_cols:
            seasonal_meta = seasonal_meta.sort_values(seasonal_order_cols)
        else:
            seasonal_meta = seasonal_meta.sort_values("player_id")
        seasonal_meta = seasonal_meta.drop_duplicates("player_id", keep="last")[seasonal_meta_cols]
        player_meta = player_meta.merge(seasonal_meta, on="player_id", how="left")
    if "player_display_name" in player_meta.columns:
        player_meta = player_meta.rename(columns={"player_display_name": "name"})
    elif "player_name" in player_meta.columns:
        player_meta = player_meta.rename(columns={"player_name": "name"})
    if "recent_team" in player_meta.columns:
        player_meta = player_meta.rename(columns={"recent_team": "nfl_team"})

    merged = grouped.merge(player_meta, on="player_id", how="left")
    if "position" in merged.columns:
        merged = merged[merged["position"].isin(VALID_POSITIONS)]

    required_columns = [
        "player_id",
        "name",
        "position",
        "nfl_team",
        "age",
        "status",
        "season",
        "games_played",
        "fantasy_pts_ppr",
        "fantasy_pts_std",
        "pts_per_game",
        "targets",
        "carries",
        "air_yards",
        "snap_pct",
        "target_share",
    ]
    for col in required_columns:
        if col not in merged.columns:
            merged[col] = None

    return merged[required_columns].reset_index(drop=True)


def upsert_players_and_stats(df: pd.DataFrame, db_session: Session) -> None:
    if df.empty:
        return

    players_df = (
        df[["player_id", "name", "position", "nfl_team", "age", "status"]]
        .dropna(subset=["player_id", "name", "position"])
        .drop_duplicates("player_id")
    )

    # Ensure dimension rows exist before player upserts.
    for pos in sorted(set(players_df["position"].dropna().tolist())):
        if pos not in VALID_POSITIONS:
            continue
        if db_session.get(Position, pos) is None:
            db_session.add(Position(code=pos, name=pos))

    for team in sorted(set(players_df["nfl_team"].dropna().tolist())):
        team_code = str(team).strip().upper()
        if not team_code:
            continue
        if db_session.get(NFLTeam, team_code) is None:
            db_session.add(NFLTeam(team_code=team_code))

    for row in players_df.to_dict(orient="records"):
        player = db_session.get(Player, row["player_id"])
        if player is None:
            row["position"] = str(row["position"]).strip().upper()
            row["nfl_team"] = str(row["nfl_team"]).strip().upper() if pd.notna(row.get("nfl_team")) else None
            player = Player(**row)
            db_session.add(player)
        else:
            player.name = row["name"]
            player.position = str(row["position"]).strip().upper()
            player.nfl_team = str(row["nfl_team"]).strip().upper() if pd.notna(row.get("nfl_team")) else None
            player.age = int(row["age"]) if row.get("age") is not None and pd.notna(row["age"]) else None
            player.status = row.get("status")

    stats_cols = [
        "player_id",
        "season",
        "games_played",
        "fantasy_pts_ppr",
        "fantasy_pts_std",
        "pts_per_game",
        "targets",
        "carries",
        "air_yards",
        "snap_pct",
        "target_share",
    ]
    stats_df = df[stats_cols].dropna(subset=["player_id", "season"])

    existing_stats = {
        (s.player_id, s.season): s
        for s in db_session.scalars(select(SeasonStats).where(SeasonStats.season.in_(stats_df["season"].unique().tolist())))
    }

    for row in stats_df.to_dict(orient="records"):
        key = (row["player_id"], int(row["season"]))
        stat = existing_stats.get(key)
        payload = {
            "player_id": row["player_id"],
            "season": int(row["season"]),
            "games_played": int(row["games_played"]) if pd.notna(row["games_played"]) else None,
            "fantasy_pts_ppr": float(row["fantasy_pts_ppr"]) if pd.notna(row["fantasy_pts_ppr"]) else None,
            "fantasy_pts_std": float(row["fantasy_pts_std"]) if pd.notna(row["fantasy_pts_std"]) else None,
            "pts_per_game": float(row["pts_per_game"]) if pd.notna(row["pts_per_game"]) else None,
            "targets": float(row["targets"]) if pd.notna(row["targets"]) else None,
            "carries": float(row["carries"]) if pd.notna(row["carries"]) else None,
            "air_yards": float(row["air_yards"]) if pd.notna(row["air_yards"]) else None,
            "snap_pct": float(row["snap_pct"]) if pd.notna(row["snap_pct"]) else None,
            "target_share": float(row["target_share"]) if pd.notna(row["target_share"]) else None,
        }

        if stat is None:
            db_session.add(SeasonStats(**payload))
        else:
            for field, value in payload.items():
                setattr(stat, field, value)

    db_session.commit()
