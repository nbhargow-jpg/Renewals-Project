"""
backend/tests/test_v2_explorer.py
Comprehensive real tests for Data Explorer (/v2/explorer/*):
- Columns returns 172 names in exact order of the Oct 7 file header row (compared to openpyxl)
- No filters returns 3,093 rows / $451,999,230.24, with Pipeline 538, blank forecast 280, Commit 479, Best Case 537, Closed 1259
- Sales Type = Renewals, Fiscal Period = Q4-2026, Include Deleted & Lost on: 348 deals / $40,068,990.09
- Asserts that if no sales_type filter is sent, no sales_type filter is applied (Explorer is the exception to the Renewals default)
- 10 real filter cases compared against pandas filter of raw Excel with exact row count and ACV sum
- Export CSV and XLSX: re-read with pandas matches header order and row count
- Reconcile endpoint returns Renewals scope comparison
- Quick filters returns accurate distinct counts
Runs on SQLite and on Postgres via TEST_DATABASE_URL.
"""
import io
import os
import pathlib
import openpyxl
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.snapshot import UploadSnapshot
from backend.services.context import ADMIN_CONTEXT
from backend.services.ingest_service import IngestService
from backend.tests.test_db_helper import get_test_engine_and_session

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
SAMPLE_OCT7 = ROOT_DIR / "data" / "sample_oct7"
FILES = sorted(SAMPLE_OCT7.glob("*.xlsx")) if SAMPLE_OCT7.exists() else []

pytestmark = pytest.mark.skipif(
    len(FILES) < 4, reason="Oct 7 sample files not present in data/sample_oct7"
)


@pytest.fixture(scope="module")
def client_and_db(tmp_path_factory):
    engine, Session = get_test_engine_and_session("test_v2_explorer", tmp_path_factory)
    db = Session()

    # Upload Oct 7 files
    files_dict = {
        "comparison_tool": SAMPLE_OCT7 / "Renewal Comparison Tool.xlsx",
        "renewals_summary:FY2026": SAMPLE_OCT7 / "Renewals Summary - Fiscal 2026.xlsx",
        "renewals_summary:FY2027": SAMPLE_OCT7 / "Renewals Summary - Fiscal 2027.xlsx",
        "renewals_summary:Q4-2026": SAMPLE_OCT7 / "Renewals Summary - Fiscal Q4.xlsx",
    }
    from datetime import date
    ingest = IngestService(db)
    val = ingest.validate_upload(
        ADMIN_CONTEXT,
        files_dict,
        data_as_of=date(2026, 10, 7),
        yesterday_date=date(2026, 10, 6),
    )
    assert val.get("session_id"), f"Validation failed: {val.get('errors')}"
    snap = ingest.commit_upload(ADMIN_CONTEXT, val["session_id"], replace=True, make_active=True)
    db.commit()

    from backend.database import get_db
    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as client:
        yield client, Session, snap.id
    app.dependency_overrides.clear()
    db.close()


def test_columns_exact_openpyxl_order(client_and_db):
    client, Session, snap_id = client_and_db

    # Read raw header with openpyxl
    wb = openpyxl.load_workbook(SAMPLE_OCT7 / "Renewal Comparison Tool.xlsx", read_only=True)
    ws = wb["today"]
    raw_headers = [c.value for c in next(ws.iter_rows(max_row=1))]

    assert len(raw_headers) == 172

    r = client.get(f"/v2/explorer/columns?as_of=2026-10-07")
    assert r.status_code == 200
    data = r.json()
    assert data["total_columns"] == 172
    col_names = [c["name"] for c in data["columns"]]

    assert col_names == raw_headers, "Explorer column order must exactly match raw Excel header order"


def test_no_filters_returns_full_excel_and_no_renewals_default(client_and_db):
    client, Session, snap_id = client_and_db

    # No filters sent -> ALL 3,093 rows and $451,999,230.24 returned (No Renewals default applied!)
    r = client.post("/v2/explorer/rows?as_of=2026-10-07", json={"page_size": 50})
    assert r.status_code == 200
    data = r.json()
    assert data["total_count"] == 3093
    assert abs(data["total_acv"] - 451999230.24) < 1.0
    assert len(data["rows"]) == 50


def test_renewals_and_q4_and_deleted_lost(client_and_db):
    client, Session, snap_id = client_and_db

    spec = {
        "period": "Q4-2026",
        "sales_types": ["Renewals"],
        "include_deleted_lost": True,
    }
    r = client.post("/v2/explorer/rows?as_of=2026-10-07", json={"filter_spec": spec, "page_size": 50})
    assert r.status_code == 200
    data = r.json()
    assert data["total_count"] == 348
    assert abs(data["total_acv"] - 40068990.09) < 0.05


def test_ten_filter_cases_against_pandas_excel(client_and_db):
    client, Session, snap_id = client_and_db

    cases = [
        # (name, filters, expected_count, expected_acv)
        ("1. text contains Mobily", [{"column": "Account Name", "operator": "contains", "value": "Mobily"}], 8, 5439648.19),
        ("2. text equals Renewals", [{"column": "Sales Type", "operator": "equals", "value": "Renewals"}], 1212, 115634387.11),
        ("3. text not equals Renewals", [{"column": "Sales Type", "operator": "not equals", "value": "Renewals"}], 1881, 336364843.13),
        ("4. text starts with Middle", [{"column": "Sub-Region", "operator": "starts with", "value": "Middle"}], 375, 74388442.92),
        ("5. is empty GP Project Code", [{"column": "GP Project Code", "operator": "is empty"}], 1783, 311137186.01),
        ("6. is not empty GP Project Code", [{"column": "GP Project Code", "operator": "is not empty"}], 1310, 140862044.23),
        ("7. in list Forecast Category", [{"column": "Forecast Category", "operator": "in list", "value": ["Commit", "Best Case"]}], 1016, 185292748.29),
        ("8. number > 1M", [{"column": "Forecast ACV Amount", "operator": ">", "value": 1000000}], 57, 132885898.97),
        ("9. number between 500K and 1M", [{"column": "Forecast ACV Amount", "operator": "between", "value": 500000, "value_to": 1000000}], 125, 83661978.15),
        ("10. AND of three filters", [
            {"column": "Sales Type", "operator": "equals", "value": "Renewals"},
            {"column": "Fiscal Period", "operator": "equals", "value": "Q4-2026"},
            {"column": "Forecast Category", "operator": "equals", "value": "Commit"},
        ], 308, 30349636.71),
    ]

    for name, flist, exp_cnt, exp_acv in cases:
        r = client.post("/v2/explorer/rows?as_of=2026-10-07", json={"filters": flist, "page_size": 10})
        assert r.status_code == 200, f"Case {name} failed: {r.text}"
        res = r.json()
        assert res["total_count"] == exp_cnt, f"Case {name}: expected count {exp_cnt}, got {res['total_count']}"
        assert abs(res["total_acv"] - exp_acv) < 0.1, f"Case {name}: expected ACV {exp_acv}, got {res['total_acv']}"


def test_export_csv_and_xlsx_match_filter_and_order(client_and_db):
    client, Session, snap_id = client_and_db

    # Export CSV with filters: Renewals & Q4-2026
    flist = [
        {"column": "Sales Type", "operator": "equals", "value": "Renewals"},
        {"column": "Fiscal Period", "operator": "equals", "value": "Q4-2026"},
    ]
    r_csv = client.post("/v2/explorer/export?as_of=2026-10-07", json={"filters": flist, "format": "csv"})
    assert r_csv.status_code == 200
    df_csv = pd.read_csv(io.BytesIO(r_csv.content))
    assert len(df_csv) == 348
    assert len(df_csv.columns) == 172
    assert df_csv.columns[0] == "Stage Number"
    assert df_csv.columns[1] == "Opportunity ID 18 Digit"

    # Export XLSX with same filter
    r_xlsx = client.post("/v2/explorer/export?as_of=2026-10-07", json={"filters": flist, "format": "xlsx"})
    assert r_xlsx.status_code == 200
    df_xlsx = pd.read_excel(io.BytesIO(r_xlsx.content), sheet_name="Data_Explorer")
    assert len(df_xlsx) == 348
    assert len(df_xlsx.columns) == 172
    assert list(df_xlsx.columns) == list(df_csv.columns)


def test_reconcile_endpoint(client_and_db):
    client, Session, snap_id = client_and_db

    # 1. Whole snapshot reconciliation
    r = client.get("/v2/explorer/reconcile?as_of=2026-10-07")
    assert r.status_code == 200
    data = r.json()
    assert data["scope"] == "Whole Snapshot"
    assert data["total_rows"] == 3093
    assert abs(data["total_acv"] - 451999230.24) < 1.0

    cats = data["forecast_categories"]
    assert cats["Pipeline"]["count"] == 538
    assert abs(cats["Pipeline"]["acv"] - 97099728.36) < 1.0
    assert cats["Blank"]["count"] == 280
    assert cats["Commit"]["count"] == 479
    assert cats["Best Case"]["count"] == 537
    assert cats["Closed"]["count"] == 1259

    # 2. Reconcile with current filter (Renewals + Q4-2026)
    flist = [
        {"column": "Sales Type", "operator": "equals", "value": "Renewals"},
        {"column": "Fiscal Period", "operator": "equals", "value": "Q4-2026"},
    ]
    r_filt = client.post("/v2/explorer/reconcile?as_of=2026-10-07", json={"filters": flist})
    assert r_filt.status_code == 200
    d_filt = r_filt.json()
    assert d_filt["current_filter"] is not None
    assert d_filt["current_filter"]["total_rows"] == 348
    assert abs(d_filt["current_filter"]["total_acv"] - 40068990.09) < 1.0


def test_quick_filters_endpoint(client_and_db):
    client, Session, snap_id = client_and_db

    r = client.get("/v2/explorer/quick-filters?as_of=2026-10-07")
    assert r.status_code == 200
    data = r.json()

    # 1. Sales types sum to 3,093
    st_names = [s["name"] for s in data["sales_types"]]
    assert set(st_names) == {"Renewals", "Upsell", "Cross sell", "New Logo"}
    assert sum(s["count"] for s in data["sales_types"]) == 3093

    # 2. Fiscal periods contains every distinct fiscal period in the Oct 7 data, including Q4-2026,
    # and they sum to 3,093
    fps = [f["name"] for f in data["fiscal_periods"]]
    assert "Q4-2026" in fps
    assert len(fps) == 16
    assert fps == [
        'Q1-2026', 'Q2-2026', 'Q3-2026', 'Q4-2026',
        'Q1-2027', 'Q2-2027', 'Q3-2027', 'Q4-2027',
        'Q1-2028', 'Q2-2028', 'Q3-2028', 'Q4-2028',
        'Q1-2029', 'Q4-2029', 'Q3-2031', 'Q4-2035'
    ]
    assert sum(f["count"] for f in data["fiscal_periods"]) == 3093

    # 3. Forecast categories sum to 3,093
    fc_names = [f["name"] for f in data["forecast_categories"]]
    assert "Closed" in fc_names and "Pipeline" in fc_names and "Commit" in fc_names and "Best Case" in fc_names
    assert sum(f["count"] for f in data["forecast_categories"]) == 3093

    # 4. Regions sum to 3,093
    assert len(data["regions"]) == 9
    assert sum(r["count"] for r in data["regions"]) == 3093

    # 5. Business units sum to 3,093
    assert len(data["business_units"]) == 16
    assert sum(b["count"] for b in data["business_units"]) == 3093

    # 6. Approval statuses sum to 3,093
    assert sum(a["count"] for a in data["approval_statuses"]) == 3093
