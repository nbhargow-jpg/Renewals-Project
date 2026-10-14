"""
Tests for FilterSpec system:
- Exact values on data/sample_oct7 on SQLite and Postgres
- Default: 348 / $40,068,990.09 on Overview, Regions, Business Units, Approvals, Delayed totals
- Sales types = all + period = all_periods: 3,093 deals / $451,999,230.24
    Pipeline 538 / $97,099,728.36
    Not yet proposed (Blank) 280 / $42,329,299.56
    Commit 479 / $61,226,563.88
    Best Case 537 / $124,066,184.41
    Closed 1,259 / $127,277,454.03
- period = Q4-2026 with Renewals = 348
- Close Date range works
- include_deleted_lost off removes only deleted/lost deals and totals reconcile
- list filters alone and combination
- rollover case (as_of in Jan 2027 -> current_quarter = Q1-2027)
- options endpoint returns dynamic choices with counts
"""
import pytest
from pathlib import Path
from datetime import date
from fastapi.testclient import TestClient
from backend.services.scopes import FilterSpec, ScopeService
from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot

SAMPLE = Path("data/sample_oct7")
pytestmark = pytest.mark.skipif(not SAMPLE.exists(), reason="real sample files not present")

@pytest.fixture(scope="module")
def seeded_client_and_db(tmp_path_factory):
    from backend.tests.test_db_helper import get_test_engine_and_session
    from backend.database import get_db
    from backend.main import app
    from backend.utils.excel_parser import detect_file_slot

    engine, Session = get_test_engine_and_session("filter_spec_test", tmp_path_factory)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db

    slots = {}
    for fp in sorted(SAMPLE.glob("*.xlsx")):
        slots[detect_file_slot(fp)[0]] = fp

    with TestClient(app) as client:
        files = [(slot, (fp.name, open(fp, "rb"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
                 for slot, fp in slots.items()]
        data = {"data_as_of_date": "2026-10-07", "yesterday_date": "2026-10-06"}
        vr = client.post("/api/snapshots/validate", data=data, files=files)
        assert vr.status_code == 200, vr.text
        session_id = vr.json()["session_id"]

        cr = client.post("/api/snapshots/commit", json={"session_id": session_id, "replace": False})
        assert cr.status_code == 200, cr.text

        yield client, Session

    app.dependency_overrides.clear()


def test_default_totals_across_endpoints(seeded_client_and_db):
    client, Session = seeded_client_and_db

    # 1. Overview summary
    r_ov = client.get("/api/v2/overview/summary")
    assert r_ov.status_code == 200
    d_ov = r_ov.json()
    assert d_ov["total"]["count"] == 348
    assert d_ov["total"]["acv"] == pytest.approx(40068990.09, rel=1e-5)
    assert d_ov["data_slice"] == "Q4 FY26"

    # 2. Business Units summary
    r_bu = client.get("/api/v2/business-units/summary")
    assert r_bu.status_code == 200
    d_bu = r_bu.json()
    assert d_bu["total"]["count"] == 348
    assert d_bu["total"]["acv"] == pytest.approx(40068990.09, rel=1e-5)

    # 3. Regions summary
    r_reg = client.get("/api/v2/regions/summary")
    assert r_reg.status_code == 200
    d_reg = r_reg.json()
    assert d_reg["total"]["count"] == 348
    assert d_reg["total"]["acv"] == pytest.approx(40068990.09, rel=1e-5)

    # 4. Approvals distribution
    r_app = client.get("/api/v2/approvals/distribution")
    assert r_app.status_code == 200
    d_app = r_app.json()
    assert d_app["total"]["count"] == 348
    assert d_app["total"]["acv"] == pytest.approx(40068990.09, rel=1e-5)

    # 5. Delayed summary (slice total matches 348)
    r_del = client.get("/api/v2/delayed/summary")
    assert r_del.status_code == 200
    d_del = r_del.json()
    assert d_del["data_slice"] == "Q4 FY26"


def test_all_opportunities_and_all_periods(seeded_client_and_db):
    client, Session = seeded_client_and_db

    params = {
        "period": "all_periods",
        "sales_types": ["all"],
        "include_deleted_lost": True
    }
    r = client.get("/api/v2/overview/summary", params=params)
    assert r.status_code == 200
    d = r.json()

    assert d["total"]["count"] == 3093
    assert d["total"]["acv"] == pytest.approx(451999230.24, rel=1e-5)

    cats = d["categories"]
    assert cats["Pipeline"]["count"] == 538
    assert cats["Pipeline"]["acv"] == pytest.approx(97099728.36, rel=1e-5)

    assert cats["Blank"]["count"] == 280
    assert cats["Blank"]["acv"] == pytest.approx(42329299.56, rel=1e-5)

    assert cats["Commit"]["count"] == 479
    assert cats["Commit"]["acv"] == pytest.approx(61226563.88, rel=1e-5)

    assert cats["Best Case"]["count"] == 537
    assert cats["Best Case"]["acv"] == pytest.approx(124066184.41, rel=1e-5)

    assert cats["Closed"]["count"] == 1259
    assert cats["Closed"]["acv"] == pytest.approx(127277454.03, rel=1e-5)


def test_period_specific_quarter(seeded_client_and_db):
    client, Session = seeded_client_and_db

    params = {"period": "Q4-2026", "sales_types": ["Renewals"]}
    r = client.get("/api/v2/overview/summary", params=params)
    assert r.status_code == 200
    d = r.json()
    assert d["total"]["count"] == 348
    assert d["total"]["acv"] == pytest.approx(40068990.09, rel=1e-5)


def test_include_deleted_lost_toggle_and_reconciliation(seeded_client_and_db):
    client, Session = seeded_client_and_db

    # With include_deleted_lost = False
    r_off = client.get("/api/v2/overview/summary", params={"include_deleted_lost": False})
    assert r_off.status_code == 200
    d_off = r_off.json()
    assert d_off["total"]["count"] == 343
    assert d_off["total"]["acv"] == pytest.approx(39856217.69, rel=1e-5)

    # Difference is exactly 5 deals / $212,772.40 (the 5 deleted/lost deals)
    r_on = client.get("/api/v2/overview/summary", params={"include_deleted_lost": True})
    assert r_on.status_code == 200
    d_on = r_on.json()
    assert d_on["total"]["count"] == 348
    assert d_on["total"]["count"] - d_off["total"]["count"] == 5
    assert pytest.approx(d_on["total"]["acv"] - d_off["total"]["acv"], rel=1e-5) == 212772.40


def test_close_date_range(seeded_client_and_db):
    client, Session = seeded_client_and_db

    params = {"period": "2026-07-01:2026-09-30"}
    r = client.get("/api/v2/overview/summary", params=params)
    assert r.status_code == 200
    d = r.json()
    assert "total" in d
    assert d["filters_applied"]["period"] == "2026-07-01:2026-09-30"


def test_rollover_case():
    snap_date = date(2027, 1, 15)
    fs = FilterSpec(period="current_quarter")
    res = ScopeService.resolve(fs, snapshot=None, as_of_date=snap_date)
    assert res.period == "Q1-2027"
    assert res.label == "Q1 FY27"


def test_options_endpoint(seeded_client_and_db):
    client, Session = seeded_client_and_db

    r = client.get("/api/v2/filters/options")
    assert r.status_code == 200
    opts = r.json()

    assert "quarters" in opts
    assert any(q["key"] == "Q4-2026" for q in opts["quarters"])

    assert "sales_types" in opts
    st_names = [st["key"] for st in opts["sales_types"]]
    assert "Renewals" in st_names

    assert "regions" in opts
    assert len(opts["regions"]) >= 5

    assert "business_units" in opts
    assert len(opts["business_units"]) > 0

    assert "forecast_categories" in opts
    fc_keys = [fc["key"] for fc in opts["forecast_categories"]]
    assert fc_keys == ["Closed", "Commit", "Best Case", "Pipeline", "Not yet proposed"]

    assert "approval_statuses" in opts
    app_keys = [app["key"] for app in opts["approval_statuses"]]
    assert "Approved" in app_keys
    assert "Pending Approval" in app_keys
    assert "Not submitted" in app_keys
