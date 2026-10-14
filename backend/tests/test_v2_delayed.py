import pytest
from datetime import date
import pandas as pd

@pytest.fixture(scope="module")
def client_and_db(tmp_path_factory):
    """Upload Oct-7 files and return TestClient + Session factory."""
    import pathlib, os
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_v2_delayed.db")

    from fastapi.testclient import TestClient
    from backend.database import get_db
    from backend.main import app
    from backend.tests.test_db_helper import get_test_engine_and_session

    engine, Session = get_test_engine_and_session("test_v2_delayed", tmp_path_factory)

    def override_db():
        db = Session()
        try: yield db
        finally: db.close()

    app.dependency_overrides[get_db] = override_db

    from backend.utils.excel_parser import detect_file_slot
    sample = pathlib.Path("data/sample_oct7")
    slots = {}
    for fp in sorted(sample.glob("*.xlsx")):
        slots[detect_file_slot(fp)[0]] = fp

    with TestClient(app) as client:
        files = [(slot, (fp.name, open(fp, "rb"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")) for slot, fp in slots.items()]
        data = {"data_as_of_date": "2026-10-07", "yesterday_date": "2026-10-06"}
        vr = client.post("/api/snapshots/validate", data=data, files=files)
        assert vr.status_code == 200, vr.text
        session_id = vr.json()["session_id"]

        cr = client.post("/api/snapshots/commit", json={"session_id": session_id, "replace": False})
        assert cr.status_code == 200, cr.text

    yield TestClient(app), Session

def test_delayed_summary_yesterday(client_and_db):
    client, _ = client_and_db
    r = client.get("/api/v2/delayed/summary?compare=yesterday")
    assert r.status_code == 200
    d = r.json()
    assert d["data_slice"] == "Q4 FY26"
    assert "delayed_vs_yesterday" in d["total"]
    
    assert d["slipped"]["count"] == 2
    assert abs(d["slipped"]["acv"] - 59514.21) < 0.1
    
    # Overdue should be invariant of compare in its root stats
    assert d["overdue"]["count"] == 6
    assert abs(d["overdue"]["acv"] - 228071.49) < 0.1
    # Already overdue yesterday
    assert d["overdue"]["delayed_vs_yesterday"]["count"] == 5
    assert abs(d["overdue"]["delayed_vs_yesterday"]["acv"] - 226531.45) < 0.1

def test_delayed_summary_last_week(client_and_db):
    client, _ = client_and_db
    r = client.get("/api/v2/delayed/summary?compare=last_week")
    assert r.status_code == 200
    d = r.json()
    assert d["data_slice"] == "Q4 FY26"
    assert "delayed_vs_lastweek" in d["total"]

    assert d["slipped"]["count"] == 5
    assert abs(d["slipped"]["acv"] - 1315839.07) < 0.1
    
    # Total delayed vs last week (slipped + later close + overdue)
    assert d["total"]["count"] == 12
    assert abs(d["total"]["acv"] - 1595630.56) < 0.1
    
    # Already overdue last week (0 because all 6 deals have Close Dates in Oct > Sep 30)
    assert d["overdue"]["delayed_vs_lastweek"]["count"] == 0

def test_delayed_deals_endpoint(client_and_db):
    client, _ = client_and_db
    # Test a combination of filters to ensure they match summary output
    r = client.get("/api/v2/delayed/deals?compare=yesterday&kind=all&region=Europe&category=Commit")
    assert r.status_code == 200
    assert r.json()["count"] == 4
    
    r2 = client.get("/api/v2/delayed/deals?compare=yesterday&kind=overdue&region=Europe&category=Commit")
    assert r2.status_code == 200
    assert r2.json()["count"] == 3

    r3 = client.get("/api/v2/delayed/deals?compare=yesterday&kind=slipped&region=Europe&category=Commit")
    assert r3.status_code == 200
    assert r3.json()["count"] == 1
    
def test_lost_deals_endpoint(client_and_db):
    client, _ = client_and_db
    # Lost vs last week
    r = client.get("/api/v2/delayed/deals?compare=last_week&kind=lost")
    assert r.status_code == 200
    assert r.json()["count"] == 2
    assert abs(r.json()["acv"] - 60979.95) < 0.1

    # Lost vs yesterday is 0
    r_y = client.get("/api/v2/delayed/deals?compare=yesterday&kind=lost")
    assert r_y.json()["count"] == 0

    r_s = client.get("/api/v2/delayed/summary?compare=last_week")
    assert r_s.json()["lost"]["count"] == 2
    
def test_delayed_deals_no_snapshot(client_and_db):
    # Time travel to a date with NO compare snapshots
    client, _ = client_and_db
    r = client.get("/api/v2/delayed/deals?as_of=2000-01-01&compare=yesterday&kind=all")
    assert r.status_code == 200
    assert r.json()["count"] == 0
