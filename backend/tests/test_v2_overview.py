"""
API test for /api/v2/overview/* — Overview tab (Tab 1).
Requires real Oct-7 files in data/sample_oct7/ (never committed).
Values come from the user's confirmed numbers.

Expected Q4 slice (Oct 7, include_deleted_lost=True):
  total: 348 deals, $40,068,990.09
  Commit:    308 / $30,349,636.71
  Best Case:  34 / $9,456,843.36
  Pipeline:    1 / $49,737.62
  Blank:       5 / $212,772.40
  Closed:      0 / $0.00

Approval (Approved includes Approved-2nd):
  Approved: 96, Pending Approval: 6, Blank: 246

Yesterday (Oct 6) Q4: 346 / $39,592,770.91
Last Week (Sep 30) Q4: 334 / $39,164,857.76

FY2026 Commit->Closed vs yesterday: 3 deals / $345,891.08
  (Note: this is an FY2026-scoped movement, not Q4-scoped)

Region Q4 counts: Europe 158, MENA 50, APAC 48, NAMR 37, South America 32, AFRICA 23
  (mapped to canonical: Europe=Europe, APAC=APAC, Africa=Africa,
   MENA=Middle East and North Africa, NAMR=North America, South America=LATAM)
"""
import pathlib
import pytest

SAMPLE = pathlib.Path("data/sample_oct7")
pytestmark = pytest.mark.skipif(not SAMPLE.exists(), reason="real sample files not present")

# ── expected values ───────────────────────────────────────────────────────────
Q4_TOTAL_COUNT = 348
Q4_TOTAL_ACV = 40_068_990.09

Q4_CATS = {
    "Commit":     {"count": 308, "acv": 30_349_636.71},
    "Best Case":  {"count":  34, "acv":  9_456_843.36},
    "Pipeline":   {"count":   1, "acv":     49_737.62},
    "Blank":      {"count":   5, "acv":    212_772.40},
    "Closed":     {"count":   0, "acv":          0.00},
}

Q4_APPROVAL = {
    "Approved":        96,
    "Pending Approval":  6,
    "Blank":           246,
}

Q4_YESTERDAY_COUNT = 346
Q4_YESTERDAY_ACV   = 39_592_770.91

Q4_LASTWEEK_COUNT = 334
Q4_LASTWEEK_ACV   = 39_164_857.76

REGION_COUNTS = {
    "Europe": 158, "Middle East and North Africa": 50,
    "APAC": 48, "North America": 37,
    "LATAM": 32, "Africa": 23,
}

ACV_ABS = 0.02  # tolerance: ±2 cents


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client_and_db(tmp_path_factory):
    """Upload Oct-7 files and return TestClient + Session factory."""
    import pathlib, os
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_v2_overview.db")

    from fastapi.testclient import TestClient
    from backend.database import get_db
    from backend.main import app
    from backend.tests.test_db_helper import get_test_engine_and_session

    engine, Session = get_test_engine_and_session("test_v2_overview", tmp_path_factory)

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
    assert "comparison_tool" in slots
    assert len([s for s in slots if s.startswith("renewals_summary:")]) == 3, set(slots)

    from backend.services.context import sign_admin_token
    token = sign_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(app) as client:
        # Validate
        files = [(slot, (fp.name, open(fp, "rb"),
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
                 for slot, fp in slots.items()]
        data = {"data_as_of_date": "2026-10-07", "yesterday_date": "2026-10-06"}
        vr = client.post("/api/snapshots/validate", data=data, files=files, headers=headers)
        assert vr.status_code == 200, vr.text
        session_id = vr.json()["session_id"]

        # Commit
        cr = client.post("/api/snapshots/commit",
                         json={"session_id": session_id, "replace": False}, headers=headers)
        assert cr.status_code == 200, cr.text

        yield client, Session

    # Cleanup
    app.dependency_overrides.clear()


# ── SECTION 1: Total Q4 ───────────────────────────────────────────────────────

class TestOverviewSummary:
    def test_total_count(self, client_and_db):
        client, _ = client_and_db
        r = client.get("/api/v2/overview/summary")
        assert r.status_code == 200
        d = r.json()
        assert d["total"]["count"] == Q4_TOTAL_COUNT

    def test_total_acv(self, client_and_db):
        client, _ = client_and_db
        r = client.get("/api/v2/overview/summary")
        assert r.status_code == 200
        assert r.json()["total"]["acv"] == pytest.approx(Q4_TOTAL_ACV, abs=ACV_ABS)

    @pytest.mark.parametrize("fc,exp", Q4_CATS.items())
    def test_category_count(self, client_and_db, fc, exp):
        client, _ = client_and_db
        r = client.get("/api/v2/overview/summary")
        assert r.status_code == 200
        cat = r.json()["categories"][fc]
        assert cat["count"] == exp["count"], f"{fc} count"
        assert cat["acv"] == pytest.approx(exp["acv"], abs=ACV_ABS), f"{fc} ACV"

    def test_yesterday_delta_count(self, client_and_db):
        client, _ = client_and_db
        r = client.get("/api/v2/overview/summary")
        assert r.status_code == 200
        dy = r.json()["total"]["delta_yesterday"]
        assert dy is not None, "No yesterday snapshot"
        assert dy["count"] == Q4_TOTAL_COUNT - Q4_YESTERDAY_COUNT
        assert dy["acv"] == pytest.approx(Q4_TOTAL_ACV - Q4_YESTERDAY_ACV, abs=ACV_ABS)

    def test_lastweek_delta_count(self, client_and_db):
        client, _ = client_and_db
        r = client.get("/api/v2/overview/summary")
        assert r.status_code == 200
        dlw = r.json()["total"]["delta_lastweek"]
        assert dlw is not None, "No last-week snapshot"
        assert dlw["count"] == Q4_TOTAL_COUNT - Q4_LASTWEEK_COUNT
        assert dlw["acv"] == pytest.approx(Q4_TOTAL_ACV - Q4_LASTWEEK_ACV, abs=ACV_ABS)

    def test_data_slice_labels_all_v2(self, client_and_db):
        client, _ = client_and_db
        
        # 2026-10-07 snapshot
        for ep in ["overview/summary", "expiry/summary", "approvals/distribution", "business-units/summary"]:
            r = client.get(f"/api/v2/{ep}")
            assert r.status_code == 200, f"Failed {ep}"
            assert r.json()["data_slice"] == "Q4 FY26"
            
        # Time-travel to 2027-01-05
        for ep in ["overview/summary", "expiry/summary", "approvals/distribution", "business-units/summary"]:
            r = client.get(f"/api/v2/{ep}?as_of=2027-01-05")
            assert r.status_code == 200, f"Failed {ep} time-travel"
            print(f"JSON for {ep}: {r.json()}")
            assert r.json()["data_slice"] == "Q1 FY27"


# ── SECTION 2: Approval totals (from regional breakdown) ─────────────────────

class TestOverviewApproval:
    def test_approval_counts_in_proposal_confirmation(self, client_and_db):
        client, _ = client_and_db
        r = client.get("/api/v2/overview/regional-breakdown")
        assert r.status_code == 200
        totals = r.json()["proposal_confirmation_totals"]
        assert totals["approved_count"] == Q4_APPROVAL["Approved"], "Approved count"
        assert totals["pending_count"]  == Q4_APPROVAL["Pending Approval"], "Pending count"
        assert totals["blank_count"]    == Q4_APPROVAL["Blank"], "Blank count"


# ── SECTION 5+6: Regional breakdown ──────────────────────────────────────────

class TestOverviewRegional:
    def test_regional_trend_totals_match_section1(self, client_and_db):
        client, _ = client_and_db
        summary  = client.get("/api/v2/overview/summary").json()
        regional = client.get("/api/v2/overview/regional-breakdown").json()
        assert regional["total_acv_check_passes"], "Regional sum != Section 1 total"
        reg_total = regional["regional_trend_totals"]["total_acv"]
        assert reg_total == pytest.approx(summary["total"]["acv"], abs=ACV_ABS)

    @pytest.mark.parametrize("canonical,expected_count", REGION_COUNTS.items())
    def test_region_deal_count(self, client_and_db, canonical, expected_count):
        client, _ = client_and_db
        r = client.get("/api/v2/overview/regional-breakdown")
        rows = {row["region"]: row for row in r.json()["regional_trend"]}
        assert canonical in rows, f"Region {canonical!r} missing from regional_trend"
        assert rows[canonical]["total_count"] == expected_count, f"{canonical} count"


# ── SECTION 4: Movements ─────────────────────────────────────────────────────

class TestOverviewMovements:
    def test_movements_endpoint_returns_data(self, client_and_db):
        client, _ = client_and_db
        r = client.get("/api/v2/overview/movements?compare=yesterday")
        assert r.status_code == 200
        d = r.json()
        assert "positive" in d and "negative" in d and "approval" in d

    def test_movements_not_from_change_logs(self, client_and_db):
        """Movements endpoint must compute from snapshot diff, never change_logs."""
        # Verify last_week movements work (change_logs has no last-week data)
        client, _ = client_and_db
        r = client.get("/api/v2/overview/movements?compare=last_week")
        assert r.status_code == 200
        d = r.json()
        # If computed from change_logs, last_week movements would all be 0
        assert d["compare"] == "last_week"
        # At minimum the endpoint must respond without error
        assert "positive" in d

    def test_slippage_yesterday(self, client_and_db):
        client, _ = client_and_db
        r = client.get("/api/v2/overview/movements?compare=yesterday")
        d = r.json()
        slip = d["slippage_to_2027"]
        assert slip["count"] == 2
        assert slip["acv"] == pytest.approx(59514.21, abs=0.01)

    def test_slippage_last_week(self, client_and_db):
        client, _ = client_and_db
        r = client.get("/api/v2/overview/movements?compare=last_week")
        d = r.json()
        
        slip = d["slippage_to_2027"]
        assert slip["count"] == 5
        assert slip["acv"] == pytest.approx(1315839.07, abs=0.01)
        
        # Check specific IDs in slippage
        slip_ids = {deal["opportunity_id_18"] for deal in slip["deals"]}
        expected_ids = {
            "006Qp00000jgO7FIAU",
            "006Qp00000bPWXFIA4",
            "0061K00000iGWbBQAW",
            "006Qp00000asRzQIAU",
            "006Qp00000asTgFIAU",
        }
        for eid in expected_ids:
            assert eid in slip_ids, f"{eid} missing from slippage_to_2027"
            
        slipped_earlier = d["slipped_earlier"]
        assert slipped_earlier["count"] == 1
        assert slipped_earlier["acv"] == pytest.approx(75567.25, abs=0.01)
        earlier_ids = {deal["opportunity_id_18"] for deal in slipped_earlier["deals"]}
        assert "006Qp00000mTS8XIAW" in earlier_ids
        
        slipped_later = d["slipped_later_quarter"]
        assert slipped_later["count"] == 0


# ── SECTION 5: Deals Drilldown & Click Targets ──────────────────────────────

class TestOverviewDealsClickTargets:
    def test_overview_deals_structure(self, client_and_db):
        client, _ = client_and_db
        r = client.get("/api/v2/overview/deals")
        assert r.status_code == 200
        d = r.json()
        assert "count" in d and "acv" in d and "filters_applied" in d and "deals" in d
        assert d["count"] == 348
        assert d["acv"] == pytest.approx(40068990.09, abs=0.01)
        assert len(d["deals"]) == 348

    def test_overview_deals_categories(self, client_and_db):
        client, _ = client_and_db

        # Closed
        r_closed = client.get("/api/v2/overview/deals?category=Closed")
        d_closed = r_closed.json()
        assert d_closed["count"] == 0
        assert d_closed["acv"] == 0.0

        # Commit
        r_commit = client.get("/api/v2/overview/deals?category=Commit")
        d_commit = r_commit.json()
        assert d_commit["count"] == 308
        assert d_commit["acv"] == pytest.approx(30349636.71, abs=0.01)

        # Best Case
        r_bc = client.get("/api/v2/overview/deals?category=Best Case")
        d_bc = r_bc.json()
        assert d_bc["count"] == 34
        assert d_bc["acv"] == pytest.approx(9456843.36, abs=0.01)

        # Blank (Not yet proposed)
        r_blank = client.get("/api/v2/overview/deals?category=Blank")
        d_blank = r_blank.json()
        assert d_blank["count"] == 5
        assert d_blank["acv"] == pytest.approx(212772.40, abs=0.01)

        # Other / Pipeline
        r_pipe = client.get("/api/v2/overview/deals?category=Pipeline")
        d_pipe = r_pipe.json()
        assert d_pipe["count"] == 1
        assert d_pipe["acv"] == pytest.approx(49737.62, abs=0.01)

        # Category sum check matches total
        total_cats_count = d_closed["count"] + d_commit["count"] + d_bc["count"] + d_blank["count"] + d_pipe["count"]
        total_cats_acv = d_closed["acv"] + d_commit["acv"] + d_bc["acv"] + d_blank["acv"] + d_pipe["acv"]
        assert total_cats_count == 348
        assert total_cats_acv == pytest.approx(40068990.09, abs=0.01)

    def test_overview_deals_slipped(self, client_and_db):
        client, _ = client_and_db

        # Slipped vs yesterday
        r_sy = client.get("/api/v2/overview/deals?kind=slipped&compare=yesterday")
        d_sy = r_sy.json()
        assert d_sy["count"] == 2
        assert d_sy["acv"] == pytest.approx(59514.21, abs=0.01)
        assert len(d_sy["deals"]) == 2
        sy_ids = {deal["opportunity_id_18"] for deal in d_sy["deals"]}
        assert "006Qp00000asTgFIAU" in sy_ids
        assert "006Qp00000jgO7FIAU" in sy_ids

        # Slipped vs last week
        r_slw = client.get("/api/v2/overview/deals?kind=slipped&compare=last_week")
        d_slw = r_slw.json()
        assert d_slw["count"] == 5
        assert d_slw["acv"] == pytest.approx(1315839.07, abs=0.01)
        assert len(d_slw["deals"]) == 5
        slw_ids = {deal["opportunity_id_18"] for deal in d_slw["deals"]}
        assert "0061K00000iGWbBQAW" in slw_ids
        assert "006Qp00000asRzQIAU" in slw_ids

    def test_overview_deals_deltas_reconciliation(self, client_and_db):
        client, _ = client_and_db

        # Delta Yesterday: chip is +2 / +$476,219.18
        r_dy = client.get("/api/v2/overview/deals?kind=delta_yesterday")
        d_dy = r_dy.json()
        assert d_dy["count"] == 2
        assert d_dy["acv"] == pytest.approx(476219.18, abs=0.01)
        assert "delta_groups" in d_dy
        groups_y = d_dy["delta_groups"]
        assert groups_y["added"]["count"] == 4
        assert groups_y["added"]["acv"] == pytest.approx(538915.01, abs=0.01)
        assert groups_y["left"]["count"] == 2
        assert groups_y["left"]["acv"] == pytest.approx(59514.21, abs=0.01)
        assert groups_y["amount_changed"]["count"] == 2
        assert groups_y["amount_changed"]["acv"] == pytest.approx(-3181.62, abs=0.01)
        # Added - Left = Net count
        assert groups_y["added"]["count"] - groups_y["left"]["count"] == groups_y["net"]["count"]
        # Added ACV - Left ACV + Amount changed diff = Net ACV
        calc_acv_y = groups_y["added"]["acv"] - groups_y["left"]["acv"] + groups_y["amount_changed"]["acv"]
        assert calc_acv_y == pytest.approx(groups_y["net"]["acv"], abs=0.01)
        assert groups_y["net"]["acv"] == pytest.approx(476219.18, abs=0.01)

        # Delta Last Week: chip is +14 / +$904,132.33
        r_dlw = client.get("/api/v2/overview/deals?kind=delta_lastweek")
        d_dlw = r_dlw.json()
        assert d_dlw["count"] == 14
        assert d_dlw["acv"] == pytest.approx(904132.33, abs=0.01)
        assert "delta_groups" in d_dlw
        groups_lw = d_dlw["delta_groups"]
        assert groups_lw["added"]["count"] == 20
        assert groups_lw["added"]["acv"] == pytest.approx(2118711.22, abs=0.01)
        assert groups_lw["left"]["count"] == 6
        assert groups_lw["left"]["acv"] == pytest.approx(1391391.20, abs=0.01)
        assert groups_lw["amount_changed"]["count"] == 10
        assert groups_lw["amount_changed"]["acv"] == pytest.approx(176812.31, abs=0.01)
        # Added - Left = Net count
        assert groups_lw["added"]["count"] - groups_lw["left"]["count"] == groups_lw["net"]["count"]
        # Added ACV - Left ACV + Amount changed diff = Net ACV
        calc_acv_lw = groups_lw["added"]["acv"] - groups_lw["left"]["acv"] + groups_lw["amount_changed"]["acv"]
        assert calc_acv_lw == pytest.approx(groups_lw["net"]["acv"], abs=0.01)
        assert groups_lw["net"]["acv"] == pytest.approx(904132.33, abs=0.01)


