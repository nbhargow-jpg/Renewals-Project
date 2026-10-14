"""
DailySummary — pre-aggregated cache for fast sparklines and trend charts.
One row per (snapshot_date, metric, dimension, dimension_value).
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import String, Numeric, Date, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class DailySummary(Base):
    __tablename__ = "daily_summary"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("upload_snapshots.id"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)

    # e.g. "total_acv" | "forecast_acv" | "approval_count" | "opp_count"
    metric: Mapped[str] = mapped_column(String(64), index=True)

    # e.g. "forecast_category" | "approval_status" | "sub_region" | "business_unit" | "overall"
    dimension: Mapped[str] = mapped_column(String(64), index=True)

    # e.g. "Commit" | "Approved" | "APAC" | "overall"
    dimension_value: Mapped[str] = mapped_column(String(256), index=True)

    value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    count: Mapped[int] = mapped_column(Integer, default=0)

    snapshot: Mapped["UploadSnapshot"] = relationship(  # noqa: F821
        "UploadSnapshot", back_populates="daily_summaries"
    )

    def __repr__(self) -> str:
        return f"<DailySummary {self.snapshot_date} {self.metric}[{self.dimension}={self.dimension_value}]={self.value}>"
