from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class SeasonStats(Base):
    __tablename__ = "season_stats"
    __table_args__ = (UniqueConstraint("player_id", "season", name="uq_season_stats_player_season"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(String(32), ForeignKey("players.player_id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    games_played: Mapped[int | None] = mapped_column(Integer)
    fantasy_pts_ppr: Mapped[float | None] = mapped_column(Float)
    fantasy_pts_std: Mapped[float | None] = mapped_column(Float)
    pts_per_game: Mapped[float | None] = mapped_column(Float)
    targets: Mapped[float | None] = mapped_column(Float)
    carries: Mapped[float | None] = mapped_column(Float)
    air_yards: Mapped[float | None] = mapped_column(Float)
    snap_pct: Mapped[float | None] = mapped_column(Float)
    target_share: Mapped[float | None] = mapped_column(Float)

    def __repr__(self) -> str:
        return f"SeasonStats(player_id={self.player_id!r}, season={self.season!r})"
