"""
UploadSnapshot — immutable record of every data upload.
One snapshot per snapshot_date; both workbooks attach to the same row.
"""
import uuid
from datetime import datetime, date, timezone

from sqlalchemy import String, DateTime, Date, Integer, Boolean, Enum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class UploadSnapshot(Base):
    __tablename__ = "upload_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    label: Mapped[str] = mapped_column(String(64))            # "Today" / "Yesterday" / custom
    snapshot_date: Mapped[date] = mapped_column(Date, index=True, unique=True)
    workbook_type: Mapped[str] = mapped_column(
        Enum("RENEWALS_SUMMARY", "COMPARISON_TOOL", "BOTH", name="workbook_type_enum"),
        default="BOTH",
    )
    source_file_summary: Mapped[str | None] = mapped_column(String(256))
    source_file_comparison: Mapped[str | None] = mapped_column(String(256))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    active_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active_today: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    uploaded_by: Mapped[str] = mapped_column(String(128), default="system")

    # Working day yesterday date & last week tracking
    yesterday_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_week_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_week_is_partial: Mapped[bool] = mapped_column(Boolean, default=False)
    column_order: Mapped[list[str] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    # Relationships
    uploaded_files: Mapped[list["UploadedFile"]] = relationship(
        "UploadedFile", back_populates="snapshot", cascade="all, delete-orphan"
    )
    opportunities: Mapped[list["Opportunity"]] = relationship(  # noqa: F821
        "Opportunity", back_populates="snapshot", cascade="all, delete-orphan"
    )
    change_logs_from: Mapped[list["ChangeLog"]] = relationship(  # noqa: F821
        "ChangeLog",
        foreign_keys="ChangeLog.snapshot_from_id",
        back_populates="snapshot_from",
    )
    change_logs_to: Mapped[list["ChangeLog"]] = relationship(  # noqa: F821
        "ChangeLog",
        foreign_keys="ChangeLog.snapshot_to_id",
        back_populates="snapshot_to",
    )
    daily_summaries: Mapped[list["DailySummary"]] = relationship(  # noqa: F821
        "DailySummary", back_populates="snapshot", cascade="all, delete-orphan"
    )
    checks: Mapped[list["SnapshotCheck"]] = relationship(
        "SnapshotCheck", back_populates="snapshot", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<UploadSnapshot {self.label} {self.snapshot_date}>"


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("upload_snapshots.id", ondelete="CASCADE"), index=True)
    file_slot: Mapped[str] = mapped_column(String(64))  # comparison_tool | fiscal_2026 | fiscal_2027 | fiscal_q4
    filename: Mapped[str] = mapped_column(String(256))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    sha256_hash: Mapped[str] = mapped_column(String(64), index=True)
    sheet_names: Mapped[str | None] = mapped_column(String(1024))
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    snapshot: Mapped["UploadSnapshot"] = relationship("UploadSnapshot", back_populates="uploaded_files")


class SnapshotCheck(Base):
    __tablename__ = "snapshot_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("upload_snapshots.id", ondelete="CASCADE"), index=True)
    workbook_name: Mapped[str] = mapped_column(String(256))
    sheet_name: Mapped[str] = mapped_column(String(128))
    cell_or_row: Mapped[str] = mapped_column(String(128))
    metric_name: Mapped[str] = mapped_column(String(128))
    excel_value: Mapped[str] = mapped_column(String(256))
    website_value: Mapped[str] = mapped_column(String(256))
    diff_value: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), index=True)  # pass | fail | warning
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    snapshot: Mapped["UploadSnapshot"] = relationship("UploadSnapshot", back_populates="checks")


