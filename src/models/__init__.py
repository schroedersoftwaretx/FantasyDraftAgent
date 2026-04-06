from __future__ import annotations

from sqlalchemy.orm import declarative_base

Base = declarative_base()

from src.models.draft import DraftPick, DraftSession  # noqa: E402,F401
from src.models.league import League  # noqa: E402,F401
from src.models.nfl_team import NFLTeam  # noqa: E402,F401
from src.models.player import Player  # noqa: E402,F401
from src.models.position import Position  # noqa: E402,F401
from src.models.projection import Projection  # noqa: E402,F401
from src.models.replacement_level import ReplacementLevel  # noqa: E402,F401
from src.models.run_context import RunContext  # noqa: E402,F401
from src.models.season_stats import SeasonStats  # noqa: E402,F401
from src.models.vorp_score import VORPScore  # noqa: E402,F401
