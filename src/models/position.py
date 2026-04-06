from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class Position(Base):
    __tablename__ = "positions"

    code: Mapped[str] = mapped_column(String(5), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    def __repr__(self) -> str:
        return f"Position(code={self.code!r}, name={self.name!r})"
