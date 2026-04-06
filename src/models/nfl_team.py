from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class NFLTeam(Base):
    __tablename__ = "nfl_teams"

    team_code: Mapped[str] = mapped_column(String(5), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100))

    def __repr__(self) -> str:
        return f"NFLTeam(team_code={self.team_code!r})"
