import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import os

from backend.main import app
from backend.database import Base, get_db
from backend.models.snapshot import UploadSnapshot
from backend.models.opportunity import Opportunity


@pytest.fixture(scope="module")
def client_and_db(tmp_path_factory):
    """Upload Oct-7 files and return TestClient + Session factory."""
    import pathlib, os
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_v2_regions.db")

    from fastapi.testclient import TestClient
    from backend.database import get_db
    from backend.main import app
    from backend.tests.test_db_helper import get_test_engine_and_session

    engine, Session = get_test_engine_and_session("test_v2_regions", tmp_path_factory)

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

        db = Session()
        snap = db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == date(2026, 10, 7)).first()
        if snap:
            opp = Opportunity(
                snapshot_id=snap.id,
                opportunity_id_18="006TESTUNMAPPEDREGION",
                opportunity_name="Test Unmapped Region",
                account_name="Test Unmapped Account",
                forecast_acv_amount=50000.0,
                forecast_category="Commit",
                approval_status="Pending Approval",
                business_unit_primary="Roaming",
                is_deleted_or_lost=False,
                fiscal_period="Q4-2026",
                close_date=date(2026, 11, 15),
                revised_sub_region="Antarctica", # Unmapped
                renewal_category="Renewal",
                sales_type="Renewals",
            )
            db.add(opp)
            db.commit()
        db.close()

        yield client, Session

    app.dependency_overrides.clear()

def test_regions_summary_total(client_and_db):
    client, _ = client_and_db
    r = client.get("/api/v2/regions/summary")
    assert r.status_code == 200
    d = r.json()
    assert "error" not in d
    assert d["data_slice"] == "Q4 FY26"
    assert d["data_slice_key"] == "Q4-2026"
    assert d["total"]["count"] == 349 # 348 + 1 unmapped
    assert round(d["total"]["acv"], 2) == 40118990.09 # 40068990.09 + 50000

def test_regions_summary_regions(client_and_db):
    client, _ = client_and_db
    r = client.get("/api/v2/regions/summary")
    d = r.json()
    regions = d["regions"]
    
    eur = next((r for r in regions if r["region"] == "Europe"), None)
    assert eur is not None
    assert eur["count"] == 158
    assert round(eur["acv"], 2) == 11103425.68

    mena = next((r for r in regions if r["region"] == "Middle East and North Africa"), None)
    assert mena is not None
    assert mena["count"] == 50

    apac = next((r for r in regions if r["region"] == "APAC"), None)
    assert apac is not None
    assert apac["count"] == 48

    na = next((r for r in regions if r["region"] == "North America"), None)
    assert na is not None
    assert na["count"] == 37

    latam = next((r for r in regions if r["region"] == "LATAM"), None)
    assert latam is not None
    assert latam["count"] == 32
    
    afr = next((r for r in regions if r["region"] == "Africa"), None)
    assert afr is not None
    assert afr["count"] == 23
    assert round(afr["acv"], 2) == 1592103.02

    # Check the unmapped
    other = next((r for r in regions if r["region"] == "Other"), None)
    assert other is not None
    assert other["count"] == 1
    assert other["acv"] == 50000.0
    
    unmapped = d["unmapped"]
    assert unmapped["count"] == 1
    assert unmapped["acv"] == 50000.0
    assert "Antarctica" in unmapped["values"]

def test_region_deals(client_and_db):
    client, _ = client_and_db
    r = client.get("/api/v2/regions/deals?region=Europe&category=Commit")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 148
    assert round(d["acv"], 2) == 10581230.77
    
    r = client.get("/api/v2/regions/deals")
    d = r.json()
    assert d["count"] == 349

def test_region_movements(client_and_db):
    client, _ = client_and_db
    r = client.get("/api/v2/regions/Europe/movements?compare=yesterday")
    assert r.status_code == 200
    d = r.json()
    assert "category_moves" in d
    assert "approval_moves" in d
    assert "new_to_slice" in d
    assert "slipped_out" in d

def test_top_opportunities(client_and_db):
    client, _ = client_and_db
    r = client.get("/api/v2/regions/Europe/top-opportunities")
    assert r.status_code == 200
    d = r.json()
    assert len(d) > 0
    assert "Telia" in d[0]["opportunity_name"]

def test_as_of_fix(client_and_db):
    client, _ = client_and_db
    
    r = client.get("/api/v2/regions/summary?as_of=2027-01-05")
    assert r.status_code == 200
    d = r.json()
    assert d["data_slice"] == "Q1 FY27"
    assert d["data_slice_key"] == "Q1-2027"
    assert d["requested_as_of"] == "2027-01-05"
    assert d["snapshot_date"] == "2026-10-07"
