from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class VORPScore(Base):
    __tablename__ = "vorp_scores"
    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "run_id",
            name="uq_vorp_player_run",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(String(32), ForeignKey("players.player_id"), nullable=False)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("run_contexts.id"), nullable=False)
    projected_pts: Mapped[float | None] = mapped_column(Float)
    vorp: Mapped[float | None] = mapped_column(Float)
    pos_rank: Mapped[int | None] = mapped_column(Integer)
    overall_rank: Mapped[int | None] = mapped_column(Integer)
    tier: Mapped[int | None] = mapped_column(Integer)
    adp_delta: Mapped[float | None] = mapped_column(Float)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"VORPScore(player_id={self.player_id!r}, run_id={self.run_id!r}, vorp={self.vorp!r})"
