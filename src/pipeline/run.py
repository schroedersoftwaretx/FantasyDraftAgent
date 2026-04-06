from __future__ import annotations

import logging
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sqlalchemy import select

from src.config import settings
from src.database import get_db, init_db
from src.ingestion.adp import fetch_fantasypros_adp
from src.ingestion.nfl_data import load_historical_stats, upsert_players_and_stats
from src.ingestion.projections import (
    compute_consensus_projection,
    fetch_espn_projections,
    fetch_nfl_data_projections,
)
from src.models.player import Player
from src.models.projection import Projection
from src.models.replacement_level import ReplacementLevel
from src.models.run_context import RunContext
from src.models.season_stats import SeasonStats
from src.models.vorp_score import VORPScore
from src.models_ml.tiers import assign_tiers
from src.models_ml.vorp import calculate_vorp
from src.models_ml.weights import compute_source_weights

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _upsert_adp(adp_df: pd.DataFrame) -> None:
    if adp_df.empty:
        return

    with get_db() as db:
        for row in adp_df.dropna(subset=["player_id"]).to_dict(orient="records"):
            player = db.get(Player, row["player_id"])
            if player is None:
                continue
            player.adp = float(row["adp"]) if pd.notna(row.get("adp")) else None
            player.adp_rank = int(row["adp_rank"]) if pd.notna(row.get("adp_rank")) else None
        db.commit()


def _upsert_source_projections(source_df: pd.DataFrame) -> None:
    if source_df.empty:
        return
    with get_db() as db:
        existing = {
            (p.player_id, p.season, p.source): p
            for p in db.scalars(select(Projection).where(Projection.season == int(source_df["season"].iloc[0])))
        }
        for row in source_df.to_dict(orient="records"):
            key = (row["player_id"], int(row["season"]), row["source"])
            payload = {
                "player_id": row["player_id"],
                "season": int(row["season"]),
                "source": row["source"],
                "projected_pts": float(row["projected_pts"]),
                "proj_pts_per_game": None,
                "weight": float(row.get("weight", 1.0)),
                "weighted_pts": float(row["projected_pts"]) * float(row.get("weight", 1.0)),
            }
            obj = existing.get(key)
            if obj is None:
                db.add(Projection(**payload))
            else:
                for field, value in payload.items():
                    setattr(obj, field, value)
        db.commit()


def _upsert_consensus_projections(consensus_df: pd.DataFrame) -> None:
    if consensus_df.empty:
        return
    with get_db() as db:
        existing = {
            (p.player_id, p.season, p.source): p
            for p in db.scalars(select(Projection).where(Projection.season == int(consensus_df["season"].iloc[0])))
        }
        for row in consensus_df.to_dict(orient="records"):
            key = (row["player_id"], int(row["season"]), "consensus")
            payload = {
                "player_id": row["player_id"],
                "season": int(row["season"]),
                "source": "consensus",
                "projected_pts": float(row["projected_pts"]),
                "proj_pts_per_game": None,
                "weight": 1.0,
                "weighted_pts": float(row["projected_pts"]),
            }
            obj = existing.get(key)
            if obj is None:
                db.add(Projection(**payload))
            else:
                for field, value in payload.items():
                    setattr(obj, field, value)
        db.commit()


def _update_projection_weights(weights: dict[str, float], season: int) -> None:
    if not weights:
        return
    with get_db() as db:
        for projection in db.scalars(select(Projection).where(Projection.season == season)):
            if projection.source in weights:
                projection.weight = float(weights[projection.source])
                projection.weighted_pts = (projection.projected_pts or 0.0) * projection.weight
        db.commit()


def _get_or_create_run_context(season: int, scoring_format: str, league_size: int) -> int:
    with get_db() as db:
        existing = db.execute(
            select(RunContext).where(
                RunContext.season == season,
                RunContext.scoring_format == scoring_format,
                RunContext.league_size == league_size,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return int(existing.id)

        ctx = RunContext(
            season=season,
            scoring_format=scoring_format,
            league_size=league_size,
        )
        db.add(ctx)
        db.commit()
        db.refresh(ctx)
        return int(ctx.id)


def _upsert_replacement_levels(vorp_df: pd.DataFrame, run_id: int) -> None:
    if vorp_df.empty:
        return
    replacement_df = (
        vorp_df[["position", "replacement_pts"]]
        .dropna(subset=["position", "replacement_pts"])
        .drop_duplicates("position")
    )
    if replacement_df.empty:
        return
    with get_db() as db:
        existing = {
            r.position: r
            for r in db.scalars(select(ReplacementLevel).where(ReplacementLevel.run_id == run_id))
        }
        for row in replacement_df.to_dict(orient="records"):
            pos = str(row["position"])
            value = float(row["replacement_pts"])
            obj = existing.get(pos)
            if obj is None:
                db.add(ReplacementLevel(run_id=run_id, position=pos, replacement_pts=value))
            else:
                obj.replacement_pts = value
        db.commit()


def _upsert_vorp_scores(vorp_df: pd.DataFrame, run_id: int) -> None:
    if vorp_df.empty:
        return
    with get_db() as db:
        existing = {
            (v.player_id, v.run_id): v
            for v in db.scalars(select(VORPScore).where(VORPScore.run_id == run_id))
        }
        for row in vorp_df.to_dict(orient="records"):
            key = (row["player_id"], run_id)
            payload = {
                "player_id": row["player_id"],
                "run_id": run_id,
                "projected_pts": float(row["projected_pts"]),
                "vorp": float(row["vorp"]),
                "pos_rank": int(row["pos_rank"]),
                "overall_rank": int(row["overall_rank"]),
                "tier": int(row["tier"]),
                "adp_delta": float(row["adp_delta"]) if pd.notna(row["adp_delta"]) else None,
                "calculated_at": datetime.now(UTC),
            }
            obj = existing.get(key)
            if obj is None:
                db.add(VORPScore(**payload))
            else:
                for field, value in payload.items():
                    setattr(obj, field, value)
        db.commit()


def _load_actuals() -> pd.DataFrame:
    with get_db() as db:
        rows = db.execute(
            select(SeasonStats.player_id, SeasonStats.season, SeasonStats.fantasy_pts_ppr)
        ).all()
    return pd.DataFrame(rows, columns=["player_id", "season", "fantasy_pts_ppr"])


def _print_summary(vorp_df: pd.DataFrame, limit: int = 10) -> None:
    print("")
    print(f"=== Top Players by VORP ({settings.DEFAULT_SCORING_FORMAT.upper()}, {settings.DEFAULT_LEAGUE_SIZE}-team) ===")
    print("")
    for position in ["QB", "RB", "WR", "TE"]:
        subset = vorp_df[vorp_df["position"] == position].sort_values("vorp", ascending=False).head(limit)
        print(f"{position}  | Rank | Player            | Proj Pts | VORP  | Tier | ADP D")
        print("----+------+-------------------+----------+-------+------+------")
        for _, row in subset.iterrows():
            adp_delta = row["adp_delta"]
            delta_str = "  n/a"
            if pd.notna(adp_delta):
                delta_str = f"{adp_delta:+.0f}".rjust(5)
            print(
                f"{int(row['pos_rank']):>4} | {int(row['overall_rank']):>4} | "
                f"{str(row['name'])[:18]:<18} | {float(row['projected_pts']):>8.1f} | "
                f"{float(row['vorp']):>5.1f} | {int(row['tier']):>4} | {delta_str}"
            )
        print("")


def run_pipeline(season: int | None = None) -> None:
    target_season = season or settings.CURRENT_SEASON
    prior_season = target_season - 1
    historical_seasons = sorted(set(s for s in settings.HISTORICAL_SEASONS if s <= prior_season))
    if prior_season not in historical_seasons:
        historical_seasons.append(prior_season)

    init_db()

    stats_df = load_historical_stats(historical_seasons)
    with get_db() as db:
        upsert_players_and_stats(stats_df, db)

    adp_df = fetch_fantasypros_adp()
    _upsert_adp(adp_df)

    espn_df = fetch_espn_projections(target_season)
    nfl_proj_df = fetch_nfl_data_projections(target_season)
    source_proj_df = pd.concat([espn_df, nfl_proj_df], ignore_index=True)

    if source_proj_df.empty:
        logger.warning("No source projections available; building fallback from latest season actuals.")
        fallback_season = max(historical_seasons) if historical_seasons else prior_season
        with get_db() as db:
            fallback_rows = db.execute(
                select(
                    SeasonStats.player_id,
                    SeasonStats.fantasy_pts_ppr,
                    Player.position,
                )
                .join(Player, Player.player_id == SeasonStats.player_id)
                .where(SeasonStats.season == fallback_season)
            ).all()
        fallback_df = pd.DataFrame(fallback_rows, columns=["player_id", "projected_pts", "position"])
        fallback_df["season"] = target_season
        fallback_df["source"] = "nfl_data_py"
        source_proj_df = fallback_df[["player_id", "season", "source", "projected_pts", "position"]]

    source_proj_df["weight"] = 1.0
    source_proj_df["weighted_pts"] = source_proj_df["projected_pts"] * source_proj_df["weight"]
    _upsert_source_projections(source_proj_df[["player_id", "season", "source", "projected_pts", "weight", "weighted_pts"]])

    # Prefer external season projections (ESPN) when available; use baseline source
    # only to fill players that do not yet have an external projection.
    espn_player_ids = set(source_proj_df.loc[source_proj_df["source"] == "espn", "player_id"].tolist())
    consensus_input = source_proj_df[
        (source_proj_df["source"] != "nfl_data_py") | (~source_proj_df["player_id"].isin(espn_player_ids))
    ].copy()

    consensus_df = compute_consensus_projection(consensus_input[["player_id", "season", "source", "projected_pts"]])
    _upsert_consensus_projections(consensus_df)

    actuals_df = _load_actuals()
    weights = compute_source_weights(
        projections_df=source_proj_df[["player_id", "season", "source", "projected_pts"]],
        actuals_df=actuals_df,
    )
    _update_projection_weights(weights, target_season)

    with get_db() as db:
        player_meta = pd.DataFrame(
            db.execute(select(Player.player_id, Player.name, Player.position, Player.adp, Player.adp_rank)).all(),
            columns=["player_id", "name", "position", "adp", "adp_rank"],
        )

    vorp_input = consensus_df.merge(player_meta[["player_id", "name", "position"]], on="player_id", how="left")
    vorp_input = vorp_input.dropna(subset=["position", "projected_pts"])
    adp_for_model = player_meta[["player_id", "adp", "adp_rank"]]
    vorp_df = calculate_vorp(
        projections_df=vorp_input[["player_id", "name", "position", "projected_pts"]],
        league_size=settings.DEFAULT_LEAGUE_SIZE,
        roster_slots=settings.ROSTER_SLOTS,
        scoring_format=settings.DEFAULT_SCORING_FORMAT,
        adp_df=adp_for_model,
    )
    if vorp_df.empty:
        logger.warning("VORP output is empty.")
        return

    vorp_df = assign_tiers(vorp_df)
    vorp_df["season"] = target_season
    vorp_df["adp_delta"] = vorp_df["adp_delta"].replace([np.inf, -np.inf], np.nan)
    run_id = _get_or_create_run_context(
        season=target_season,
        scoring_format=settings.DEFAULT_SCORING_FORMAT,
        league_size=settings.DEFAULT_LEAGUE_SIZE,
    )
    _upsert_replacement_levels(vorp_df, run_id=run_id)
    _upsert_vorp_scores(vorp_df, run_id=run_id)
    _print_summary(vorp_df)


if __name__ == "__main__":
    run_pipeline()
