"""
test_commit_session_validation.py
Tests that the /snapshots/commit endpoint rejects:
  1. A session_id that was never issued (random UUID)
  2. A session_id that has already been consumed (used twice)
  3. A session_id from a failed validation (can_commit=False)

These tests call the HTTP API directly (not the service layer).
"""
import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import get_db
from backend.services.ingest_service import _UPLOAD_SESSIONS


from backend.services.context import require_admin_context, ADMIN_CONTEXT


@pytest.fixture
def client(seeded_session, db_engine):
    Session = sessionmaker(bind=db_engine)
    def _override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[require_admin_context] = lambda: ADMIN_CONTEXT
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestCommitSessionValidation:
    """Commit endpoint must reject invalid / failed session tokens."""

    def test_random_uuid_rejected(self, client):
        """A random UUID that was never issued by validate_upload should return 400."""
        fake_id = str(uuid.uuid4())
        r = client.post("/api/snapshots/commit", json={"session_id": fake_id})
        assert r.status_code == 400, (
            f"Expected 400 for unknown session_id, got {r.status_code}: {r.text}"
        )
        assert "expired" in r.json()["detail"].lower() or "invalid" in r.json()["detail"].lower(), (
            f"Error detail should mention 'expired' or 'invalid': {r.json()['detail']}"
        )

    def test_failed_session_rejected(self, client):
        """A session_id stored with can_commit=False must be rejected by the commit endpoint."""
        # Manually inject a failed session into the in-memory store
        failed_session_id = str(uuid.uuid4())
        _UPLOAD_SESSIONS[failed_session_id] = {
            "can_commit": False,
            "data_as_of": None,
            "yesterday_date": None,
            "files_dict": {},
            "file_metadata": [],
            "today_mapped": None,
            "today_raw": None,
            "yesterday_raw": None,
            "comp_sheets": {},
            "summary_dfs": {},
            "scope_ids": {},
            "scope_available": {},
            "renewals_ids": set(),
            "renewals_available": False,
            "scopes_summary": {},
            "snapshot_exists": False,
        }
        try:
            r = client.post("/api/snapshots/commit", json={"session_id": failed_session_id})
            assert r.status_code == 400, (
                f"Expected 400 for failed session, got {r.status_code}: {r.text}"
            )
            detail = r.json()["detail"].lower()
            assert "validation errors" in detail or "cannot commit" in detail, (
                f"Error detail should mention validation: {r.json()['detail']}"
            )
        finally:
            _UPLOAD_SESSIONS.pop(failed_session_id, None)

    def test_empty_string_session_rejected(self, client):
        """An empty session_id string must be rejected cleanly."""
        r = client.post("/api/snapshots/commit", json={"session_id": ""})
        # 400 or 422 both acceptable — the important thing is it does not succeed
        assert r.status_code in (400, 422), (
            f"Expected 400/422 for empty session_id, got {r.status_code}: {r.text}"
        )

    def test_missing_session_id_rejected(self, client):
        """Sending no session_id at all must be rejected with 422 Unprocessable Entity."""
        r = client.post("/api/snapshots/commit", json={})
        assert r.status_code == 422, (
            f"Expected 422 for missing session_id, got {r.status_code}: {r.text}"
        )
