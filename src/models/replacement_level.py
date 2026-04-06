from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class ReplacementLevel(Base):
    __tablename__ = "replacement_levels"
    __table_args__ = (
        UniqueConstraint("run_id", "position", name="uq_replacement_level_run_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("run_contexts.id"), nullable=False)
    position: Mapped[str] = mapped_column(String(5), ForeignKey("positions.code"), nullable=False)
    replacement_pts: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:
        return (
            f"ReplacementLevel(run_id={self.run_id!r}, position={self.position!r}, "
            f"replacement_pts={self.replacement_pts!r})"
        )
