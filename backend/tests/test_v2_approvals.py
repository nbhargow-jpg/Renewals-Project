import pytest
import pathlib
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db
from backend.utils.excel_parser import detect_file_slot

@pytest.fixture(scope="module")
def client_and_db(tmp_path_factory):
    from backend.tests.test_db_helper import get_test_engine_and_session
    engine, Session = get_test_engine_and_session("test_v2_approvals", tmp_path_factory)
    
    def override_db():
        db = Session()
        try: yield db
        finally: db.close()

    app.dependency_overrides[get_db] = override_db

    sample = pathlib.Path("data/sample_oct7")
    slots = {}
    for fp in sorted(sample.glob("*.xlsx")):
        slots[detect_file_slot(fp)[0]] = fp

    with TestClient(app) as test_client:
        files = [(slot, (fp.name, open(fp, "rb"),
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
                 for slot, fp in slots.items()]
        data = {"data_as_of_date": "2026-10-07", "yesterday_date": "2026-10-06"}
        vr = test_client.post("/api/snapshots/validate", data=data, files=files)
        assert vr.status_code == 200, vr.text
        session_id = vr.json()["session_id"]

        cr = test_client.post("/api/snapshots/commit",
                         json={"session_id": session_id, "replace": False})
        assert cr.status_code == 200, cr.text

        yield test_client

def test_v2_approvals_oct7(client_and_db):
    res = client_and_db.get("/api/v2/approvals/distribution?as_of=2026-10-07&exclude_deleted_lost=false")
    assert res.status_code == 200
    d = res.json()
    assert "error" not in d
    
    assert d["total"]["count"] == 348
    assert d["total"]["acv"] == 40068990.09
    
    stats = {s["status"]: s for s in d["statuses"]}
    assert "Blank" in stats
    assert stats["Blank"]["count"] == 246
    assert stats["Blank"]["acv"] == 31192259.04
    
    assert "Approved" in stats
    assert stats["Approved"]["count"] == 96
    assert stats["Approved"]["acv"] == 8571916.50
    assert stats["Approved"]["delta_yesterday"]["count"] == 96 - 88
    assert round(stats["Approved"]["delta_yesterday"]["acv"] - (8571916.50 - 8158081.51), 2) == 0.0
    assert stats["Approved"]["delta_lastweek"]["count"] == 96 - 73
    assert round(stats["Approved"]["delta_lastweek"]["acv"] - (8571916.50 - 6172895.93), 2) == 0.0

    assert "Pending Approval" in stats
    assert stats["Pending Approval"]["count"] == 6
    assert stats["Pending Approval"]["acv"] == 304814.55
    assert stats["Pending Approval"]["delta_yesterday"]["count"] == 6 - 7
    assert round(stats["Pending Approval"]["delta_yesterday"]["acv"] - (304814.55 - 405102.02), 2) == 0.0
    assert stats["Pending Approval"]["delta_lastweek"]["count"] == 6 - 4
    assert round(stats["Pending Approval"]["delta_lastweek"]["acv"] - (304814.55 - 1464342.36), 2) == 0.0

    mat = d["matrix"]
    assert mat["Approved"]["Best Case"]["count"] == 13
    assert mat["Approved"]["Commit"]["count"] == 83
    assert mat["Pending Approval"]["Best Case"]["count"] == 1
    assert mat["Pending Approval"]["Commit"]["count"] == 5
    assert mat["Blank"]["Best Case"]["count"] == 20
    assert mat["Blank"]["Blank"]["count"] == 5
    assert mat["Blank"]["Commit"]["count"] == 220
    assert mat["Blank"]["Pipeline"]["count"] == 1
    
    # Tests for get_deals
    def check_deals(qs, count, acv):
        res = client_and_db.get(f"/api/v2/approvals/deals?as_of=2026-10-07&exclude_deleted_lost=false{qs}")
        d = res.json()
        assert d["count"] == count
        assert round(d["acv"], 2) == round(acv, 2)
        assert len(d["deals"]) == count

    check_deals("&status=Blank&category=Commit", 220, 23303174.90)
    check_deals("&status=Blank&category=Blank", 5, 212772.40)
    check_deals("&status=Approved", 96, 8571916.50)
    check_deals("&status=Approved&category=Best Case", 13, 1812016.90)
    check_deals("&status=Pending Approval", 6, 304814.55)
    check_deals("", 348, 40068990.09)

def test_v2_approvals_time_travel(client_and_db):
    res = client_and_db.get("/api/v2/approvals/distribution?as_of=2027-01-05&exclude_deleted_lost=false")
    assert res.status_code == 200

def test_v2_approvals_empty(client_and_db):
    res = client_and_db.get("/api/v2/approvals/distribution?as_of=2020-01-01&exclude_deleted_lost=false")
    d = res.json()
    assert "error" in d or d.get("total", {}).get("count") == 0

def test_v2_approvals_exclude_deleted(client_and_db):
    res = client_and_db.get("/api/v2/approvals/distribution?as_of=2026-10-07&exclude_deleted_lost=true")
    d = res.json()
    assert "error" not in d
    assert d["total"]["count"] <= 348
