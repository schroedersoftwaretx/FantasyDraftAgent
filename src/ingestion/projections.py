from __future__ import annotations

import logging
import json
import re
from difflib import get_close_matches

import pandas as pd
import requests
from sqlalchemy import select

from src.database import get_db
from src.models.player import Player
from src.models.season_stats import SeasonStats

logger = logging.getLogger(__name__)
VALID_POSITIONS = {"QB", "RB", "WR", "TE"}
ESPN_POSITION_MAP = {
    1: "QB",
    2: "RB",
    3: "WR",
    4: "TE",
}


def _name_aliases(name: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", name.lower())
    if not tokens:
        return []

    aliases: list[str] = [
        " ".join(tokens),  # full normalized name, highest confidence
        "".join(tokens),
    ]
    if len(tokens) >= 2:
        first = tokens[0]
        last = tokens[-1]
        aliases.extend(
            [
                f"{first} {last}",
                f"{first[0]} {last}",
                f"{first[0]}.{last}",
                f"{first[0]}{last}",
            ]
        )
    # Deduplicate while preserving confidence order.
    return list(dict.fromkeys(aliases))


def _player_lookup() -> tuple[dict[str, str], dict[str, str]]:
    with get_db() as db:
        players = db.scalars(select(Player)).all()
    id_map = {p.player_id: p.player_id for p in players}
    name_map: dict[str, str] = {}
    for player in players:
        for alias in _name_aliases(player.name):
            if alias not in name_map:
                name_map[alias] = player.player_id
    return id_map, name_map


def fetch_espn_projections(season: int) -> pd.DataFrame:
    # ESPN projections backing the public projections page.
    # Use X-Fantasy-Filter to request a larger player set than the default 50 rows.
    url = (
        f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"
        "/segments/0/leaguedefaults/3?view=kona_player_info"
    )
    fantasy_filter = {
        "players": {
            "limit": 2000,
            "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
        }
    }
    headers = {"X-Fantasy-Filter": json.dumps(fantasy_filter)}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        logger.warning("ESPN projections fetch failed: %s", exc)
        return pd.DataFrame(columns=["player_id", "season", "source", "projected_pts", "position"])

    _, name_map = _player_lookup()
    known_names = [k for k in name_map.keys() if " " in k] or list(name_map.keys())

    rows: list[dict[str, object]] = []
    players = payload.get("players", []) if isinstance(payload, dict) else []
    for wrapper in players:
        player_obj = wrapper.get("player", {}) if isinstance(wrapper, dict) else {}
        if not isinstance(player_obj, dict):
            continue

        name = str(player_obj.get("fullName") or "").strip()
        if not name:
            continue

        position = ESPN_POSITION_MAP.get(player_obj.get("defaultPositionId"))
        if position not in VALID_POSITIONS:
            continue

        stats_list = player_obj.get("stats", [])
        projection_record = None
        for stat_rec in stats_list if isinstance(stats_list, list) else []:
            if (
                stat_rec.get("statSourceId") == 1
                and stat_rec.get("statSplitTypeId") == 0
                and stat_rec.get("scoringPeriodId") == 0
                and int(stat_rec.get("seasonId", 0) or 0) == int(season)
            ):
                projection_record = stat_rec
                break

        if projection_record is None:
            continue

        pts = projection_record.get("appliedTotal")
        if pts is None:
            continue

        aliases = _name_aliases(name)
        player_id = next((name_map[a] for a in aliases if a in name_map), None)
        if player_id is None:
            key = " ".join(re.findall(r"[a-z0-9]+", name.lower()))
            match = get_close_matches(key, known_names, n=1, cutoff=0.8)
            player_id = name_map[match[0]] if match else None

        if not player_id:
            continue

        rows.append(
            {
                "player_id": player_id,
                "season": season,
                "source": "espn",
                "projected_pts": float(pts),
                "position": position,
            }
        )

    df = pd.DataFrame(rows, columns=["player_id", "season", "source", "projected_pts", "position"])
    if df.empty:
        return df

    # Keep one row per player/source/season to satisfy unique constraints.
    # Use the highest projected value when multiple name matches map to same player_id.
    df = (
        df.sort_values("projected_pts", ascending=False)
        .drop_duplicates(subset=["player_id", "season", "source"], keep="first")
        .reset_index(drop=True)
    )
    return df


def fetch_sleeper_projections(season: int) -> pd.DataFrame:
    # Backwards-compatible wrapper name retained from phase-1 spec.
    # Sleeper's previously attempted projections endpoint is unreliable;
    # use ESPN fantasy projections as the primary source.
    return fetch_espn_projections(season)


def fetch_nfl_data_projections(season: int) -> pd.DataFrame:
    # Simple phase-1 baseline: two-year rolling average of historical PPR points.
    with get_db() as db:
        hist = db.execute(
            select(
                SeasonStats.player_id,
                SeasonStats.season,
                SeasonStats.fantasy_pts_ppr,
                Player.position,
            ).join(Player, Player.player_id == SeasonStats.player_id)
        ).all()

    if not hist:
        return pd.DataFrame(columns=["player_id", "season", "source", "projected_pts", "position"])

    hist_df = pd.DataFrame(hist, columns=["player_id", "season", "fantasy_pts_ppr", "position"])
    hist_df = hist_df[hist_df["season"].between(season - 2, season - 1)]
    if hist_df.empty:
        return pd.DataFrame(columns=["player_id", "season", "source", "projected_pts", "position"])

    out = (
        hist_df.groupby(["player_id", "position"], as_index=False)["fantasy_pts_ppr"]
        .mean()
        .rename(columns={"fantasy_pts_ppr": "projected_pts"})
    )
    out["season"] = season
    out["source"] = "nfl_data_py"
    return out[["player_id", "season", "source", "projected_pts", "position"]]


def compute_consensus_projection(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["player_id", "season", "projected_pts"])

    data = df.copy()
    data["weight"] = 1.0
    data["weighted_pts"] = data["projected_pts"] * data["weight"]

    summary = (
        data.groupby(["player_id", "season"], as_index=False)
        .agg(total_weighted_pts=("weighted_pts", "sum"), total_weight=("weight", "sum"))
    )
    summary["projected_pts"] = summary["total_weighted_pts"] / summary["total_weight"]
    return summary[["player_id", "season", "projected_pts"]]
