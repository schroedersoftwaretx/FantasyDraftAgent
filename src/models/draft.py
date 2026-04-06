from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class DraftSession(Base):
    __tablename__ = "draft_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    league_id: Mapped[str] = mapped_column(String(64), ForeignKey("leagues.league_id"), nullable=False)
    current_pick: Mapped[int] = mapped_column(Integer, default=1)
    total_picks: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"DraftSession(session_id={self.session_id!r}, league_id={self.league_id!r})"


class DraftPick(Base):
    __tablename__ = "draft_picks"
    __table_args__ = (
        UniqueConstraint("session_id", "pick_number", name="uq_draft_picks_session_pick"),
        UniqueConstraint("session_id", "player_id", name="uq_draft_picks_session_player"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("draft_sessions.session_id"), nullable=False)
    player_id: Mapped[str] = mapped_column(String(32), ForeignKey("players.player_id"), nullable=False)
    pick_number: Mapped[int] = mapped_column(Integer, nullable=False)
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    team_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    picked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"DraftPick(session_id={self.session_id!r}, pick_number={self.pick_number!r})"
