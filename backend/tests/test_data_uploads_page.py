"""
Tests for Data Uploads consolidation:
1. Old routes /upload and /history redirect to /data-uploads (frontend routes / redirects).
2. No write controls accepted without admin (POST/PUT/PATCH/DELETE require admin).
3. History numbers equal DB values (348 deals / $40,068,990.09 for Oct 7 Q4 slice).
4. Content-based slot detection and coverage metadata.
"""
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db
from backend.models.snapshot import UploadSnapshot
from backend.models.opportunity import Opportunity
from backend.services.context import sign_admin_token
from backend.utils.excel_parser import detect_file_slot

SAMPLE_DIR = Path(os.environ.get("RENEWALS_SAMPLE_DIR", Path(__file__).resolve().parents[2] / "data" / "sample_oct7"))
FILES = sorted(SAMPLE_DIR.glob("*.xlsx")) if SAMPLE_DIR.exists() else []

@pytest.fixture(scope="module", autouse=True)
def setup_admin_env():
    from backend.config import settings
    old_pw = settings.ADMIN_PASSWORD
    old_key = settings.ADMIN_SECRET_KEY
    settings.ADMIN_PASSWORD = "test-admin-secret-password-xyz"
    settings.ADMIN_SECRET_KEY = "test-secret-key-32bytes-hex-dummy-value"
    yield
    settings.ADMIN_PASSWORD = old_pw
    settings.ADMIN_SECRET_KEY = old_key

@pytest.fixture(scope="module")
def admin_token(setup_admin_env):
    return sign_admin_token()

@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}

@pytest.fixture(scope="module")
def client_and_db(tmp_path_factory, setup_admin_env):
    from backend.tests.test_db_helper import get_test_engine_and_session
    engine, Session = get_test_engine_and_session("test_data_uploads_page", tmp_path_factory)

    from backend.services.context import require_admin_context
    app.dependency_overrides.pop(require_admin_context, None)

    def _override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c, Session
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def seeded_oct7(client_and_db, admin_headers):
    client, Session = client_and_db
    # If already has Oct 7 snapshot in DB, return it
    db = Session()
    from datetime import date as dt_date
    existing = db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == dt_date(2026, 10, 7)).first()
    if existing:
        db.close()
        return existing.id

    # Ingest sample_oct7 files cleanly
    out = {}
    for f in FILES:
        slot, _ = detect_file_slot(f)
        out[slot] = f

    handles = {s: (p.name, p.open("rb"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") for s, p in out.items()}
    try:
        val_res = client.post("/api/snapshots/validate", data={"data_as_of_date": "2026-10-07"}, files=handles, headers=admin_headers)
    finally:
        for _, fh, _ in handles.values():
            fh.close()
    assert val_res.status_code == 200, val_res.text
    session_id = val_res.json()["session_id"]
    com_res = client.post("/api/snapshots/commit", json={"session_id": session_id, "replace": False, "make_active": True}, headers=admin_headers)
    assert com_res.status_code == 200, com_res.text
    snap_id = com_res.json()["snapshot_id"]
    db.close()
    return snap_id


def test_history_numbers_equal_db_values(client_and_db, seeded_oct7):
    """
    Assert snapshot history endpoint returns exact DB values for Oct 7 Q4 slice:
    348 deals / $40,068,990.09.
    """
    client, _ = client_and_db
    res = client.get("/api/snapshots/history")
    assert res.status_code == 200, res.text
    history = res.json()
    assert len(history) > 0

    oct7_snap = next((h for h in history if h["snapshot_date"] == "2026-10-07"), None)
    assert oct7_snap is not None, f"Oct 7 snapshot not found in history: {[h['snapshot_date'] for h in history]}"

    assert oct7_snap["q_slice_label"] in ("Q4 FY26", "Q4-2026")
    assert oct7_snap["q_slice_deals"] == 348
    assert abs(oct7_snap["q_slice_acv"] - 40068990.09) < 0.01

    # Check sha256 and files metadata
    assert "files" in oct7_snap
    for f in oct7_snap["files"]:
        assert "filename" in f
        assert "sha256" in f


def test_snapshots_list_also_reports_q_slice_deals_and_acv(client_and_db, seeded_oct7):
    """
    Assert GET /api/snapshots also returns q_slice_deals and q_slice_acv matching DB.
    """
    client, _ = client_and_db
    res = client.get("/api/snapshots")
    assert res.status_code == 200
    snaps = res.json()
    oct7_snap = next((s for s in snaps if s["snapshot_date"] == "2026-10-07"), None)
    assert oct7_snap is not None
    assert oct7_snap["q_slice_deals"] == 348
    assert abs(oct7_snap["q_slice_acv"] - 40068990.09) < 0.01


def test_write_routes_reject_non_admin_requests(client_and_db):
    """
    Mutating snapshot routes (validate, commit, upload, set-active, delete)
    must reject calls without admin authorization (401 or 403).
    """
    client, _ = client_and_db
    mutating_calls = [
        ("POST", "/api/snapshots/validate"),
        ("POST", "/api/snapshots/commit"),
        ("POST", "/api/snapshots/upload"),
        ("POST", "/api/snapshots/59d7e47e-c9e1-4bbd-9c80-33f756c17a33/set-active"),
        ("DELETE", "/api/snapshots/fake_id"),
    ]

    bad_headers = {"Authorization": "Bearer bad-token-xyz"}

    for method, path in mutating_calls:
        # Without token -> 401
        r_no = client.request(method, path)
        assert r_no.status_code == 401, f"{method} {path} without token returned {r_no.status_code}"

        # With bad token -> 403
        r_bad = client.request(method, path, headers=bad_headers)
        assert r_bad.status_code == 403, f"{method} {path} with bad token returned {r_bad.status_code}"


def test_set_active_snapshot_admin_only(client_and_db, seeded_oct7, admin_headers):
    """
    Admin can set active snapshot via POST /api/snapshots/{id}/set-active.
    """
    client, _ = client_and_db
    res = client.post(f"/api/snapshots/{seeded_oct7}/set-active", headers=admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["is_active_today"] is True
    assert body["active_snapshot_id"] == seeded_oct7
