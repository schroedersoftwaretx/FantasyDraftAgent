from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class Projection(Base):
    __tablename__ = "projections"
    __table_args__ = (UniqueConstraint("player_id", "season", "source", name="uq_projection_player_season_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(String(32), ForeignKey("players.player_id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    projected_pts: Mapped[float | None] = mapped_column(Float)
    proj_pts_per_game: Mapped[float | None] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    weighted_pts: Mapped[float | None] = mapped_column(Float)
    pulled_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"Projection(player_id={self.player_id!r}, season={self.season!r}, source={self.source!r})"
