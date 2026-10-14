import pytest
from datetime import date
from backend.models.snapshot import UploadSnapshot

ACV_ABS = 0.01

@pytest.fixture(scope="module")
def client_and_db(tmp_path_factory):
    """Upload Oct-7 files and return TestClient + Session factory."""
    import pathlib, os
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_v2_business_units.db")

    from fastapi.testclient import TestClient
    from backend.database import get_db
    from backend.main import app
    from backend.tests.test_db_helper import get_test_engine_and_session

    engine, Session = get_test_engine_and_session("test_v2_business_units", tmp_path_factory)

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
        # Validate
        files = [(slot, (fp.name, open(fp, "rb"),
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
                 for slot, fp in slots.items()]
        data = {"data_as_of_date": "2026-10-07", "yesterday_date": "2026-10-06"}
        vr = client.post("/api/snapshots/validate", data=data, files=files)
        assert vr.status_code == 200, vr.text
        session_id = vr.json()["session_id"]

        # Commit
        cr = client.post("/api/snapshots/commit",
                         json={"session_id": session_id, "replace": False})
        assert cr.status_code == 200, cr.text

        yield client, Session()

    # Cleanup
    app.dependency_overrides.clear()

def test_bu_summary_oct7(client_and_db):
    client, db = client_and_db
    r = client.get("/api/v2/business-units/summary")
    assert r.status_code == 200
    d = r.json()

    assert d["data_slice_key"] == "Q4-2026"
    assert d["total"]["count"] == 348
    assert d["total"]["acv"] == pytest.approx(40068990.09, abs=ACV_ABS)

    rows = {r["bu"]: r for r in d["rows"]}
    
    # Assert today
    assert rows["Roaming"]["count"] == 86
    assert rows["Roaming"]["acv"] == pytest.approx(12469199.93, abs=ACV_ABS)
    assert rows["Testing"]["count"] == 166
    assert rows["Testing"]["acv"] == pytest.approx(10459935.58, abs=ACV_ABS)
    assert rows["Roaming; Security"]["count"] == 4
    assert rows["Roaming; Security"]["acv"] == pytest.approx(6067424.00, abs=ACV_ABS)
    assert rows["Risk"]["count"] == 66
    assert rows["Risk"]["acv"] == pytest.approx(5295599.20, abs=ACV_ABS)
    assert rows["Engagement and Experience"]["count"] == 7
    assert rows["Engagement and Experience"]["acv"] == pytest.approx(4326903.53, abs=ACV_ABS)
    assert rows["Security"]["count"] == 18
    assert rows["Security"]["acv"] == pytest.approx(1346965.40, abs=ACV_ABS)
    assert rows["Risk; Roaming"]["count"] == 1
    assert rows["Risk; Roaming"]["acv"] == pytest.approx(102962.45, abs=ACV_ABS)

    # Assert matrix counts
    assert rows["Roaming"]["cells"]["Best Case"]["count"] == 12
    assert rows["Roaming"]["cells"]["Blank"]["count"] == 2
    assert rows["Roaming"]["cells"]["Commit"]["count"] == 72
    assert rows["Roaming"]["cells"]["Pipeline"]["count"] == 0

    assert rows["Testing"]["cells"]["Best Case"]["count"] == 12
    assert rows["Testing"]["cells"]["Blank"]["count"] == 3
    assert rows["Testing"]["cells"]["Commit"]["count"] == 150
    assert rows["Testing"]["cells"]["Pipeline"]["count"] == 1

    # Assert matrix ACV
    assert rows["Roaming"]["cells"]["Best Case"]["acv"] == pytest.approx(1386929.98, abs=ACV_ABS)
    assert rows["Roaming"]["cells"]["Blank"]["acv"] == pytest.approx(146246.02, abs=ACV_ABS)
    assert rows["Roaming"]["cells"]["Commit"]["acv"] == pytest.approx(10936023.93, abs=ACV_ABS)

    assert rows["Testing"]["cells"]["Best Case"]["acv"] == pytest.approx(1624565.77, abs=ACV_ABS)
    assert rows["Testing"]["cells"]["Blank"]["acv"] == pytest.approx(66526.38, abs=ACV_ABS)
    assert rows["Testing"]["cells"]["Commit"]["acv"] == pytest.approx(8719105.81, abs=ACV_ABS)
    assert rows["Testing"]["cells"]["Pipeline"]["acv"] == pytest.approx(49737.62, abs=ACV_ABS)

    assert rows["Roaming; Security"]["cells"]["Best Case"]["acv"] == pytest.approx(4968375.00, abs=ACV_ABS)
    assert rows["Roaming; Security"]["cells"]["Commit"]["acv"] == pytest.approx(1099049.00, abs=ACV_ABS)

    # Deltas vs yesterday
    # Roaming +2 / +351,774.65 ; Testing -1 / -22,736.61 ; Engagement and Experience +1 / +147,181.14
    dy = rows["Roaming"]["delta_yesterday"]
    assert dy["count"] == 2
    assert dy["acv"] == pytest.approx(351774.65, abs=ACV_ABS)
    
    dt = rows["Testing"]["delta_yesterday"]
    assert dt["count"] == -1
    assert dt["acv"] == pytest.approx(-22736.61, abs=ACV_ABS)
    
    de = rows["Engagement and Experience"]["delta_yesterday"]
    assert de["count"] == 1
    assert de["acv"] == pytest.approx(147181.14, abs=ACV_ABS)

    # Deltas vs last week
    # Roaming +6 / +525,274.74 ; Risk +3 / +307,814.87 ; Testing +5 / -13,744.66 ; Engagement and Experience 0 / +84,787.38
    dlw = rows["Roaming"]["delta_lastweek"]
    assert dlw["count"] == 6
    assert dlw["acv"] == pytest.approx(525274.74, abs=ACV_ABS)

    dlwr = rows["Risk"]["delta_lastweek"]
    assert dlwr["count"] == 3
    assert dlwr["acv"] == pytest.approx(307814.87, abs=ACV_ABS)
    
    dlwt = rows["Testing"]["delta_lastweek"]
    assert dlwt["count"] == 5
    assert dlwt["acv"] == pytest.approx(-13744.66, abs=ACV_ABS)
    
    dlwe = rows["Engagement and Experience"]["delta_lastweek"]
    assert dlwe["count"] == 0
    assert dlwe["acv"] == pytest.approx(84787.38, abs=ACV_ABS)

def test_bu_deals_roaming_commit(client_and_db):
    client, _ = client_and_db
    r = client.get("/api/v2/business-units/deals?bu=Roaming&category=Commit")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 72
    assert d["acv"] == pytest.approx(10936023.93, abs=ACV_ABS)

def test_bu_deals_roaming_security(client_and_db):
    client, _ = client_and_db
    r = client.get("/api/v2/business-units/deals?bu=Roaming;%20Security")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 4
    assert d["acv"] == pytest.approx(6067424.00, abs=ACV_ABS)
    
def test_bu_deals_no_filter(client_and_db):
    client, _ = client_and_db
    r = client.get("/api/v2/business-units/deals")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 348
    assert d["acv"] == pytest.approx(40068990.09, abs=ACV_ABS)

def test_bu_exclude_deleted(client_and_db):
    client, _ = client_and_db
    r = client.get("/api/v2/business-units/summary?exclude_deleted_lost=true")
    assert r.status_code == 200
    d = r.json()
    # It should succeed without error, though all Q4 deals are likely not deleted
    assert "rows" in d

def test_bu_empty_slice(client_and_db):
    client, _ = client_and_db
    # Pass a time-travel date where the slice is empty or no snapshots exist
    r = client.get("/api/v2/business-units/summary?as_of=2024-01-01")
    assert r.status_code == 200
    d = r.json()
    # If no snapshot, returns error code payload OR empty totals
    if "error" not in d:
        assert d["total"]["count"] == 0

def test_bu_time_travel_2027(client_and_db):
    client, db = client_and_db
    # Insert a dummy snap for 2027-01-05
    from backend.models.snapshot import UploadSnapshot
    snap = UploadSnapshot(snapshot_date=date(2027,1,5), label="Dummy", is_active_today=False)
    db.add(snap)
    db.commit()
    
    r = client.get("/api/v2/business-units/summary?as_of=2027-01-05")
    assert r.status_code == 200
    d = r.json()
    assert d["data_slice_key"] == "Q1-2027"

def test_top_opportunities(client_and_db):
    client, _ = client_and_db
    r = client.get("/api/v2/business-units/top-opportunities?bu=Roaming")
    assert r.status_code == 200
    d = r.json()
    deals = d["deals"]
    assert len(deals) > 0
    assert deals[0]["opportunity_name"] == "Docomo GRP Roaming Platform Support Extension 2027 OPEX"
    assert deals[0]["account_name"] == "NTT Docomo Japan"
    assert deals[0]["forecast_acv_amount"] == pytest.approx(1000000.0, abs=ACV_ABS)
    assert deals[0]["forecast_category"] == "Commit"
    if len(deals) > 1:
        assert "TPG - Roaming Platform Managed Service" in deals[1]["opportunity_name"]
        assert deals[1]["forecast_acv_amount"] == pytest.approx(858986.59, abs=ACV_ABS)
