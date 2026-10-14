"""
test_analytics.py — asserts the Oct 5 reference numbers from the spec.

All assertions are against values computed FROM THE RAW DATA by our code.
The pivot/summary sheets are not read.
"""
import pytest
from backend.services.analytics_service import AnalyticsService
from backend.services.context import ADMIN_CONTEXT

# ------------------------------------------------------------------ #
# Reference numbers from the spec (Oct 5 2026)
# ------------------------------------------------------------------ #

# Grand total ACV for the expiry-pivot scope (1,167 opportunities)
REF_EXPIRY_PIVOT_ACV = 120_511_647.51
REF_EXPIRY_PIVOT_COUNT = 1_167

# Approval status (all 3,086 rows)
REF_TOTAL_ROWS = 3_086
REF_APPROVAL_APPROVED = 748
REF_APPROVAL_APPROVED_2ND = 877
REF_APPROVAL_PENDING = 31
REF_APPROVAL_BLANK = 1_411
REF_APPROVAL_REJECTED = 19
REF_APPROVAL_ACV_TOTAL = 450_040_250.54   # Exact to the cent!

# Exact Approval ACV per status (Oct 5)
REF_APPROVAL_APPROVED_ACV = 95_793_389.47
REF_APPROVAL_APPROVED_2ND_ACV = 86_981_910.94
REF_APPROVAL_PENDING_ACV = 11_000_202.55
REF_APPROVAL_BLANK_ACV = 246_458_479.25
REF_APPROVAL_REJECTED_ACV = 9_806_268.33

# Forecast category counts
REF_FORECAST_CLOSED = 1_245
REF_FORECAST_COMMIT = 488
REF_FORECAST_BEST_CASE = 547
REF_FORECAST_PIPELINE = 538
REF_FORECAST_BLANK = 268

# Exact Forecast Category ACV (Oct 5)
REF_FORECAST_CLOSED_ACV = 124_716_887.79
REF_FORECAST_COMMIT_ACV = 62_209_347.81
REF_FORECAST_BEST_CASE_ACV = 129_321_882.47
REF_FORECAST_PIPELINE_ACV = 92_623_466.32
REF_FORECAST_BLANK_ACV = 41_168_666.15


def _get_svc(seeded_session):
    return AnalyticsService(seeded_session)


class TestTotalRowCount:
    def test_today_total_rows(self, seeded_session):
        svc = _get_svc(seeded_session)
        kpis = svc.get_kpis(ADMIN_CONTEXT)
        assert kpis["total_count"] == REF_TOTAL_ROWS, (
            f"Expected {REF_TOTAL_ROWS} rows, got {kpis['total_count']}"
        )


class TestForecastCategories:
    @pytest.fixture(autouse=True)
    def _setup(self, seeded_session):
        svc = _get_svc(seeded_session)
        self.summary = svc.get_approval_status(ADMIN_CONTEXT)  # has all rows
        self.kpis = svc.get_kpis(ADMIN_CONTEXT)
        # Build forecast breakdown directly
        from backend.models.opportunity import Opportunity
        from backend.models.snapshot import UploadSnapshot
        snap = (
            seeded_session.query(UploadSnapshot)
            .filter_by(is_active_today=True)
            .first()
        )
        opps = seeded_session.query(Opportunity).filter_by(snapshot_id=snap.id).all()
        from collections import Counter
        self.fc_counts = Counter(o.forecast_category or "Blank" for o in opps)
        self.fc_acvs = {}
        for o in opps:
            c = o.forecast_category or "Blank"
            self.fc_acvs[c] = round(self.fc_acvs.get(c, 0.0) + float(o.forecast_acv_amount or 0), 2)

    def test_closed_count(self):
        assert self.fc_counts["Closed"] == REF_FORECAST_CLOSED, (
            f"Closed: expected {REF_FORECAST_CLOSED}, got {self.fc_counts['Closed']}"
        )

    def test_commit_count(self):
        assert self.fc_counts["Commit"] == REF_FORECAST_COMMIT, (
            f"Commit: expected {REF_FORECAST_COMMIT}, got {self.fc_counts['Commit']}"
        )

    def test_best_case_count(self):
        assert self.fc_counts["Best Case"] == REF_FORECAST_BEST_CASE, (
            f"Best Case: expected {REF_FORECAST_BEST_CASE}, got {self.fc_counts['Best Case']}"
        )

    def test_pipeline_count(self):
        assert self.fc_counts["Pipeline"] == REF_FORECAST_PIPELINE, (
            f"Pipeline: expected {REF_FORECAST_PIPELINE}, got {self.fc_counts['Pipeline']}"
        )

    def test_blank_count(self):
        assert self.fc_counts["Blank"] == REF_FORECAST_BLANK, (
            f"Blank: expected {REF_FORECAST_BLANK}, got {self.fc_counts['Blank']}"
        )

    def test_forecast_count_totals_to_3086(self):
        total = sum(self.fc_counts.values())
        assert total == REF_TOTAL_ROWS, f"Total forecast count: expected {REF_TOTAL_ROWS}, got {total}"

    def test_forecast_acv_per_category_exact(self):
        """Assert exact ACV to the cent for each forecast category and exact sum to total"""
        print(f"\n[Forecast Counts] Closed: {self.fc_counts['Closed']:,} | Commit: {self.fc_counts['Commit']:,} | Best Case: {self.fc_counts['Best Case']:,} | Pipeline: {self.fc_counts['Pipeline']:,} | Blank: {self.fc_counts['Blank']:,}")
        assert self.fc_counts["Closed"] == 1245
        assert self.fc_counts["Commit"] == 488
        assert self.fc_counts["Best Case"] == 547
        assert self.fc_counts["Pipeline"] == 538
        assert self.fc_counts["Blank"] == 268

        assert round(self.fc_acvs["Closed"], 2) == REF_FORECAST_CLOSED_ACV
        assert round(self.fc_acvs["Commit"], 2) == REF_FORECAST_COMMIT_ACV
        assert round(self.fc_acvs["Best Case"], 2) == REF_FORECAST_BEST_CASE_ACV
        assert round(self.fc_acvs["Pipeline"], 2) == REF_FORECAST_PIPELINE_ACV
        assert round(self.fc_acvs["Blank"], 2) == REF_FORECAST_BLANK_ACV

        cat_sum = round(
            REF_FORECAST_CLOSED_ACV +
            REF_FORECAST_COMMIT_ACV +
            REF_FORECAST_BEST_CASE_ACV +
            REF_FORECAST_PIPELINE_ACV +
            REF_FORECAST_BLANK_ACV,
            2,
        )
        assert cat_sum == REF_APPROVAL_ACV_TOTAL


class TestApprovalStatus:
    @pytest.fixture(autouse=True)
    def _setup(self, seeded_session):
        from backend.models.opportunity import Opportunity
        from backend.models.snapshot import UploadSnapshot
        snap = (
            seeded_session.query(UploadSnapshot)
            .filter_by(is_active_today=True)
            .first()
        )
        opps = seeded_session.query(Opportunity).filter_by(snapshot_id=snap.id).all()
        from collections import Counter
        self.status_counts = Counter(o.approval_status or "Blank" for o in opps)
        self.status_acvs = {}
        for o in opps:
            st = o.approval_status or "Blank"
            self.status_acvs[st] = round(self.status_acvs.get(st, 0.0) + float(o.forecast_acv_amount or 0), 2)
        self.total_acv = sum(float(o.forecast_acv_amount or 0) for o in opps)

    def test_approved_count(self):
        assert self.status_counts["Approved"] == REF_APPROVAL_APPROVED, (
            f"Approved: expected {REF_APPROVAL_APPROVED}, got {self.status_counts['Approved']}"
        )

    def test_approved_2nd_count(self):
        assert self.status_counts["Approved - 2nd"] == REF_APPROVAL_APPROVED_2ND, (
            f"Approved-2nd: expected {REF_APPROVAL_APPROVED_2ND}, got {self.status_counts['Approved - 2nd']}"
        )

    def test_pending_count(self):
        assert self.status_counts["Pending Approval"] == REF_APPROVAL_PENDING, (
            f"Pending: expected {REF_APPROVAL_PENDING}, got {self.status_counts['Pending Approval']}"
        )

    def test_blank_count(self):
        assert self.status_counts["Blank"] == REF_APPROVAL_BLANK, (
            f"Blank: expected {REF_APPROVAL_BLANK}, got {self.status_counts['Blank']}"
        )

    def test_rejected_count(self):
        assert self.status_counts["Rejected"] == REF_APPROVAL_REJECTED, (
            f"Rejected: expected {REF_APPROVAL_REJECTED}, got {self.status_counts['Rejected']}"
        )

    def test_approval_status_sums_to_3086(self):
        total = sum(self.status_counts.values())
        assert total == REF_TOTAL_ROWS, f"Approval total: expected {REF_TOTAL_ROWS}, got {total}"

    def test_approval_acv_total(self):
        """Assert exact total ACV to the cent: $450,040,250.54"""
        assert round(self.total_acv, 2) == REF_APPROVAL_ACV_TOTAL, (
            f"Approval ACV: expected exact {REF_APPROVAL_ACV_TOTAL}, got {round(self.total_acv, 2)}"
        )

    def test_approval_acv_per_status_exact(self):
        """Assert exact ACV to the cent for each approval status and exact sum to total"""
        assert round(self.status_acvs["Approved"], 2) == REF_APPROVAL_APPROVED_ACV
        assert round(self.status_acvs["Approved - 2nd"], 2) == REF_APPROVAL_APPROVED_2ND_ACV
        assert round(self.status_acvs["Pending Approval"], 2) == REF_APPROVAL_PENDING_ACV
        assert round(self.status_acvs["Blank"], 2) == REF_APPROVAL_BLANK_ACV
        assert round(self.status_acvs["Rejected"], 2) == REF_APPROVAL_REJECTED_ACV

        five_sum = round(
            REF_APPROVAL_APPROVED_ACV +
            REF_APPROVAL_APPROVED_2ND_ACV +
            REF_APPROVAL_PENDING_ACV +
            REF_APPROVAL_BLANK_ACV +
            REF_APPROVAL_REJECTED_ACV,
            2,
        )
        assert five_sum == REF_APPROVAL_ACV_TOTAL


class TestExpiryPivotScope:
    """
    Expiry Q3 Summary pivot exact assertions for Oct 5 2026 snapshot.
    Rule:
      (a) Service Expiry Period is one of Q1-2026 .. Q4-2027
      (b) Forecast Category is not blank.
    """

    EXPECTED_QUARTERS = {
        "Q1-2026": {"acv": 24_945_874.66, "count": 266},
        "Q1-2027": {"acv": 3_289_137.52, "count": 13},
        "Q2-2026": {"acv": 20_973_514.23, "count": 257},
        "Q2-2027": {"acv": 434_901.89, "count": 3},
        "Q3-2026": {"acv": 18_132_885.71, "count": 197},
        "Q3-2027": {"acv": 56_284.56, "count": 3},
        "Q4-2026": {"acv": 52_675_598.94, "count": 427},
        "Q4-2027": {"acv": 3_450.00, "count": 1},
    }

    def test_oct5_expiry_pivot_exact_totals(self, seeded_session):
        svc = _get_svc(seeded_session)
        res = svc.get_expiry_quarters(ADMIN_CONTEXT)

        # Assert total count == 1167
        assert res["total_count"] == 1167, f"Expected count 1167, got {res['total_count']}"

        # Assert total ACV == 120,511,647.51
        assert abs(res["total_acv"] - 120_511_647.51) < 0.01, f"Expected ACV 120,511,647.51, got {res['total_acv']}"

        # Assert per-quarter totals
        by_quarter = res["by_quarter"]
        for quarter, expected in self.EXPECTED_QUARTERS.items():
            actual = by_quarter.get(quarter)
            assert actual is not None, f"Quarter {quarter} missing from by_quarter results"
            assert actual["count"] == expected["count"], (
                f"{quarter} count mismatch: expected {expected['count']}, got {actual['count']}"
            )
            assert abs(actual["acv"] - expected["acv"]) < 0.01, (
                f"{quarter} ACV mismatch: expected {expected['acv']}, got {actual['acv']}"
            )

    def test_expiry_pivot_deltas_vs_yesterday_and_lastweek(self, seeded_session):
        """
        Asserts the vs-Yesterday and vs-Last-Week Grand Total deltas:
          T-Y:  +1,038,157.57 (+5)
          T-LW: +1,127,296.25 (+20)
        """
        svc = _get_svc(seeded_session)
        summary = svc.get_forecast_summary(ADMIN_CONTEXT)
        totals = summary.get("totals", {})

        # T-Y deltas
        d_yest = totals.get("delta_vs_yesterday", {})
        assert d_yest.get("count") == 5, f"T-Y count delta: expected +5, got {d_yest.get('count')}"
        assert abs(d_yest.get("acv", 0.0) - 1_038_157.57) < 0.01, (
            f"T-Y ACV delta: expected +1,038,157.57, got {d_yest.get('acv')}"
        )

        # T-LW deltas: Grand Total = +20 opportunities, +1,127,296.25 ACV
        d_lw = totals.get("delta_vs_lastweek", {})
        assert d_lw.get("count") == 20, f"T-LW count delta: expected +20, got {d_lw.get('count')}"
        assert abs(d_lw.get("acv", 0.0) - 1_127_296.25) < 0.01, (
            f"T-LW ACV delta: expected +1,127,296.25, got {d_lw.get('acv')}"
        )

    def test_q2_2027_best_case_and_total_movement_vs_lastweek(self, seeded_session):
        """
        Q2-2027 Best Case today 0 (0), vs last week -542,295.23 (-1);
        Q2-2027 total vs last week -178,872.92 (0).
        """
        svc = _get_svc(seeded_session)
        summary = svc.get_forecast_summary(ADMIN_CONTEXT)

        # 1. Q2-2027 Best Case cell check
        by_cell = summary.get("by_cell", {})
        cell = by_cell.get("Q2-2027|Best Case") or by_cell.get(("Q2-2027", "Best Case"))
        assert cell is not None, "Q2-2027 Best Case cell missing from by_cell"

        # Today: 0 count, 0 ACV
        assert cell["today"]["count"] == 0, f"Q2-2027 Best Case today count: expected 0, got {cell['today']['count']}"
        assert cell["today"]["acv"] == 0.0, f"Q2-2027 Best Case today ACV: expected 0.0, got {cell['today']['acv']}"

        # Vs last week: -1 count, -542,295.23 ACV
        d_lw = cell["delta_vs_lastweek"]
        assert d_lw["count"] == -1, f"Q2-2027 Best Case delta count vs LW: expected -1, got {d_lw['count']}"
        assert abs(d_lw["acv"] - (-542_295.23)) < 0.01, (
            f"Q2-2027 Best Case delta ACV vs LW: expected -542,295.23, got {d_lw['acv']}"
        )

        # 2. Q2-2027 total check
        by_quarter = summary.get("by_quarter", {})
        q2_2027 = by_quarter.get("Q2-2027")
        assert q2_2027 is not None, "Q2-2027 quarter missing from by_quarter"

        q_d_lw = q2_2027["delta_vs_lastweek"]
        assert q_d_lw["count"] == 0, f"Q2-2027 total delta count vs LW: expected 0, got {q_d_lw['count']}"
        assert abs(q_d_lw["acv"] - (-178_872.92)) < 0.01, (
            f"Q2-2027 total delta ACV vs LW: expected -178,872.92, got {q_d_lw['acv']}"
        )




class TestComparisonEndpoint:
    """Verifies the GET /compare functionality across two dates."""

    def test_compare_dates_returns_all_dimensions(self, seeded_session):
        from datetime import date
        svc = _get_svc(seeded_session)
        res = svc.get_comparison(ADMIN_CONTEXT, date(2026, 10, 2), date(2026, 10, 5))

        assert "error" not in res
        assert "from_snapshot" in res
        assert "to_snapshot" in res
        assert "diff" in res

        # Assert all 6 required comparison dimensions exist
        assert "expiry_pivot" in res and len(res["expiry_pivot"]) > 0
        assert "forecast_category" in res and len(res["forecast_category"]) > 0
        assert "approval_status" in res and len(res["approval_status"]) > 0
        assert "region" in res and len(res["region"]) > 0
        assert "business_unit" in res and len(res["business_unit"]) > 0
        assert "movement" in res

        # Check structure of items
        fc_item = res["forecast_category"][0]
        assert "category" in fc_item
        assert "from_count" in fc_item
        assert "to_count" in fc_item
        assert "diff_count" in fc_item or "count_diff" in fc_item

        appr_item = res["approval_status"][0]
        assert "status" in appr_item
        assert "from_acv" in appr_item
        assert "to_acv" in appr_item

    def test_compare_nonexistent_date_returns_error(self, seeded_session):
        from datetime import date
        svc = _get_svc(seeded_session)
        res = svc.get_comparison(ADMIN_CONTEXT, date(2020, 1, 1), date(2026, 10, 5))
        assert "error" in res


class TestOpportunityHistory:
    """Verifies that opportunity history tracks across snapshots."""

    def test_opportunity_history(self, seeded_session):
        from backend.models.opportunity import Opportunity
        from backend.services.opportunity_service import OpportunityService

        # Pick an opportunity that appears in the snapshot
        opp = seeded_session.query(Opportunity).first()
        assert opp is not None
        opp_id = opp.opportunity_id_18

        opp_svc = OpportunityService(seeded_session)
        history = opp_svc.get_opportunity_history(ADMIN_CONTEXT, opp_id)

        assert isinstance(history, list)
        assert len(history) >= 1
        for entry in history:
            assert entry["opportunity_id_18"] == opp_id
            assert "snapshot_date" in entry
            assert "snapshot_label" in entry


class TestReuploadIdempotency:
    """Verifies that re-uploading the same date replaces only that date and does not duplicate."""

    def test_reupload_same_date(self, seeded_session):
        from datetime import date
        from backend.services.ingest_service import IngestService
        from backend.models.snapshot import UploadSnapshot
        from backend.models.opportunity import Opportunity
        from backend.config import settings

        initial_snap_count = seeded_session.query(UploadSnapshot).count()
        snap_today = seeded_session.query(UploadSnapshot).filter_by(snapshot_date=date(2026, 10, 5)).first()
        assert snap_today is not None
        initial_opp_count = seeded_session.query(Opportunity).filter_by(snapshot_id=snap_today.id).count()

        # Re-ingest
        svc = IngestService(seeded_session)
        renewals_file = settings.DATA_DIR / "Renewals Summary 3.xlsx"
        svc.ingest_renewals_summary(
            ADMIN_CONTEXT,
            renewals_file,
            snapshot_date=date(2026, 10, 5),
            label="Today",
        )
        seeded_session.commit()

        # Snapshot count should not increase
        final_snap_count = seeded_session.query(UploadSnapshot).count()
        assert final_snap_count == initial_snap_count, "Snapshots should not duplicate on re-upload"

        # Opportunity rows for today should be replaced, not doubled
        final_opp_count = seeded_session.query(Opportunity).filter_by(snapshot_id=snap_today.id).count()
        assert final_opp_count == initial_opp_count, "Opportunity count should match after re-upload"


class TestWaterfallReconciliation:
    """Verifies that the waterfall chart reconciles exactly across snapshots."""

    def test_waterfall_reconciliation_exact(self, seeded_session):
        from datetime import date
        svc = _get_svc(seeded_session)
        res = svc.get_comparison(ADMIN_CONTEXT, date(2026, 10, 2), date(2026, 10, 5))
        assert "waterfall" in res
        wf = res["waterfall"]

        # Exact mathematical identity:
        # start + new + increases - decreases - removed = end
        reconciled = round(
            wf["start_acv"] + wf["new_acv"] + wf["increases_acv"] - wf["decreases_acv"] - wf["removed_acv"],
            2,
        )
        assert reconciled == wf["end_acv"], (
            f"Waterfall reconciliation failure: {wf['start_acv']} + {wf['new_acv']} + "
            f"{wf['increases_acv']} - {wf['decreases_acv']} - {wf['removed_acv']} = {reconciled} != {wf['end_acv']}"
        )
        assert wf["is_reconciled"] is True
        assert wf["start_count"] == 3082
        assert wf["end_count"] == 3086

    def test_waterfall_reconciliation_vs_last_week(self, seeded_session):
        from datetime import date
        svc = _get_svc(seeded_session)
        res = svc.get_comparison(ADMIN_CONTEXT, date(2026, 9, 28), date(2026, 10, 5))
        assert "waterfall" in res
        wf = res["waterfall"]

        reconciled = round(
            wf["start_acv"] + wf["new_acv"] + wf["increases_acv"] - wf["decreases_acv"] - wf["removed_acv"],
            2,
        )
        assert reconciled == wf["end_acv"], (
            f"Waterfall reconciliation vs last week failure: {reconciled} != {wf['end_acv']}"
        )
        assert wf["is_reconciled"] is True


class TestPrompt3OverviewVerification:
    """
    Verifies the specific numbers requested in PROMPT 3:
    1. Commit -> Closed insight chip showing moving deals ACV ($6.58M, 29 deals) vs Commit net change (-$5.65M)
    2. Category-specific vs-last-week deltas:
       Total +$3.26M (+13), Closed +$15.36M (+86), Commit -$7.11M (-64), Best Case -$4.46M (-8), Pipeline -$2.11M (-22)
    3. Needs Attention counts:
       Newly rejected 0, Newly pending 5, Dropped from forecast 16 (Pipeline->blank 7, Best Case->blank 5, Commit->blank 4),
       ACV dropped > 25% = 4, Total unique deals = 25.
    """

    def test_commit_to_closed_headline_and_insight_chip(self, seeded_session):
        from datetime import date
        svc = _get_svc(seeded_session)
        res = svc.get_comparison(ADMIN_CONTEXT, date(2026, 10, 2), date(2026, 10, 5))

        # Headline verification
        headline = res["headline"]["text"]
        assert "ACV is up $3.07M and 4 opportunities since yesterday." in headline
        assert "Commit moved -$5.65M, mostly into Closed (29 deals)." in headline

        # Insight chip verification: must show ACV of deals that moved (~$6.58M), NOT net category change (-$5.65M)
        chips = {c["label"]: c["value"] for c in res["headline"]["chips"]}
        assert "Commit → Closed" in chips
        chip_val = chips["Commit → Closed"]
        assert "+$6.58M (29 deals)" in chip_val
        assert "-$5.65M" not in chip_val

    def test_kpi_tiles_category_deltas_vs_last_week(self, seeded_session):
        from datetime import date
        svc = _get_svc(seeded_session)
        res = svc.get_comparison(ADMIN_CONTEXT, date(2026, 10, 2), date(2026, 10, 5))

        kpis = {k["key"]: k for k in res["kpi_strip"]}

        # 1. Total: +$3.26M (+13)
        assert round(kpis["total_acv"]["delta_last_week"], 2) == 3_264_648.31
        assert kpis["total_count"]["delta_last_week"] == 13

        # 2. Closed: +$15.36M (+86)
        assert round(kpis["closed_acv"]["delta_last_week"], 2) == 15_362_878.71
        assert kpis["closed_acv"]["delta_last_week_count"] == 86

        # 3. Commit: -$7.11M (-64)
        assert round(kpis["commit_acv"]["delta_last_week"], 2) == -7_108_963.06
        assert kpis["commit_acv"]["delta_last_week_count"] == -64

        # 4. Best Case: -$4.46M (-8)
        assert round(kpis["best_case_acv"]["delta_last_week"], 2) == -4_455_170.63
        assert kpis["best_case_acv"]["delta_last_week_count"] == -8

        # 5. Pipeline: -$2.11M (-22)
        assert round(kpis["pipeline_acv"]["delta_last_week"], 2) == -2_110_150.03
        assert kpis["pipeline_acv"]["delta_last_week_count"] == -22

    def test_needs_attention_counts_and_summary(self, seeded_session):
        from datetime import date
        svc = _get_svc(seeded_session)
        res = svc.get_comparison(ADMIN_CONTEXT, date(2026, 10, 2), date(2026, 10, 5))

        summary = res["needs_attention_summary"]
        counts = summary["counts_by_type"]

        # Expected counts per user spec:
        # Newly rejected: 0
        assert counts["newly_rejected"] == 0
        # Newly pending: 5
        assert counts["newly_pending"] == 5
        # Dropped from forecast / slipped: 16
        assert counts["dropped_from_forecast"] == 16
        # ACV dropped > 25%: 4
        assert counts["acv_drop_25"] == 4

        # Total unique deals: 25 (with overlaps removed)
        assert summary["total_unique"] == 25
        assert summary["total_exceptions"] == 25
        assert summary["overlap_count"] == 0

        # Verify items inside dropped_from_forecast have the 7 Pipeline, 5 Best Case, 4 Commit
        dropped_items = [i for i in res["needs_attention"] if i["attention_type"] == "dropped_from_forecast"]
        assert len(dropped_items) == 16
        pipe_to_blank = [i for i in dropped_items if i["old_value"] == "Pipeline" and i["new_value"] in ["Blank", "", None]]
        bc_to_blank = [i for i in dropped_items if i["old_value"] == "Best Case" and i["new_value"] in ["Blank", "", None]]
        commit_to_blank = [i for i in dropped_items if i["old_value"] == "Commit" and i["new_value"] in ["Blank", "", None]]
        assert len(pipe_to_blank) == 7
        assert len(bc_to_blank) == 5
        assert len(commit_to_blank) == 4


class TestPrompt4ReferenceVerification:
    """
    Automated tests verifying Prompt 4 reference numbers:
    1. Expiry Page:
       - Total: 1,167 / $120,511,647.51
       - Q4-2026: $52,675,598.94 (427 deals)
       - Q2-2027 total vs last week: -$178,872.92 (0 count)
       - Q2-2027 Best Case vs last week: -$542,295.23 (-1 count)
    2. Approvals Page:
       - Total: 3,086 / $450.04M
       - Approved: 748 / $95.79M
       - Approved - 2nd: 877 / $86.98M
       - Pending: 31 / $11.00M
       - Blank: 1,411 / $246.46M
       - Rejected: 19 / $9.81M
       - Changes today: newly approved 9, newly pending 5, newly rejected 0
    3. Business Units Page:
       - 16 distinct rows in "As in Excel" mode
       - Testing: 1,135 (338 / 358 / 3 / 433 / 3)
       - Risk: 749 (174 / 259 / 3 / 308 / 5)
       - Roaming: 750 (156 / 174 / 12 / 402 / 6)
       - Security: 205 (38 / 48 / 5 / 113 / 1)
       - Engagement and Experience: 169 (27 / 22 / 3 / 114 / 3)
       - Total: 3,086 = 748 + 877 + 31 + 1,411 + 19
       - 5 distinct BUs in "Split" mode
    """

    def test_prompt4_expiry_references(self, seeded_session):
        svc = _get_svc(seeded_session)
        res = svc.get_forecast_summary(ADMIN_CONTEXT)

        # Total 1,167 / $120,511,647.51
        tot = res["totals"]["today"]
        assert tot["count"] == 1167
        assert round(tot["acv"], 2) == 120_511_647.51

        # Q4-2026: $52,675,598.94 (427)
        q4_2026 = res["by_quarter"]["Q4-2026"]["today"]
        assert q4_2026["count"] == 427
        assert round(q4_2026["acv"], 2) == 52_675_598.94

        # Q2-2027 total vs last week: -$178,872.92 (0)
        q2_2027_lw = res["by_quarter"]["Q2-2027"]["delta_vs_lastweek"]
        assert round(q2_2027_lw["acv"], 2) == -178_872.92
        assert q2_2027_lw["count"] == 0

        # Q2-2027 Best Case vs last week: -$542,295.23 (-1)
        q2_bc_lw = res["by_cell"]["Q2-2027|Best Case"]["delta_vs_lastweek"]
        assert round(q2_bc_lw["acv"], 2) == -542_295.23
        assert q2_bc_lw["count"] == -1

    def test_prompt4_approvals_references(self, seeded_session):
        svc = _get_svc(seeded_session)
        res = svc.get_approval_status(ADMIN_CONTEXT)

        assert res["total_count"] == 3086
        assert round(res["total_acv"], 2) == 450_040_250.54

        rows = {r["approval_status"]: r for r in res["rows"]}

        # Approved 748 / $95,793,389.47
        assert rows["Approved"]["count"] == 748
        assert round(rows["Approved"]["acv"], 2) == 95_793_389.47

        # Approved - 2nd 877 / $86,981,910.94
        assert rows["Approved - 2nd"]["count"] == 877
        assert round(rows["Approved - 2nd"]["acv"], 2) == 86_981_910.94

        # Pending 31 / $11,000,202.55
        assert rows["Pending-Approval"]["count"] == 31
        assert round(rows["Pending-Approval"]["acv"], 2) == 11_000_202.55

        # Blank 1,411 / $246,458,479.25
        assert rows["Blank"]["count"] == 1411
        assert round(rows["Blank"]["acv"], 2) == 246_458_479.25

        # Rejected 19 / $9,806,268.33
        assert rows["Rejected"]["count"] == 19
        assert round(rows["Rejected"]["acv"], 2) == 9_806_268.33

        # The five statuses must sum exactly to the total down to the cent
        sum_five = round(
            rows["Approved"]["acv"] +
            rows["Approved - 2nd"]["acv"] +
            rows["Pending-Approval"]["acv"] +
            rows["Blank"]["acv"] +
            rows["Rejected"]["acv"],
            2,
        )
        assert sum_five == 450_040_250.54
        assert round(res["total_acv"], 2) == 450_040_250.54

        # Changes: newly approved 9, newly pending 5, newly rejected 0
        changes = res["changes"]
        assert changes["newly_approved_count"] == 9
        assert changes["newly_pending_count"] == 5
        assert changes["newly_rejected_count"] == 0

    def test_prompt4_business_units_as_in_excel(self, seeded_session):
        svc = _get_svc(seeded_session)
        res = svc.get_approval_by_bu(ADMIN_CONTEXT, mode="as_in_excel")

        # 16 distinct rows in "As in Excel" mode
        rows = {r["business_unit"]: r for r in res["as_in_excel_rows"]}
        assert len(rows) == 16

        # Testing 1,135 (338 / 358 / 3 / 433 / 3)
        testing = rows["Testing"]
        assert testing["total_count"] == 1135
        assert testing["approved_count"] == 338
        assert testing["approved_2nd_count"] == 358
        assert testing["pending_count"] == 3
        assert testing["blank_count"] == 433
        assert testing["rejected_count"] == 3
        assert round(testing["acv"], 2) == 75_351_983.77

        # Risk 749 (174 / 259 / 3 / 308 / 5)
        risk = rows["Risk"]
        assert risk["total_count"] == 749
        assert risk["approved_count"] == 174
        assert risk["approved_2nd_count"] == 259
        assert risk["pending_count"] == 3
        assert risk["blank_count"] == 308
        assert risk["rejected_count"] == 5
        assert round(risk["acv"], 2) == 93_690_411.86

        # Roaming 750 (156 / 174 / 12 / 402 / 6)
        roaming = rows["Roaming"]
        assert roaming["total_count"] == 750
        assert roaming["approved_count"] == 156
        assert roaming["approved_2nd_count"] == 174
        assert roaming["pending_count"] == 12
        assert roaming["blank_count"] == 402
        assert roaming["rejected_count"] == 6
        assert round(roaming["acv"], 2) == 123_685_700.19

        # Security 205 (38 / 48 / 5 / 113 / 1)
        security = rows["Security"]
        assert security["total_count"] == 205
        assert security["approved_count"] == 38
        assert security["approved_2nd_count"] == 48
        assert security["pending_count"] == 5
        assert security["blank_count"] == 113
        assert security["rejected_count"] == 1
        assert round(security["acv"], 2) == 35_272_566.61

        # Engagement and Experience 169 (27 / 22 / 3 / 114 / 3)
        ee = rows["Engagement and Experience"]
        assert ee["total_count"] == 169
        assert ee["approved_count"] == 27
        assert ee["approved_2nd_count"] == 22
        assert ee["pending_count"] == 3
        assert ee["blank_count"] == 114
        assert ee["rejected_count"] == 3
        assert round(ee["acv"], 2) == 73_829_369.93

        # Total 3,086 = 748 + 877 + 31 + 1,411 + 19
        tot = res["total"]
        assert tot["total_count"] == 3086
        assert tot["approved_count"] == 748
        assert tot["approved_2nd_count"] == 877
        assert tot["pending_count"] == 31
        assert tot["blank_count"] == 1411
        assert tot["rejected_count"] == 19
        assert (
            tot["approved_count"] + tot["approved_2nd_count"] +
            tot["pending_count"] + tot["blank_count"] + tot["rejected_count"]
            == 3086
        )
        assert round(tot["acv"], 2) == 450_040_250.54

        # Sum of all 16 rows must equal total ACV exactly to the cent
        sum_16 = round(sum(r["acv"] for r in res["as_in_excel_rows"]), 2)
        assert sum_16 == 450_040_250.54

    def test_prompt4_business_units_split(self, seeded_session):
        svc = _get_svc(seeded_session)
        res = svc.get_approval_by_bu(ADMIN_CONTEXT, mode="split")

        rows = {r["business_unit"]: r for r in res["split_rows"]}
        assert len(rows) == 5
        assert set(rows.keys()) == {
            "Testing", "Roaming", "Risk", "Security", "Engagement and Experience"
        }
        assert res["total"]["total_count"] == 3086
        assert round(res["total"]["acv"], 2) == 450_040_250.54


class TestPrompt5RegionsExploreHistory:
    """
    Prompt 5 verification:
    1. Regions references down to the cent:
       - North America: 328 opps, $79,885,241.32 (top: Verizon_AMC, $4,968,375.00)
       - West Europe: 912 opps, $77,950,209.50 (top: OFR RR, $4,563,084.65)
       - Middle East: 374 opps, $74,343,552.73 (top: Mobilis, $13,800,000.00)
       - AFRICA: 390 opps, $71,672,803.13 (top: CAK, $4,000,000.00)
       - SEAO: 338 opps, $48,958,583.57 (top: Optus, $1,672,867.34)
       - South America: 276 opps, $35,055,573.86 (top: AMX, $1,032,629.03)
       - NASA: 170 opps, $34,506,916.51 (top: NTT Docomo, $4,000,000.00)
       - East Europe: 292 opps, $19,139,173.92 (top: Azercell, $912,616.93)
       - NAMR GUAVUS: 6 opps, $8,528,196.00 (top: Verizon Guavus, $5,435,136.00)
       - Sum of all 9 regions == 3,086 count, $450,040,250.54 ACV
    2. Explore filters:
       - Region, BU, Category, Approval, Expiry, ACV range, Search
    3. CSV Export:
       - Header + rows count matching filter
    4. History Overview:
       - Timeline, 3 snapshots, history note
    """

    def test_prompt5_regions_exact_references(self, seeded_session):
        svc = _get_svc(seeded_session)
        # 1. As in Excel mode (default)
        res = svc.get_sub_regions_overview(ADMIN_CONTEXT, mode="as_in_excel")

        assert res["total_count"] == 3086
        assert round(res["total_acv"], 2) == 450_040_250.54

        regions = {r["sub_region"]: r for r in res["regions"]}
        assert len(regions) == 9

        # 1. North America: 328 opps, $79,885,241.32 (top: Verizon_AMC..., $4,968,375.00)
        na = regions["North America"]
        assert na["count"] == 328
        assert round(na["acv"], 2) == 79_885_241.32
        assert "Verizon_AMC" in na["top_10_opportunities"][0]["opportunity_name"]
        assert round(na["top_10_opportunities"][0]["acv"], 2) == 4_968_375.00
        assert na["leading_bu"] == "Roaming; Security"

        # 2. West Europe: 912 opps, $77,950,209.50 (top: OFR RR..., $4,563,084.65)
        we = regions["West Europe"]
        assert we["count"] == 912
        assert round(we["acv"], 2) == 77_950_209.50
        assert "OFR RR platform replacement" in we["top_10_opportunities"][0]["opportunity_name"]
        assert round(we["top_10_opportunities"][0]["acv"], 2) == 4_563_084.65
        assert we["leading_bu"] == "Roaming"

        # 3. Middle East: 374 opps, $74,343,552.73 (top: Mobilis - CEM RFP 2026, $13,800,000.00)
        me = regions["Middle East"]
        assert me["count"] == 374
        assert round(me["acv"], 2) == 74_343_552.73
        assert "Mobilis - CEM RFP 2026" in me["top_10_opportunities"][0]["opportunity_name"]
        assert round(me["top_10_opportunities"][0]["acv"], 2) == 13_800_000.00
        assert me["leading_bu"] == "Engagement and Experience"

        # 4. AFRICA: 390 opps, $71,672,803.13 (top: CAK - Tax Assurance, $4,000,000.00)
        af = regions["AFRICA"]
        assert af["count"] == 390
        assert round(af["acv"], 2) == 71_672_803.13
        assert "CAK - Tax Assurance" in af["top_10_opportunities"][0]["opportunity_name"]
        assert round(af["top_10_opportunities"][0]["acv"], 2) == 4_000_000.00
        assert af["leading_bu"] == "Risk"

        # 5. SEAO: 338 opps, $48,958,583.57 (top: Optus..., $1,672,867.34)
        seao = regions["SEAO"]
        assert seao["count"] == 338
        assert round(seao["acv"], 2) == 48_958_583.57
        assert "Optus - E000 Nomadics extension" in seao["top_10_opportunities"][0]["opportunity_name"]
        assert round(seao["top_10_opportunities"][0]["acv"], 2) == 1_672_867.34
        assert seao["leading_bu"] == "Testing"

        # 6. South America: 276 opps, $35,055,573.86 (top: AMX - Claro Brasil..., $1,032,629.03)
        sa = regions["South America"]
        assert sa["count"] == 276
        assert round(sa["acv"], 2) == 35_055_573.86
        assert sa["top_10_opportunities"][0]["opportunity_name"] == "AMX - Claro Brasil - RAID Modules - RA Transformation - PO 2"
        assert round(sa["top_10_opportunities"][0]["acv"], 2) == 1_032_629.03
        assert sa["leading_bu"] == "Risk"

        # 7. NASA: 170 opps, $34,506,916.51 (top: NTT Docomo..., $4,000,000.00)
        nasa = regions["NASA"]
        assert nasa["count"] == 170
        assert round(nasa["acv"], 2) == 34_506_916.51
        assert nasa["top_10_opportunities"][0]["opportunity_name"] == "NTT Docomo SecurityFW_International and MVNO"
        assert round(nasa["top_10_opportunities"][0]["acv"], 2) == 4_000_000.00
        assert nasa["leading_bu"] == "Risk; Roaming; Security"

        # 8. East Europe: 292 opps, $19,139,173.92 (top: Azercell RA & FMS RFI, $912,616.93)
        ee = regions["East Europe"]
        assert ee["count"] == 292
        assert round(ee["acv"], 2) == 19_139_173.92
        assert "Azercell RA & FMS RFI" in ee["top_10_opportunities"][0]["opportunity_name"]
        assert round(ee["top_10_opportunities"][0]["acv"], 2) == 912_616.93
        assert ee["leading_bu"] == "Risk"

        # 9. NAMR GUAVUS: 6 opps, $8,528,196.00 (top: Verizon Guavus EBM EDR/FDR, $5,435,136.00)
        ng = regions["NAMR GUAVUS"]
        assert ng["count"] == 6
        assert round(ng["acv"], 2) == 8_528_196.00
        assert "Verizon Guavus EBM EDR/FDR" in ng["top_10_opportunities"][0]["opportunity_name"]
        assert round(ng["top_10_opportunities"][0]["acv"], 2) == 5_435_136.00
        assert ng["leading_bu"] == "Engagement and Experience"

        # Reconcile sum of all 9 sub-regions
        sum_acv = round(sum(r["acv"] for r in res["regions"]), 2)
        sum_cnt = sum(r["count"] for r in res["regions"])
        assert sum_acv == 450_040_250.54
        assert sum_cnt == 3086

        # 2. Split mode: NASA leading BU must be first listed BU ("Risk") and NA must be "Roaming"
        res_split = svc.get_sub_regions_overview(ADMIN_CONTEXT, mode="split")
        regions_split = {r["sub_region"]: r for r in res_split["regions"]}
        assert regions_split["NASA"]["leading_bu"] == "Risk"
        assert regions_split["North America"]["leading_bu"] == "Roaming"

    def test_prompt5_regions_top_opportunity_raw_data_all_9_regions(self, seeded_session):
        """Assert the top opportunity ID, name, BU and ACV for all 9 regions from the raw data."""
        from backend.models.opportunity import Opportunity
        from backend.models.snapshot import UploadSnapshot

        snap = (
            seeded_session.query(UploadSnapshot)
            .filter_by(is_active_today=True)
            .first()
        )

        expected_top_raw = {
            "North America": {
                "id": "006Qp00000as0WCIAY",
                "name": "Verizon_AMC, Onsite Manage Services and License renewal  - RNS  -2027",
                "bu_raw": "Roaming; Security",
                "bu_prim": "Roaming",
                "acv": 4_968_375.00,
            },
            "West Europe": {
                "id": "006Qp00000kgHhuIAE",
                "name": "OFR RR platform replacement",
                "bu_raw": "Roaming",
                "bu_prim": "Roaming",
                "acv": 4_563_084.65,
            },
            "Middle East": {
                "id": "006Qp00000jDqtJIAS",
                "name": "Mobilis - CEM RFP 2026",
                "bu_raw": "Engagement and Experience",
                "bu_prim": "Engagement and Experience",
                "acv": 13_800_000.00,
            },
            "AFRICA": {
                "id": "0061K00000lgzEgQAI",
                "name": "CAK - Tax Assurance",
                "bu_raw": "Risk",
                "bu_prim": "Risk",
                "acv": 4_000_000.00,
            },
            "SEAO": {
                "id": "006Qp00000aofsrIAA",
                "name": "Optus - E000 Nomadics extension",
                "bu_raw": "Testing",
                "bu_prim": "Testing",
                "acv": 1_672_867.34,
            },
            "South America": {
                "id": "006Qp00000Yx1voIAB",
                "name": "AMX - Claro Brasil - RAID Modules - RA Transformation - PO 2",
                "bu_raw": "Risk",
                "bu_prim": "Risk",
                "acv": 1_032_629.03,
            },
            "NASA": {
                "id": "006Qp00000OkzXKIAZ",
                "name": "NTT Docomo SecurityFW_International and MVNO",
                "bu_raw": "Risk; Roaming; Security",
                "bu_prim": "Risk",
                "acv": 4_000_000.00,
            },
            "East Europe": {
                "id": "0061K00000fl1ntQAA",
                "name": "Azercell RA & FMS RFI",
                "bu_raw": "Risk",
                "bu_prim": "Risk",
                "acv": 912_616.93,
            },
            "NAMR GUAVUS": {
                "id": "006Qp00000fhmwGIAQ",
                "bu_raw": "Engagement and Experience",
                "bu_prim": "Engagement and Experience",
                "acv": 5_435_136.00,
            },
        }

        for region_name, exp in expected_top_raw.items():
            top_opp = (
                seeded_session.query(Opportunity)
                .filter(
                    Opportunity.snapshot_id == snap.id,
                    Opportunity.sub_region == region_name,
                )
                .order_by(Opportunity.forecast_acv_amount.desc())
                .first()
            )
            assert top_opp is not None, f"No opportunity found for region {region_name}"
            assert top_opp.opportunity_id_18 == exp["id"], (
                f"{region_name} ID: expected {exp['id']}, got {top_opp.opportunity_id_18}"
            )
            if "name" in exp:
                assert top_opp.opportunity_name == exp["name"], (
                    f"{region_name} Name: expected {exp['name']!r}, got {top_opp.opportunity_name!r}"
                )
            else:
                assert "Verizon Guavus EBM EDR/FDR" in top_opp.opportunity_name
            assert top_opp.business_unit_raw == exp["bu_raw"], (
                f"{region_name} BU Raw: expected {exp['bu_raw']!r}, got {top_opp.business_unit_raw!r}"
            )
            assert top_opp.business_unit_primary == exp["bu_prim"], (
                f"{region_name} BU Primary: expected {exp['bu_prim']!r}, got {top_opp.business_unit_primary!r}"
            )
            assert round(float(top_opp.forecast_acv_amount), 2) == exp["acv"], (
                f"{region_name} ACV: expected {exp['acv']}, got {top_opp.forecast_acv_amount}"
            )

    def test_prompt5_explore_filters_and_export(self, seeded_session):
        from backend.services.opportunity_service import OpportunityService

        opp_svc = OpportunityService(seeded_session)

        # 1. Filter by region
        na_res = opp_svc.list_opportunities(ADMIN_CONTEXT, sub_region=["North America"])
        assert na_res["total"] == 328

        # 2. Filter by forecast category
        commit_res = opp_svc.list_opportunities(ADMIN_CONTEXT, forecast_category=["Commit"])
        assert commit_res["total"] == 488

        # 3. Filter by approval status
        app_res = opp_svc.list_opportunities(ADMIN_CONTEXT, approval_status=["Approved"])
        assert app_res["total"] == 748

        # 4. Filter by min ACV
        high_res = opp_svc.list_opportunities(ADMIN_CONTEXT, min_acv=1_000_000)
        assert high_res["total"] > 0
        for item in high_res["items"]:
            assert item["forecast_acv_amount"] >= 1_000_000

        # 5. Search by text
        search_res = opp_svc.list_opportunities(ADMIN_CONTEXT, search="Verizon")
        assert search_res["total"] > 0

        # 6. CSV Export row count and headers
        csv_text = opp_svc.export_opportunities_csv(ADMIN_CONTEXT, sub_region=["North America"])
        lines = csv_text.strip().split("\r\n") if "\r\n" in csv_text else csv_text.strip().split("\n")
        assert len(lines) == 329  # 1 header + 328 rows
        assert "Opportunity ID,Opportunity Name,Account Name,Sub-Region" in lines[0]

    def test_prompt5_history_overview(self, seeded_session):
        svc = _get_svc(seeded_session)
        res = svc.get_history_overview(ADMIN_CONTEXT)

        assert res["total_count"] == 3
        assert len(res["snapshots"]) == 3
        assert "Collecting history" in res["history_note"]
        assert len(res["trends"]["total_acv"]) == 3
        assert len(res["trends"]["count"]) == 3





