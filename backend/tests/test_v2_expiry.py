import pytest
import pathlib
from datetime import date
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import get_db
from backend.utils.excel_parser import detect_file_slot

client = TestClient(app)

@pytest.fixture(scope="module")
def client_and_db(tmp_path_factory):
    from backend.tests.test_db_helper import get_test_engine_and_session
    engine, Session = get_test_engine_and_session("test_v2_expiry", tmp_path_factory)
    
    def override_db():
        db = Session()
        try: yield db
        finally: db.close()

    app.dependency_overrides[get_db] = override_db

    sample = pathlib.Path("data/sample_oct7")
    slots = {}
    for fp in sorted(sample.glob("*.xlsx")):
        slots[detect_file_slot(fp)[0]] = fp
    assert "comparison_tool" in slots
    assert len([s for s in slots if s.startswith("renewals_summary:")]) == 3, set(slots)

    from backend.services.context import sign_admin_token
    token = sign_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(app) as test_client:
        files = [(slot, (fp.name, open(fp, "rb"),
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
                 for slot, fp in slots.items()]
        data = {"data_as_of_date": "2026-10-07", "yesterday_date": "2026-10-06"}
        vr = test_client.post("/api/snapshots/validate", data=data, files=files, headers=headers)
        assert vr.status_code == 200, vr.text
        session_id = vr.json()["session_id"]

        cr = test_client.post("/api/snapshots/commit",
                         json={"session_id": session_id, "replace": False}, headers=headers)
        assert cr.status_code == 200, cr.text

        yield test_client

class TestExpirySummary:
    def test_full_grid(self, client_and_db):
        res = client_and_db.get("/api/v2/expiry/summary?exclude_deleted_lost=false")
        assert res.status_code == 200
        d = res.json()
        
        g26 = d["grids"]["2026"]
        g27 = d["grids"]["2027"]
        
        q1_26 = next(r for r in g26["rows"] if r["quarter"] == "Q1-2026")
        assert q1_26["cells"]["Best Case"]["count"] == 7
        assert q1_26["cells"]["Closed"]["count"] == 193
        assert q1_26["cells"]["Commit"]["count"] == 5
        assert q1_26["cells"]["Pipeline"]["count"] == 1
        assert q1_26["total"]["count"] == 206
        assert q1_26["total"]["acv"] == 15562415.66
        
        q4_26 = next(r for r in g26["rows"] if r["quarter"] == "Q4-2026")
        assert q4_26["cells"]["Best Case"]["count"] == 81
        assert q4_26["cells"]["Closed"]["count"] == 43
        assert q4_26["cells"]["Commit"]["count"] == 279
        assert q4_26["cells"]["Pipeline"]["count"] == 7
        assert q4_26["total"]["count"] == 410
        assert q4_26["total"]["acv"] == 52134488.49
        
        assert g26["totals"]["grand"]["count"] == 941
        assert g26["totals"]["grand"]["acv"] == 100657985.75
        
        assert g27["totals"]["grand"]["count"] == 16
        assert g27["totals"]["grand"]["acv"] == 1869207.49
        
        assert d["grand_total"]["count"] == 957
        assert d["grand_total"]["acv"] == 102527193.24
        
        assert d["slippage"]["count"] == 105
        assert d["slippage"]["acv"] == 12415568.47
        
        # Verify row sums == column sums == grand total
        total_row_count = sum(r["total"]["count"] for r in g26["rows"]) + sum(r["total"]["count"] for r in g27["rows"])
        total_col_count = sum(c["count"] for c in g26["totals"]["category"].values()) + sum(c["count"] for c in g27["totals"]["category"].values())
        assert total_row_count == d["grand_total"]["count"]
        assert total_col_count == d["grand_total"]["count"]

        # Category ACV totals: Best Case 17,371,360.19, Closed 50,184,576.91, Commit 33,274,667.84, Pipeline 1,696,588.30
        assert round(g26["totals"]["category"]["Best Case"]["acv"] + g27["totals"]["category"]["Best Case"]["acv"], 2) == 17371360.19
        assert round(g26["totals"]["category"]["Closed"]["acv"] + g27["totals"]["category"]["Closed"]["acv"], 2) == 50184576.91
        assert round(g26["totals"]["category"]["Commit"]["acv"] + g27["totals"]["category"]["Commit"]["acv"], 2) == 33274667.84
        assert round(g26["totals"]["category"]["Pipeline"]["acv"] + g27["totals"]["category"]["Pipeline"]["acv"], 2) == 1696588.30

        # Last-week deltas present
        assert "lastweek" in d["deltas"]["2026"]
        
    def test_exclude_deleted_lost(self, client_and_db):
        res = client_and_db.get("/api/v2/expiry/summary?exclude_deleted_lost=false")
        d_incl = res.json()
        
        res = client_and_db.get("/api/v2/expiry/summary?exclude_deleted_lost=true")
        d_excl = res.json()
        
        assert d_excl["grand_total"]["count"] <= d_incl["grand_total"]["count"]
        assert d_excl["grand_total"]["acv"] <= d_incl["grand_total"]["acv"]
        
        g26 = d_excl["grids"]["2026"]
        g27 = d_excl["grids"]["2027"]
        total_row_count = sum(r["total"]["count"] for r in g26["rows"]) + sum(r["total"]["count"] for r in g27["rows"])
        total_col_count = sum(c["count"] for c in g26["totals"]["category"].values()) + sum(c["count"] for c in g27["totals"]["category"].values())
        assert total_row_count == d_excl["grand_total"]["count"]
        assert total_col_count == d_excl["grand_total"]["count"]

    def test_time_travel(self, client_and_db):
        res = client_and_db.get("/api/v2/expiry/summary?exclude_deleted_lost=false&as_of=2027-01-05")
        # Time travel tests logic here if we need it
        
    def test_deals(self, client_and_db):
        res = client_and_db.get("/api/v2/expiry/deals?quarter=Q1-2026&category=Closed&exclude_deleted_lost=false")
        assert res.status_code == 200
        deals = res.json()
        assert len(deals) == 193
        acv = round(sum(d.get("forecast_acv_amount", 0) for d in deals), 2)
        assert acv == 14591997.17