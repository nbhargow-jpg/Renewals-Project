"""
Tests for Addendum B (Excel Control Reconciliation), Addendum C (Lifetime-Proof Ingestion & Schema Drift),
and Addendum D (Admin-Only Upload Security).
"""
import os
import shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import openpyxl

from backend.main import app
from backend.database import get_db
from backend.services.context import sign_admin_token
from backend.services.reconciliation import ReconciliationEngine
from backend.utils.excel_parser import detect_file_slot, parse_comparison_tool, parse_renewals_summary

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
def admin_headers(setup_admin_env):
    token = sign_admin_token()
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="module")
def client_and_db(tmp_path_factory, setup_admin_env):
    from backend.tests.test_db_helper import get_test_engine_and_session
    engine, Session = get_test_engine_and_session("test_addenda_bcd", tmp_path_factory)

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


# ==============================================================================
# ADDENDUM B: SOURCE RECONCILIATION AGAINST EXCEL'S OWN SUMMARY SHEETS
# ==============================================================================

@pytest.mark.skipif(len(FILES) < 4, reason="Oct 7 sample files not found")
def test_addendum_b_exact_number_of_checks_match_sample_oct7():
    """
    On sample_oct7, exactly 28 checks run across the Comparison Tool and Renewals Summary workbooks.
    All 28 must pass with status == 'pass'.
    """
    from backend.utils.excel_parser import parse_comparison_tool, parse_summary_workbook, _map_columns

    files_dict = {}
    comp_sheets = {}
    summary_dfs = {}
    today_mapped = None
    yesterday_mapped = None

    for f in FILES:
        slot, _ = detect_file_slot(f)
        files_dict[slot] = f
        if slot == "comparison_tool":
            comp = parse_comparison_tool(f)
            comp_sheets = comp
            today_mapped = _map_columns(comp["today"])
            yesterday_mapped = _map_columns(comp["yesterday"])
        else:
            summary_dfs[slot] = parse_summary_workbook(f)

    engine = ReconciliationEngine()
    checks = engine.run_all_checks(
        snapshot_id="test_oct7",
        files_dict=files_dict,
        comp_sheets=comp_sheets,
        summary_dfs=summary_dfs,
        today_mapped=today_mapped,
        yesterday_mapped=yesterday_mapped,
    )

    passed_count = sum(1 for c in checks if c.status == "pass")
    failed_count = sum(1 for c in checks if c.status == "fail")

    assert len(checks) == 196, f"Expected exactly 196 checks on sample_oct7, got {len(checks)}"
    assert passed_count == 196, f"Expected 196 passed checks, got {passed_count}"
    assert failed_count == 0, f"Expected 0 failed checks, got {failed_count}"


@pytest.mark.skipif(len(FILES) < 4, reason="Oct 7 sample files not found")
def test_addendum_b_doctored_workbook_mismatch_names_sheet_cell_values(tmp_path):
    """
    Doctored copy of a Renewals Summary workbook:
    Mutate a specific control cell (Today_Expiry sheet, Commit row Today Count).
    Assert that:
    1. Upload / check does NOT fail or crash.
    2. Status is 'fail' / badge 'red'.
    3. The mismatch identifies the EXACT sheet ('Today_Expiry'), cell/row, Excel value, and website value.
    """
    from backend.utils.excel_parser import parse_comparison_tool, parse_summary_workbook, _map_columns

    # Setup files dict
    files_dict = {}
    comp_sheets = {}
    summary_dfs = {}
    today_mapped = None
    yesterday_mapped = None

    # Find the Q4 summary file and copy/doctor it
    q4_file = None
    for f in FILES:
        slot, _ = detect_file_slot(f)
        if slot == "fiscal_q4" or "q4" in f.name.lower():
            q4_file = f
            break
    assert q4_file is not None

    doctored_q4 = tmp_path / q4_file.name
    shutil.copyfile(q4_file, doctored_q4)

    wb = openpyxl.load_workbook(doctored_q4)
    sheet = wb["Today_Expiry"]
    # Row 3 is Commit in Today_Expiry; column D is Today Count (308). Mutate to 999.
    orig_val = sheet["D3"].value
    assert orig_val == 308, f"Expected 308 in D3, found {orig_val}"
    sheet["D3"] = 999
    wb.save(doctored_q4)

    for f in FILES:
        slot, _ = detect_file_slot(f)
        if f == q4_file:
            files_dict[slot] = doctored_q4
            summary_dfs[slot] = parse_summary_workbook(doctored_q4)
        elif slot == "comparison_tool":
            files_dict[slot] = f
            comp = parse_comparison_tool(f)
            comp_sheets = comp
            today_mapped = _map_columns(comp["today"])
            yesterday_mapped = _map_columns(comp["yesterday"])
        else:
            files_dict[slot] = f
            summary_dfs[slot] = parse_summary_workbook(f)

    engine = ReconciliationEngine()
    checks = engine.run_all_checks(
        snapshot_id="test_doctored",
        files_dict=files_dict,
        comp_sheets=comp_sheets,
        summary_dfs=summary_dfs,
        today_mapped=today_mapped,
        yesterday_mapped=yesterday_mapped,
    )

    failed_checks = [c for c in checks if c.status == "fail"]
    assert len(failed_checks) >= 1, f"Expected at least 1 failed check, got {len(failed_checks)}"

    found = False
    for m in failed_checks:
        if m.sheet_name == "Today_Expiry" and "D3" in m.cell_or_row:
            assert m.excel_value == "999"
            assert m.website_value == "308"
            found = True
            break

    assert found, f"Expected mismatch at Today_Expiry D3 with excel=999, website=308. Mismatches found: {[c.cell_or_row for c in failed_checks]}"


# ==============================================================================
# ADDENDUM C: LIFETIME-PROOF INGESTION & TWO-WAY SCHEMA DRIFT
# ==============================================================================

def test_addendum_c_two_way_schema_drift():
    """
    Validate that two-way schema drift warns both:
    1. When a new column appears.
    2. When a known column disappears vs previous snapshot.
    """
    from backend.services.ingest_service import detect_schema_drift

    previous_cols = ["Opportunity ID", "Opportunity Name", "ACV", "Forecast Category", "Region"]
    
    # 1. New column appears: "Risk Score"
    new_cols_1 = ["Opportunity ID", "Opportunity Name", "ACV", "Forecast Category", "Region", "Risk Score"]
    warnings_1 = detect_schema_drift(new_cols_1, previous_cols)
    assert any("New column 'Risk Score' detected" in w for w in warnings_1)

    # 2. Known column disappears: "ACV" disappears
    new_cols_2 = ["Opportunity ID", "Opportunity Name", "Forecast Category", "Region"]
    warnings_2 = detect_schema_drift(new_cols_2, previous_cols)
    assert any("Known column 'ACV' disappeared" in w for w in warnings_2)


def test_addendum_c_unknown_region_and_new_forecast_category(client_and_db, admin_headers):
    """
    - A new unknown region maps to "Other" with a visible notice / banner count.
    - A new forecast category gets handled without crashing.
    """
    from datetime import date
    from backend.models.opportunity import Opportunity
    from backend.models.snapshot import UploadSnapshot

    client, Session = client_and_db
    db = Session()
    snap = UploadSnapshot(snapshot_date=date(2026, 11, 1), label="Nov 1", is_active_today=True)
    db.add(snap)
    db.commit()

    # Insert an opportunity with an unknown region "Antarctica" and a new forecast category "Upsell Stretch"
    opp = Opportunity(
        snapshot_id=snap.id,
        opportunity_id_18="006000000000001AAA",
        opportunity_name="Polar Project",
        forecast_category="Upsell Stretch",
        sub_region="Antarctica",
        revised_sub_region="",  # Blank/unmapped revised_sub_region maps to Other
        forecast_acv_amount=150000.0,
        sales_type="Renewals",
        fiscal_period="Q4-2026",
    )
    db.add(opp)
    db.commit()
    db.close()

    r = client.get("/api/v2/overview/summary?as_of=2026-11-01")
    assert r.status_code == 200
    data = r.json()
    assert data["other_region_count"] >= 1
    assert "Upsell Stretch" in data["categories"]
    assert data["categories"]["Upsell Stretch"]["count"] == 1
    assert data["categories"]["Upsell Stretch"]["acv"] == 150000.0


# ==============================================================================
# ADDENDUM D: ADMIN-ONLY MUTATING ROUTES & AUTH SECURITY
# ==============================================================================

def get_all_mutating_routes():
    """Discover all POST, PUT, PATCH, DELETE routes from app."""
    routes = []
    for inc in app.routes:
        if hasattr(inc, "original_router") and hasattr(inc, "include_context"):
            prefix = inc.include_context.prefix or ""
            for r in inc.original_router.routes:
                if hasattr(r, "methods"):
                    for m in r.methods:
                        if m in {"POST", "PUT", "PATCH", "DELETE"}:
                            routes.append((m, f"{prefix}{r.path}"))
        elif hasattr(inc, "methods"):
            for m in inc.methods:
                if m in {"POST", "PUT", "PATCH", "DELETE"}:
                    routes.append((m, getattr(inc, "path", "")))
    return sorted(list(set(routes)))


def test_addendum_d_mutating_routes_require_admin(client_and_db, admin_headers):
    """
    Every mutating route must return 401 without an Authorization header,
    403 with an invalid token, and 403 with an expired token.
    Public read routes stay 200 without token.
    Discovers all mutating routes dynamically from app.routes.
    """
    client, _ = client_and_db

    # 1. Public read routes stay public
    r_public = client.get("/api/snapshots")
    assert r_public.status_code == 200

    r_public_v2 = client.get("/api/v2/overview/summary")
    assert r_public_v2.status_code == 200

    mutating_routes = get_all_mutating_routes()
    # Exempt non-admin auth routes (login/logout), read-style AI assistant queries,
    # and Explorer query/export routes (Explorer prompt explicitly states: "Admin is not required for reading or exporting.")
    exempt_paths = {
        "/api/admin/login",
        "/admin/login",
        "/api/ai/ask",
        "/ai/ask",
        "/api/ai/chat/stream",
        "/ai/chat/stream",
        "/v2/explorer/rows",
        "/api/v2/explorer/rows",
        "/v2/explorer/export",
        "/api/v2/explorer/export",
        "/v2/explorer/reconcile",
        "/api/v2/explorer/reconcile",
    }
    write_routes = [(m, p) for m, p in mutating_routes if p not in exempt_paths]

    assert len(write_routes) >= 4, f"Expected at least 4 write routes, found {len(write_routes)}"

    # Generate an expired token
    import time, json, base64, hmac, hashlib
    from backend.config import settings

    payload_expired = {
        "sub": "admin",
        "role": "admin",
        "exp": int(time.time()) - 3600,  # 1 hour ago
        "iat": int(time.time()) - 7200,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload_expired).encode("utf-8")).decode("utf-8").rstrip("=")
    key = settings.ADMIN_SECRET_KEY.encode("utf-8")
    sig = hmac.new(key, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")
    expired_token = f"{payload_b64}.{sig_b64}"

    bad_headers = {"Authorization": "Bearer bad-token-12345"}
    expired_headers = {"Authorization": f"Bearer {expired_token}"}

    for method, path in write_routes:
        test_path = path.replace("{snapshot_id}", "fake-snapshot-id-123")

        # 1. Without auth header -> 401
        r_no_auth = client.request(method, test_path)
        assert r_no_auth.status_code == 401, f"{method} {path} expected 401 unauthenticated, got {r_no_auth.status_code}"

        # 2. With invalid token -> 403
        r_bad = client.request(method, test_path, headers=bad_headers)
        assert r_bad.status_code == 403, f"{method} {path} expected 403 with bad token, got {r_bad.status_code}"

        # 3. With expired token -> 403
        r_exp = client.request(method, test_path, headers=expired_headers)
        assert r_exp.status_code == 403, f"{method} {path} expected 403 with expired token, got {r_exp.status_code}"

        # 4. With valid admin token -> passes auth (status != 401 and != 403)
        r_valid = client.request(method, test_path, headers=admin_headers)
        assert r_valid.status_code not in (401, 403), f"{method} {path} failed auth with valid token: {r_valid.status_code}"


def test_addendum_d_unconfigured_admin_blocks_writes(client_and_db):
    """
    If ADMIN_PASSWORD or ADMIN_SECRET_KEY is unset or default,
    write routes return 403 and /api/admin/status reports is_configured=False.
    """
    client, _ = client_and_db
    from backend.config import settings

    orig_pw = settings.ADMIN_PASSWORD
    orig_key = settings.ADMIN_SECRET_KEY
    try:
        # Case 1: Empty password
        settings.ADMIN_PASSWORD = ""
        r_stat = client.get("/api/admin/status")
        assert r_stat.status_code == 200
        assert r_stat.json()["is_configured"] is False

        r_val = client.post("/api/snapshots/validate")
        assert r_val.status_code == 403
        assert "not configured" in r_val.json()["detail"].lower()

        # Case 2: Placeholder secret key
        settings.ADMIN_PASSWORD = "my-secret-password"
        settings.ADMIN_SECRET_KEY = "supersecret_renewals_admin_signing_key_change_in_prod"
        r_stat2 = client.get("/api/admin/status")
        assert r_stat2.json()["is_configured"] is False

        r_val2 = client.post("/api/snapshots/validate")
        assert r_val2.status_code == 403
        assert "not configured" in r_val2.json()["detail"].lower()
    finally:
        settings.ADMIN_PASSWORD = orig_pw
        settings.ADMIN_SECRET_KEY = orig_key


def test_addendum_d_password_never_logged_or_returned(client_and_db, caplog):
    """
    Password must NEVER appear in logs or HTTP responses,
    both during failed attempts and successful logins.
    """
    import logging
    client, _ = client_and_db
    from backend.config import settings

    secret_pw = settings.ADMIN_PASSWORD

    with caplog.at_level(logging.DEBUG):
        # 1. Failed login attempt
        r_fail = client.post("/api/admin/login", json={"password": "wrong-password-attempt"})
        assert r_fail.status_code == 401
        assert secret_pw not in r_fail.text
        assert "wrong-password-attempt" not in caplog.text
        assert secret_pw not in caplog.text

        caplog.clear()

        # 2. Successful login attempt
        r_ok = client.post("/api/admin/login", json={"password": secret_pw})
        assert r_ok.status_code == 200
        body = r_ok.json()
        assert "token" in body
        assert secret_pw not in r_ok.text
        assert secret_pw not in caplog.text

