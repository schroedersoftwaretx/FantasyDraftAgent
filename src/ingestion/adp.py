from __future__ import annotations

import logging
from difflib import get_close_matches

import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from src.config import settings
from src.database import get_db
from src.models.player import Player

logger = logging.getLogger(__name__)
VALID_POSITIONS = {"QB", "RB", "WR", "TE"}


def _normalize_player_name(raw: str) -> str:
    return raw.replace(".", "").replace("'", "").strip().lower()


def fetch_fantasypros_adp() -> pd.DataFrame:
    try:
        response = requests.get(settings.FANTASYPROS_ADP_URL, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("FantasyPros ADP fetch failed: %s", exc)
        return pd.DataFrame(columns=["player_id", "name", "position", "nfl_team", "adp", "adp_rank"])

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table")
    if table is None:
        logger.warning("FantasyPros ADP table not found in response")
        return pd.DataFrame(columns=["player_id", "name", "position", "nfl_team", "adp", "adp_rank"])

    rows: list[dict[str, object]] = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue

        rank_text = tds[0].get_text(strip=True)
        player_text = tds[1].get_text(" ", strip=True)
        adp_text = tds[2].get_text(strip=True)
        if not rank_text or not player_text or not adp_text:
            continue

        parts = player_text.split()
        if len(parts) < 3:
            continue
        position = parts[-2].upper()
        nfl_team = parts[-1].upper()
        name = " ".join(parts[:-2]).strip()
        if position not in VALID_POSITIONS:
            continue
        try:
            adp = float(adp_text)
            adp_rank = int(float(rank_text))
        except ValueError:
            continue
        rows.append(
            {
                "name": name,
                "position": position,
                "nfl_team": nfl_team,
                "adp": adp,
                "adp_rank": adp_rank,
            }
        )

    adp_df = pd.DataFrame(rows)
    if adp_df.empty:
        return pd.DataFrame(columns=["player_id", "name", "position", "nfl_team", "adp", "adp_rank"])

    try:
        with get_db() as db:
            players = db.scalars(select(Player)).all()
    except SQLAlchemyError:
        players = []

    if not players:
        adp_df["player_id"] = None
        return adp_df[["player_id", "name", "position", "nfl_team", "adp", "adp_rank"]]

    name_map = {_normalize_player_name(p.name): p.player_id for p in players}
    normalized_names = list(name_map.keys())

    matched_ids: list[str | None] = []
    for _, row in adp_df.iterrows():
        key = _normalize_player_name(str(row["name"]))
        player_id = name_map.get(key)
        if player_id is None:
            match = get_close_matches(key, normalized_names, n=1, cutoff=0.85)
            player_id = name_map[match[0]] if match else None
        matched_ids.append(player_id)

    adp_df["player_id"] = matched_ids
    return adp_df[["player_id", "name", "position", "nfl_team", "adp", "adp_rank"]]
