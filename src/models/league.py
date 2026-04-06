from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class League(Base):
    __tablename__ = "leagues"

    league_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100))
    platform: Mapped[str | None] = mapped_column(String(20))
    num_teams: Mapped[int] = mapped_column(Integer, default=12)
    scoring_format: Mapped[str] = mapped_column(String(10), default="ppr")
    qb_slots: Mapped[int] = mapped_column(Integer, default=1)
    rb_slots: Mapped[int] = mapped_column(Integer, default=2)
    wr_slots: Mapped[int] = mapped_column(Integer, default=2)
    te_slots: Mapped[int] = mapped_column(Integer, default=1)
    flex_slots: Mapped[int] = mapped_column(Integer, default=1)
    bench_slots: Mapped[int] = mapped_column(Integer, default=6)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"League(league_id={self.league_id!r}, name={self.name!r})"
