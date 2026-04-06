from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.ingestion.adp import fetch_fantasypros_adp
from src.ingestion.nfl_data import upsert_players_and_stats
from src.models import Base
from src.models.season_stats import SeasonStats


def test_fetch_fantasypros_adp_live_non_empty_when_available() -> None:
    try:
        df = fetch_fantasypros_adp()
    except Exception as exc:  # pragma: no cover - network variability
        pytest.skip(f"Network unavailable for live ADP test: {exc}")

    if df.empty:
        pytest.skip("Live ADP endpoint returned empty data")
    assert not df.empty


def test_fetch_fantasypros_adp_with_mocked_response() -> None:
    html = """
    <html><body>
      <table>
        <tr><th>RK</th><th>Player Team (Bye)</th><th>AVG</th></tr>
        <tr><td>1</td><td>Christian McCaffrey RB SF</td><td>1.4</td></tr>
        <tr><td>2</td><td>CeeDee Lamb WR DAL</td><td>2.9</td></tr>
      </table>
    </body></html>
    """

    class MockResp:
        status_code = 200
        text = html

        def raise_for_status(self) -> None:
            return None

    with patch("src.ingestion.adp.requests.get", return_value=MockResp()):
        df = fetch_fantasypros_adp()

    assert isinstance(df, pd.DataFrame)
    assert {"name", "position", "nfl_team", "adp", "adp_rank"}.issubset(set(df.columns))
    assert len(df) >= 2


def test_upsert_players_and_stats_duplicate_inserts_no_raise() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    df = pd.DataFrame(
        [
            {
                "player_id": "abc123",
                "name": "Test Player",
                "position": "RB",
                "nfl_team": "NYJ",
                "age": 25,
                "status": "Active",
                "season": 2024,
                "games_played": 17,
                "fantasy_pts_ppr": 250.0,
                "fantasy_pts_std": 200.0,
                "pts_per_game": 14.7,
                "targets": 80,
                "carries": 220,
                "air_yards": 0.0,
                "snap_pct": 0.7,
                "target_share": 0.15,
            }
        ]
    )

    with Session() as db:
        upsert_players_and_stats(df, db)
        upsert_players_and_stats(df, db)
        rows = db.query(SeasonStats).all()
        assert len(rows) == 1
