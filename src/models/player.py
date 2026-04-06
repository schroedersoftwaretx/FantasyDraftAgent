from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class Player(Base):
    __tablename__ = "players"

    player_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[str] = mapped_column(String(5), ForeignKey("positions.code"), nullable=False)
    nfl_team: Mapped[str | None] = mapped_column(String(5), ForeignKey("nfl_teams.team_code"))
    age: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(20))
    adp: Mapped[float | None] = mapped_column(Float)
    adp_rank: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"Player(player_id={self.player_id!r}, name={self.name!r}, position={self.position!r})"
