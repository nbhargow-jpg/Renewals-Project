"""
test_atomic_commit.py
Verify that commit_upload is strictly atomic:
When an unexpected exception occurs mid-commit, the transaction is rolled back
and no partial snapshot, opportunities, daily summaries, or change logs remain.
"""
import pytest
from datetime import date
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models.snapshot import UploadSnapshot, UploadedFile
from backend.models.opportunity import Opportunity
from backend.models.daily_summary import DailySummary
from backend.services.context import ADMIN_CONTEXT
from backend.services.ingest_service import IngestService, _save_session_to_disk, _delete_session
import pandas as pd


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def test_commit_atomic_rollback_on_failure(memory_db):
    """If a failure occurs during commit_upload, assert nothing is saved."""
    svc = IngestService(memory_db)
    
    # Setup test session payload
    test_session_id = "test-atomic-session-failure"
    today_mapped = pd.DataFrame([
        {
            "opportunity_id_18": "006TESTOPP001",
            "opportunity_name": "Test Opp 1",
            "forecast_acv_amount": 10000.0,
            "forecast_category": "Commit",
            "close_date": date(2026, 10, 7),
            "revised_sub_region": "North America",
        }
    ])
    
    session_data = {
        "data_as_of": date(2026, 10, 7),
        "yesterday_date": date(2026, 10, 6),
        "file_metadata": [{
            "slot": "comparison_tool",
            "filename": "mock.xlsx",
            "size_bytes": 100,
            "sha256": "mockhash",
        }],
        "today_mapped": today_mapped,
        "today_raw": None,
        "yesterday_raw": None,
        "summary_dfs": {},
        "scopes_summary": {},
        "snapshot_exists": False,
        "can_commit": True,
    }
    _save_session_to_disk(test_session_id, session_data)

    try:
        # Force an error mid-commit (e.g. inside _build_daily_summaries_multi_scope)
        with patch.object(svc, "_build_daily_summaries_multi_scope", side_effect=RuntimeError("Forced mid-commit failure")):
            with pytest.raises(RuntimeError, match="Forced mid-commit failure"):
                svc.commit_upload(ADMIN_CONTEXT, test_session_id, replace=False)

        # Assert database has zero records saved
        assert memory_db.query(UploadSnapshot).count() == 0, "No snapshots should remain"
        assert memory_db.query(Opportunity).count() == 0, "No opportunities should remain"
        assert memory_db.query(DailySummary).count() == 0, "No daily summaries should remain"
        assert memory_db.query(UploadedFile).count() == 0, "No uploaded files should remain"
    finally:
        _delete_session(test_session_id)
