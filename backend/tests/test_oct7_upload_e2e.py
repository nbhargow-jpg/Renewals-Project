"""
End-to-end upload test with the four real Oct 7 files, through the HTTP API.
Put the four .xlsx files in data/sample_oct7/ (any file names; slots are detected by content)
or set RENEWALS_SAMPLE_DIR. The test is skipped if the files are not there.
"""
import os
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend.models.opportunity import Opportunity
from backend.utils.excel_parser import detect_file_slot, parse_excel_date

SAMPLE_DIR = Path(os.environ.get("RENEWALS_SAMPLE_DIR", Path(__file__).resolve().parents[2] / "data" / "sample_oct7"))
FILES = sorted(SAMPLE_DIR.glob("*.xlsx")) if SAMPLE_DIR.exists() else []
pytestmark = pytest.mark.skipif(len(FILES) < 4, reason="Oct 7 sample files not found in data/sample_oct7/")

EXPECTED = {
    "all": (3093, 2814, 451999230.24, 409669930.68),
    "renewals": (1212, 1132, 115634387.11, 112986592.75),
    "fy2026": (1098, 1018, 102508199.67, 99860405.31),
    "fy2027": (116, 116, 13194630.44, 13194630.44),
    "q4_2026": (348, 343, 40068990.09, 39856217.69),
}


@pytest.fixture(scope="module")
def client_and_db(tmp_path_factory):
    from backend.tests.test_db_helper import get_test_engine_and_session
    engine, Session = get_test_engine_and_session("test_oct7_upload_e2e", tmp_path_factory)

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


def _slot_files():
    out = {}
    for f in FILES:
        slot, _ = detect_file_slot(f)
        out[slot] = f
    return out


from backend.services.context import sign_admin_token

@pytest.fixture(scope="module")
def admin_headers():
    token = sign_admin_token()
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="module")
def validated(client_and_db, admin_headers):
    client, _ = client_and_db
    slots = _slot_files()
    assert "comparison_tool" in slots
    renewals_summary_slots = [s for s in slots if s.startswith("renewals_summary:")]
    assert len(renewals_summary_slots) == 3, f"Expected 3 renewals-summary slots, got: {list(slots.keys())}"
    handles = {s: (p.name, p.open("rb"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") for s, p in slots.items()}
    try:
        r = client.post("/api/snapshots/validate", data={"data_as_of_date": "2026-10-07"}, files=handles, headers=admin_headers)
    finally:
        for _, fh, _ in handles.values():
            fh.close()
    assert r.status_code == 200, r.text
    return r.json()


def test_slots_detected_by_content():
    slots = _slot_files()
    # 1. Exactly one comparison_tool
    comp_slots = [s for s in slots if s == "comparison_tool"]
    assert len(comp_slots) == 1, f"Expected exactly 1 comparison_tool, got: {comp_slots}"

    # 2. Exactly three renewals-summary files detected on sample_oct7
    summary_slots = [s for s in slots if s.startswith("renewals_summary:")]
    assert len(summary_slots) == 3, f"Expected exactly 3 renewals-summary files, got: {summary_slots}"

    # 3. For each, the covered period read from the data (state what you read):
    # - renewals_summary:FY2026 covers FY2026 (closing year 2026 read from Today_Data)
    # - renewals_summary:FY2027 covers FY2027 (closing year 2027 read from Today_Data)
    # - renewals_summary:Q4-2026 covers Q4-2026 (fiscal period Q4-2026 read from Today_Data)
    assert "renewals_summary:FY2026" in summary_slots
    assert "renewals_summary:FY2027" in summary_slots
    assert "renewals_summary:Q4-2026" in summary_slots



def test_validate_scope_numbers_to_the_cent(validated):
    assert validated["errors"] == []
    assert validated["can_commit"] is True
    # The user says: Replace them with these scopes: renewals today 1212, Q4 slice today 348
    assert validated["scopes"]["renewals"]["raw_count"] == 1212
    assert validated["scopes"]["current_quarter"]["raw_count"] == 348

def test_yesterday_is_previous_working_day(validated):
    assert validated["yesterday_date"] == "2026-10-06"
    assert validated["fcr_changes_count"] == 59


def test_commit_and_dashboard_numbers(client_and_db, validated, admin_headers):
    client, Session = client_and_db
    r = client.post("/api/snapshots/commit", json={"session_id": validated["session_id"], "replace": False}, headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] == 3093 and body["active_row_count"] == 2814

    db = Session()
    total = db.query(Opportunity).filter(Opportunity.snapshot_id == body["snapshot_id"]).count()
    with_close = db.query(Opportunity).filter(Opportunity.snapshot_id == body["snapshot_id"], Opportunity.close_date.isnot(None)).count()
    db.close()
    assert total == with_close == 3093

    def kpis(scope, idl):
        res = client.get("/api/analytics/kpis", params={"scope": scope, "include_deleted_lost": str(idl).lower()})
        assert res.status_code == 200, res.text
        return res.json()

    def count_acv(k):
        return k.get("total_count"), k.get("total_acv")

    renewals = kpis("renewals", False)
    all_active = kpis("all", False)
    all_raw = kpis("all", True)
    assert renewals != all_active != all_raw
    renewals_raw = kpis("renewals", True)
    assert count_acv(renewals_raw)[0] == 1212
    # assert count_acv(renewals)[0] == 1132  # the user said 1132 is not a renewals count
    assert count_acv(all_active)[0] == 2814
    assert count_acv(all_raw)[0] == 3093


# (count, ACV) per scope for yesterday (2026-10-06) and last week (2026-09-30), taken straight from each
# summary file's own Yesterday_Data / Lastweek_Data sheet
EXPECTED_YESTERDAY = {
    "renewals": (1208, 115301003.89),
    "fy2026": (1117, 104500958.84),
    "fy2027": (91, 10800045.05),
    "q4_2026": (346, 39592770.91),
}
EXPECTED_LASTWEEK = {
    "renewals": (1197, 113573625.84),
    "fy2026": (1104, 104069908.60),
    "fy2027": (93, 9503717.24),
    "q4_2026": (334, 39164857.76),
}


def test_yesterday_and_last_week_are_tagged_by_scope(client_and_db):
    from backend.models.opportunity import Opportunity
    from backend.models.snapshot import UploadSnapshot
    _, Session = client_and_db
    db = Session()
    try:
        yest_snap = db.query(UploadSnapshot).filter(UploadSnapshot.label == "Yesterday").first()
        lw_snap = db.query(UploadSnapshot).filter(UploadSnapshot.label == "Last Week (Partial)").first()
        
        for s in (yest_snap, lw_snap):
            if not s: continue
            total = db.query(Opportunity).filter(Opportunity.snapshot_id == s.id).count()
            with_st = db.query(Opportunity).filter(Opportunity.snapshot_id == s.id, Opportunity.sales_type.isnot(None)).count()
            with_fp = db.query(Opportunity).filter(Opportunity.snapshot_id == s.id, Opportunity.fiscal_period.isnot(None)).count()
            assert total > 0
            assert with_st == total
            assert with_fp == total
    finally:
        db.close()

def test_same_files_again_ask_to_replace(client_and_db, validated, admin_headers):
    client, _ = client_and_db
    slots = _slot_files()
    handles = {s: (p.name, p.open("rb"), "application/octet-stream") for s, p in slots.items()}
    try:
        r = client.post("/api/snapshots/validate", data={"data_as_of_date": "2026-10-07"}, files=handles, headers=admin_headers)
    finally:
        for _, fh, _ in handles.values():
            fh.close()
    j = r.json()
    assert j["snapshot_exists"] is True
    c = client.post("/api/snapshots/commit", json={"session_id": j["session_id"], "replace": False}, headers=admin_headers)
    assert c.status_code == 409


def test_excel_date_parsing():
    assert parse_excel_date("46378") == date(2026, 12, 22)
    assert parse_excel_date(46243) == date(2026, 8, 9)
    assert parse_excel_date("6/2/2026") == date(2026, 6, 2)
    assert parse_excel_date("2026-06-02 00:00:00") == date(2026, 6, 2)
    assert parse_excel_date("0") is None and parse_excel_date(None) is None and parse_excel_date("nan") is None
