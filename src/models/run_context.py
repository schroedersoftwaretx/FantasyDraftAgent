from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class RunContext(Base):
    __tablename__ = "run_contexts"
    __table_args__ = (
        UniqueConstraint(
            "season",
            "scoring_format",
            "league_size",
            name="uq_run_context_season_format_size",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    scoring_format: Mapped[str] = mapped_column(String(10), nullable=False)
    league_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return (
            "RunContext("
            f"id={self.id!r}, season={self.season!r}, "
            f"scoring_format={self.scoring_format!r}, league_size={self.league_size!r})"
        )
