"""
ChangeLog — field-level diff between two snapshots.
ForecastMovementLog — category-to-category flow (powers Sankey).
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import String, Text, DateTime, Integer, Numeric, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class ChangeLog(Base):
    __tablename__ = "change_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # nullable: may be None when the 'from' data comes from the Comparison Tool's embedded
    # yesterday sheet rather than a persisted DB snapshot.
    snapshot_from_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("upload_snapshots.id"), nullable=True, index=True
    )
    snapshot_to_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("upload_snapshots.id"), index=True
    )

    opportunity_id_18: Mapped[str | None] = mapped_column(String(64), index=True)
    opportunity_name: Mapped[str | None] = mapped_column(String(512))

    changed_column: Mapped[str | None] = mapped_column(String(128))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)

    opportunity_status: Mapped[str | None] = mapped_column(String(64))
    # e.g. "ACV Change" | "Category Move" | "Approval Change" | "Owner Change"
    change_type: Mapped[str | None] = mapped_column(String(64))

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    snapshot_from: Mapped["UploadSnapshot"] = relationship(  # noqa: F821
        "UploadSnapshot",
        foreign_keys=[snapshot_from_id],
        back_populates="change_logs_from",
    )
    snapshot_to: Mapped["UploadSnapshot"] = relationship(  # noqa: F821
        "UploadSnapshot",
        foreign_keys=[snapshot_to_id],
        back_populates="change_logs_to",
    )


class ForecastMovementLog(Base):
    """One row per from→to category pair per snapshot comparison."""
    __tablename__ = "forecast_movement_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_from_id: Mapped[str] = mapped_column(String(36), ForeignKey("upload_snapshots.id"), index=True)
    snapshot_to_id: Mapped[str] = mapped_column(String(36), ForeignKey("upload_snapshots.id"), index=True)
    from_category: Mapped[str | None] = mapped_column(String(64))
    to_category: Mapped[str | None] = mapped_column(String(64))
    opportunity_count: Mapped[int] = mapped_column(Integer, default=0)
    acv_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)

    def __repr__(self) -> str:
        return f"<ForecastMovement {self.from_category}→{self.to_category} n={self.opportunity_count}>"
