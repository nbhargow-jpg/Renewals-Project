"""
test_upload_hardening.py — Tests for Upload hardening requirements:
  1. Yesterday resolution: latest snapshot in DB within 5 days (Monday -> Friday, holiday gap)
  2. Bootstrap from file when no prior snapshot in DB
  3. Out-of-order backfill: older date preserves latest active snapshot by default
  4. Explicit make_active override for backfills
  5. Replace flow safety checks
  6. Duplicate hash warnings
"""
import pytest
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
from sqlalchemy.orm import sessionmaker

from backend.models.snapshot import UploadSnapshot, UploadedFile
from backend.services.context import ADMIN_CONTEXT
from backend.services.ingest_service import IngestService, _save_session_to_disk
from backend.utils.excel_parser import compute_file_sha256
from backend.config import settings


from backend.models.opportunity import Opportunity
from backend.models.daily_summary import DailySummary
from backend.models.change_log import ChangeLog, ForecastMovementLog


@pytest.fixture
def clean_db(db_engine):
    """Provides a clean database for each upload test."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    for model in [UploadedFile, Opportunity, DailySummary, ChangeLog, ForecastMovementLog, UploadSnapshot]:
        session.query(model).delete()
    session.commit()

    yield session

    session.rollback()
    for model in [UploadedFile, Opportunity, DailySummary, ChangeLog, ForecastMovementLog, UploadSnapshot]:
        session.query(model).delete()
    session.commit()
    session.close()


class TestUploadHardening:
    def test_monday_to_friday_db_resolution(self, clean_db):
        """When Friday Oct 2 is in DB, validating Monday Oct 5 resolves yesterday to Friday Oct 2."""
        fri_date = date(2026, 10, 2)
        mon_date = date(2026, 10, 5)

        # Insert Friday snapshot
        fri_snap = UploadSnapshot(
            label="Friday",
            snapshot_date=fri_date,
            row_count=100,
            active_row_count=100,
            uploaded_by="test_user",
        )
        clean_db.add(fri_snap)
        clean_db.commit()

        svc = IngestService(clean_db)
        # Use existing comparison file for validation
        comp_file = settings.DATA_DIR / "sample_oct7" / "Renewal Comparison Tool 11.xlsx"
        if not comp_file.exists():
            comp_file = settings.DATA_DIR / "Renewal Comparison Tool 11.xlsx"

        res = svc.validate_upload(
            ADMIN_CONTEXT,
            {"comparison_tool": comp_file},
            data_as_of=mon_date,
            yesterday_date=None,
        )

        assert res["yesterday_date"] == fri_date.isoformat()
        assert "from database snapshot" in res["yesterday_source_desc"]
        assert fri_date.isoformat() in res["yesterday_source_desc"]

    def test_holiday_gap_resolves_to_last_real_upload(self, clean_db):
        """If Tuesday was a holiday, Wednesday Oct 7 resolves to Monday Oct 5."""
        mon_date = date(2026, 10, 5)
        wed_date = date(2026, 10, 7)

        mon_snap = UploadSnapshot(
            label="Monday",
            snapshot_date=mon_date,
            row_count=150,
            active_row_count=150,
            uploaded_by="test_user",
        )
        clean_db.add(mon_snap)
        clean_db.commit()

        svc = IngestService(clean_db)
        comp_file = settings.DATA_DIR / "sample_oct7" / "Renewal Comparison Tool 11.xlsx"
        if not comp_file.exists():
            comp_file = settings.DATA_DIR / "Renewal Comparison Tool 11.xlsx"

        res = svc.validate_upload(
            ADMIN_CONTEXT,
            {"comparison_tool": comp_file},
            data_as_of=wed_date,
            yesterday_date=None,
        )

        assert res["yesterday_date"] == mon_date.isoformat()
        assert "from database snapshot" in res["yesterday_source_desc"]

    def test_bootstrap_from_file_when_no_prior_snapshot(self, clean_db):
        """When no prior snapshot is found in DB within 5 days, bootstrap from file."""
        clean_db.query(UploadSnapshot).delete()
        clean_db.commit()

        target_date = date(2026, 10, 5)
        svc = IngestService(clean_db)
        comp_file = settings.DATA_DIR / "sample_oct7" / "Renewal Comparison Tool 11.xlsx"
        if not comp_file.exists():
            comp_file = settings.DATA_DIR / "Renewal Comparison Tool 11.xlsx"

        res = svc.validate_upload(
            ADMIN_CONTEXT,
            {"comparison_tool": comp_file},
            data_as_of=target_date,
            yesterday_date=None,
        )

        assert "bootstrapped from Yesterday_Data sheet" in res["yesterday_source_desc"]

    def test_backfill_upload_preserves_latest_active_snapshot(self, clean_db):
        """Uploading an older date must not automatically become active today if newer exists."""
        clean_db.query(UploadSnapshot).delete()
        clean_db.commit()

        newer_date = date(2026, 10, 7)
        older_date = date(2026, 10, 1)

        newer_snap = UploadSnapshot(
            label="Newer",
            snapshot_date=newer_date,
            row_count=200,
            active_row_count=200,
            is_active_today=True,
            uploaded_by="test_user",
        )
        clean_db.add(newer_snap)
        clean_db.commit()

        svc = IngestService(clean_db)
        comp_file = settings.DATA_DIR / "sample_oct7" / "Renewal Comparison Tool 11.xlsx"
        if not comp_file.exists():
            comp_file = settings.DATA_DIR / "Renewal Comparison Tool 11.xlsx"

        res = svc.validate_upload(
            ADMIN_CONTEXT,
            {"comparison_tool": comp_file},
            data_as_of=older_date,
            yesterday_date=None,
        )
        session_id = res["session_id"]
        assert session_id is not None

        # Commit without make_active (default: older snapshot should NOT become active)
        old_snap = svc.commit_upload(ADMIN_CONTEXT, session_id, replace=False, make_active=None)
        assert old_snap.is_active_today is False

        # Confirm newer snapshot is still active
        clean_db.refresh(newer_snap)
        assert newer_snap.is_active_today is True

    def test_backfill_upload_explicit_make_active(self, clean_db):
        """Uploading an older date with make_active=True overrides the default."""
        clean_db.query(UploadSnapshot).delete()
        clean_db.commit()

        newer_date = date(2026, 10, 7)
        older_date = date(2026, 10, 1)

        newer_snap = UploadSnapshot(
            label="Newer",
            snapshot_date=newer_date,
            row_count=200,
            active_row_count=200,
            is_active_today=True,
            uploaded_by="test_user",
        )
        clean_db.add(newer_snap)
        clean_db.commit()

        svc = IngestService(clean_db)
        comp_file = settings.DATA_DIR / "sample_oct7" / "Renewal Comparison Tool 11.xlsx"
        if not comp_file.exists():
            comp_file = settings.DATA_DIR / "Renewal Comparison Tool 11.xlsx"

        res = svc.validate_upload(
            ADMIN_CONTEXT,
            {"comparison_tool": comp_file},
            data_as_of=older_date,
            yesterday_date=None,
        )
        session_id = res["session_id"]

        old_snap = svc.commit_upload(ADMIN_CONTEXT, session_id, replace=False, make_active=True)
        assert old_snap.is_active_today is True

        clean_db.refresh(newer_snap)
        assert newer_snap.is_active_today is False

    def test_replace_flow_safety_checks(self, clean_db):
        """Committing for a date that already exists raises ValueError if replace=False, succeeds if replace=True."""
        target_date = date(2026, 10, 5)
        clean_db.query(UploadSnapshot).delete()
        clean_db.commit()

        existing = UploadSnapshot(
            label="Existing",
            snapshot_date=target_date,
            row_count=100,
            active_row_count=100,
            uploaded_by="test_user",
        )
        clean_db.add(existing)
        clean_db.commit()

        svc = IngestService(clean_db)
        comp_file = settings.DATA_DIR / "sample_oct7" / "Renewal Comparison Tool 11.xlsx"
        if not comp_file.exists():
            comp_file = settings.DATA_DIR / "Renewal Comparison Tool 11.xlsx"

        res = svc.validate_upload(
            ADMIN_CONTEXT,
            {"comparison_tool": comp_file},
            data_as_of=target_date,
            yesterday_date=None,
        )
        assert res["snapshot_exists"] is True
        assert res["existing_snapshot"] is not None
        session_id = res["session_id"]

        # 1. Commit with replace=False should raise ValueError
        with pytest.raises(ValueError, match="already exists"):
            svc.commit_upload(ADMIN_CONTEXT, session_id, replace=False)

        # 2. Commit with replace=True should succeed
        replaced_snap = svc.commit_upload(ADMIN_CONTEXT, session_id, replace=True)
        assert replaced_snap.snapshot_date == target_date
        assert replaced_snap.id == existing.id

    def test_duplicate_hash_warning(self, clean_db):
        """When identical files are validated against a different snapshot date, warn about identical SHA-256."""
        comp_file = settings.DATA_DIR / "sample_oct7" / "Renewal Comparison Tool 11.xlsx"
        if not comp_file.exists():
            comp_file = settings.DATA_DIR / "Renewal Comparison Tool 11.xlsx"

        file_sha = compute_file_sha256(comp_file)

        # Create previous snapshot with this file
        prev_date = date(2026, 10, 1)
        prev_snap = UploadSnapshot(
            label="Previous",
            snapshot_date=prev_date,
            row_count=50,
            active_row_count=50,
        )
        clean_db.add(prev_snap)
        clean_db.flush()

        clean_db.add(
            UploadedFile(
                snapshot_id=prev_snap.id,
                file_slot="comparison_tool",
                filename=comp_file.name,
                file_size_bytes=comp_file.stat().st_size,
                sha256_hash=file_sha,
            )
        )
        clean_db.commit()

        svc = IngestService(clean_db)
        new_date = date(2026, 10, 5)
        res = svc.validate_upload(
            ADMIN_CONTEXT,
            {"comparison_tool": comp_file},
            data_as_of=new_date,
            yesterday_date=None,
        )

        sha_warnings = [w for w in res["warnings"] if "identical content" in w.lower() or "sha-256" in w.lower()]
        assert len(sha_warnings) > 0, f"Expected duplicate SHA-256 warning, got warnings: {res['warnings']}"
