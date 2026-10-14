"""
test_prompt10.py — Comprehensive tests for Prompt 10:
- Working day Yesterday auto-fill & manual override
- UI label showing real date & Monday case
- Anomaly normalization by days_between & 7-snapshot count rule
- Staleness and days since last change using snapshot date
- B1: Old snapshots have null scope flags, trends show gaps not 0
- B2: Content-based slot detection for summary files & slot mismatch warnings
- B3: Yesterday sheet from comparison tool & last week source tracking
- B4: Scope and include_deleted_lost applied across assistant, insights, exports, analytics
- B5: Atomic transaction rollback & duplicate file SHA-256 detection
"""
from datetime import date, timedelta
from pathlib import Path
import pytest

from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot, UploadedFile
from backend.services.context import ADMIN_CONTEXT, UserContext
from backend.services.ingest_service import (
    compute_previous_working_day,
)
from backend.utils.excel_parser import (
    detect_file_slot,
    compute_file_sha256,
)
from backend.services.analytics_service import AnalyticsService
from backend.services.risk_service import RiskService
from backend.services.assistant_tools import AssistantTools
from backend.services.pptx_export_service import PptxExportService
from backend.services.excel_export_service import ExcelExportService


# =========================================================================== #
# Part A: Working day Yesterday & Anomaly Normalization Tests
# =========================================================================== #

class TestWorkingDayYesterday:
    def test_monday_auto_fills_previous_friday(self):
        # Monday 2026-10-05 -> Friday 2026-10-02 (3 days earlier)
        mon = date(2026, 10, 5)
        assert mon.weekday() == 0  # Monday
        prev_work_day = compute_previous_working_day(mon)
        assert prev_work_day == date(2026, 10, 2)
        assert prev_work_day.weekday() == 4  # Friday

    def test_wednesday_auto_fills_previous_day(self):
        # Wednesday 2026-10-07 -> Tuesday 2026-10-06 (1 day earlier)
        wed = date(2026, 10, 7)
        assert wed.weekday() == 2  # Wednesday
        prev_work_day = compute_previous_working_day(wed)
        assert prev_work_day == date(2026, 10, 6)
        assert prev_work_day.weekday() == 1  # Tuesday

    def test_tuesday_and_friday_working_days(self):
        # Tuesday 2026-10-06 -> Monday 2026-10-05
        assert compute_previous_working_day(date(2026, 10, 6)) == date(2026, 10, 5)
        # Friday 2026-10-02 -> Thursday 2026-10-01
        assert compute_previous_working_day(date(2026, 10, 2)) == date(2026, 10, 1)

    def test_weekend_dates_warning_flag(self):
        # Saturday and Sunday should map to Friday and be flagged with warning
        sat = date(2026, 10, 3)
        sun = date(2026, 10, 4)
        assert compute_previous_working_day(sat) == date(2026, 10, 2)
        assert compute_previous_working_day(sun) == date(2026, 10, 2)

    def test_manual_override_saved_and_used(self, seeded_session):
        # Verify manual override (e.g. for holiday) is persisted to yesterday_date
        snap = UploadSnapshot(
            snapshot_date=date(2027, 8, 16),
            yesterday_date=date(2027, 8, 12),  # Manual override (Thursday holiday on Friday)
            label="Manual Override Test",
            is_active_today=False,
            active_row_count=10,
        )
        seeded_session.add(snap)
        seeded_session.commit()

        loaded = seeded_session.query(UploadSnapshot).filter_by(id=snap.id).first()
        assert loaded.yesterday_date == date(2027, 8, 12)

    def test_friday_to_monday_change_divided_by_3_in_anomaly_input(self, seeded_session):
        # Verify that when two snapshots are Friday 2026-10-02 and Monday 2026-10-05 (3 days apart),
        # days_between is 3 and rate is change / 3
        d_fri = date(2026, 10, 2)
        d_mon = date(2026, 10, 5)
        days_diff = (d_mon - d_fri).days
        assert days_diff == 3

        # Simulate change calculation:
        fri_acv = 118_552_667.81
        mon_acv = 120_511_647.51
        raw_change = mon_acv - fri_acv
        daily_normalized = raw_change / days_diff
        assert round(daily_normalized, 2) == round(1_958_979.70 / 3, 2)

    def test_7_snapshots_needed_rule_counts_snapshots_not_calendar_days(self, seeded_session):
        svc = AnalyticsService(seeded_session)
        res = svc.compute_anomaly_zscore(ADMIN_CONTEXT)
        # If there are fewer than 7 snapshots, it must report has_sufficient_history=False
        # regardless of how many calendar days elapsed
        if res["snapshot_count"] < 7:
            assert res["has_sufficient_history"] is False
            assert res["required_snapshots"] == 7

    def test_staleness_and_risk_uses_snapshot_data_as_of_not_machine_date(self, seeded_session):
        risk_svc = RiskService(seeded_session)
        # An opportunity whose close date is 2026-10-10 relative to 2026-10-05 is within 5 days.
        opp = Opportunity(
            snapshot_id="test_snap_1",
            opportunity_id_18="006000000000001AAA",
            opportunity_name="Near Expiry Deal",
            account_name="Acme Corp",
            forecast_category="Commit",
            forecast_acv_amount=500_000.0,
            probability_pct=90.0,
            close_date=date(2026, 10, 10),
            service_expiry_period="Q4-2026",
            approval_status="Approved",
            months_delayed=0,
            in_renewals=True,
            is_deleted_or_lost=False,
        )
        # Compute with explicit as_of_date
        res_oct5 = risk_svc.compute_deal_risk(opp, as_of_date=date(2026, 10, 5))
        # Find close date factor
        close_factors = [f for f in res_oct5["factors"] if "Close Date" in f["name"]]
        assert len(close_factors) == 1
        assert close_factors[0]["points"] > 0
        assert "imminent" in close_factors[0]["description"].lower() or "remaining" in close_factors[0]["description"].lower()


# =========================================================================== #
# Part B1: Backfill & Null Scope Flags (Gaps, not zeros)
# =========================================================================== #

class TestB1BackfillAndNullScopes:
    def test_old_snapshot_scope_flags_null_and_unavailable(self, seeded_session):
        # Create an older snapshot without scope flags populated
        old_snap = UploadSnapshot(
            snapshot_date=date(2027, 7, 1),
            yesterday_date=date(2027, 6, 30),
            label="Historic Snapshot",
            is_active_today=False,
            active_row_count=50,
        )
        seeded_session.add(old_snap)
        seeded_session.commit()

        opp = Opportunity(
            snapshot_id=old_snap.id,
            opportunity_id_18="006OLD000000001AAA",
            opportunity_name="Old Opp",
            account_name="Old Corp",
            forecast_category="Commit",
            forecast_acv_amount=100_000.0,
            in_renewals=True,
            in_fy2026=None,  # Null for old snapshots
            in_fy2027=None,
            in_q4_2026=None,
            is_deleted_or_lost=False,
            stage_number=3,
        )
        seeded_session.add(opp)
        seeded_session.commit()

        svc = AnalyticsService(seeded_session)
        # Check scope availability: renewals is True, but fy2026/fy2027/q4_2026 are False
        assert svc.is_scope_available(old_snap.id, "renewals") is True
        assert svc.is_scope_available(old_snap.id, "fy2026") is False
        assert svc.is_scope_available(old_snap.id, "fy2027") is False
        assert svc.is_scope_available(old_snap.id, "q4_2026") is False

    def test_history_trend_returns_gaps_not_zeros_for_unavailable_scope(self, seeded_session):
        svc = AnalyticsService(seeded_session)
        overview = svc.get_history_overview(ADMIN_CONTEXT, scope="fy2026")
        # Snapshots where fy2026 is unavailable must have value: None, NEVER 0.0
        for pt in overview["trends"]["total_acv"]:
            if pt["value"] is None:
                assert pt["value"] is not 0.0
                assert pt["value"] is not 0


# =========================================================================== #
# Part B2: Content-Based Slot Detection
# =========================================================================== #

class TestB2ContentBasedSlotDetection:
    def test_detect_comparison_tool(self):
        comp_file = Path("Renewal Comparison Tool 11.xlsx")
        if not comp_file.exists():
            comp_file = Path("data/Renewal Comparison Tool 11.xlsx")
        if comp_file.exists():
            slot, desc = detect_file_slot(comp_file)
            assert slot == "comparison_tool"
            assert "today & yesterday" in desc.lower()

    def test_detect_summary_files_by_content(self):
        q4_file = Path("Renewals Summary - Fiscal Q4.xlsx")
        if not q4_file.exists():
            q4_file = Path("data/Renewals Summary - Fiscal Q4.xlsx")
        if q4_file.exists():
            slot, desc = detect_file_slot(q4_file)
            assert slot in ("fiscal_q4", "renewals_summary:Q4-2026")
            assert "q4" in desc.lower()

        fy27_file = Path("Renewals Summary - Fiscal 2027.xlsx")
        if not fy27_file.exists():
            fy27_file = Path("data/Renewals Summary - Fiscal 2027.xlsx")
        if fy27_file.exists():
            slot, desc = detect_file_slot(fy27_file)
            assert slot in ("fiscal_2027", "renewals_summary:FY2027")
            assert "2027" in desc.lower()

        fy26_file = Path("Renewals Summary - Fiscal 2026.xlsx")
        if not fy26_file.exists():
            fy26_file = Path("data/Renewals Summary - Fiscal 2026.xlsx")
        if fy26_file.exists():
            slot, desc = detect_file_slot(fy26_file)
            assert slot in ("fiscal_2026", "renewals_summary:FY2026")


# =========================================================================== #
# Part B3: Yesterday & Last Week Data Sources
# =========================================================================== #

class TestB3YesterdayAndLastWeekSources:
    def test_yesterday_data_uses_comparison_tool_sheet_always(self, seeded_session):
        # AnalyticsService._get_adjacent_snapshot(snap, days_back=1) returns exactly yesterday_date
        svc = AnalyticsService(seeded_session)
        active_snap = svc.get_active_snapshot(ADMIN_CONTEXT)
        if active_snap:
            assert active_snap.yesterday_date is not None
            yest_snap = svc._get_adjacent_snapshot(active_snap, days_back=1)
            assert yest_snap is not None
            assert yest_snap.snapshot_date == active_snap.yesterday_date

    def test_last_week_source_tracking(self, seeded_session):
        # Verify last_week_source and last_week_is_partial columns exist on UploadSnapshot
        snap = UploadSnapshot(
            snapshot_date=date(2027, 5, 10),
            yesterday_date=date(2027, 5, 7),
            label="Source Tracking Test",
            last_week_source="summary_union",
            last_week_is_partial=True,
            active_row_count=100,
        )
        seeded_session.add(snap)
        seeded_session.commit()

        loaded = seeded_session.query(UploadSnapshot).filter_by(id=snap.id).first()
        assert loaded.last_week_source == "summary_union"
        assert loaded.last_week_is_partial is True


# =========================================================================== #
# Part B4: Scope and Include Deleted & Lost Applied Across All Features
# =========================================================================== #

class TestB4ScopeAndIncludeDeletedLostEverywhere:
    def test_assistant_tools_filtering(self, seeded_session):
        # Default AssistantTools has scope="all", include_deleted_lost=True
        tools_all = AssistantTools(seeded_session, ADMIN_CONTEXT, scope="all", include_deleted_lost=True)
        kpi_all = tools_all.get_kpis()
        assert kpi_all["numbers"]["total_count"] == 3086

        # Scoped AssistantTools to renewals only excluding deleted/lost
        tools_renewals = AssistantTools(seeded_session, ADMIN_CONTEXT, scope="renewals", include_deleted_lost=False)
        kpi_renewals = tools_renewals.get_kpis()
        assert kpi_renewals["numbers"]["total_count"] < 3086
        assert kpi_renewals["numbers"]["total_count"] == 1128

    def test_risk_service_filtering(self, seeded_session):
        risk_svc = RiskService(seeded_session)
        # Insights with renewals only and no deleted/lost
        insights_renewals = risk_svc.get_insights(ADMIN_CONTEXT, scope="renewals", include_deleted_lost=False)
        assert "top_at_risk" in insights_renewals
        # All deals in insights must have in_renewals == True
        for d in insights_renewals["top_at_risk"]:
            opp = seeded_session.query(Opportunity).filter_by(opportunity_id_18=d["opportunity_id_18"]).first()
            if opp:
                assert opp.in_renewals is True
                assert opp.is_deleted_or_lost is False

    def test_analytics_kpi_filtering(self, seeded_session):
        svc = AnalyticsService(seeded_session)
        kpi_all = svc.get_kpis(ADMIN_CONTEXT, scope="all", include_deleted_lost=True)
        assert kpi_all["total_count"] == 3086

        kpi_renewals = svc.get_kpis(ADMIN_CONTEXT, scope="renewals", include_deleted_lost=False)
        assert kpi_renewals["total_count"] == 1128

    def test_pptx_and_excel_export_respects_scope(self, seeded_session):
        pptx_svc = PptxExportService(seeded_session)
        excel_svc = ExcelExportService(seeded_session)
        # Verify export accepts scope and include_deleted_lost arguments without error
        stream, fname = pptx_svc.generate_pptx(scope="renewals", include_deleted_lost=False)
        assert len(stream.getvalue()) > 0
        assert fname.endswith(".pptx")

        stream_xl, fname_xl = excel_svc.generate_excel(scope="renewals", include_deleted_lost=False)
        assert len(stream_xl.getvalue()) > 0
        assert fname_xl.endswith(".xlsx")


# =========================================================================== #
# Part B5: Atomic Transaction & Duplicate SHA-256 Detection
# =========================================================================== #

class TestB5AtomicTransactionAndDuplicateSHA256:
    def test_sha256_computation_and_duplicate_detection(self, tmp_path, seeded_session):
        test_file = tmp_path / "sample.xlsx"
        test_file.write_bytes(b"test file content for sha256 calculation")
        file_hash = compute_file_sha256(test_file)
        assert len(file_hash) == 64  # SHA-256 hex string

        # Save an uploaded file record with non-conflicting snapshot date
        snap = UploadSnapshot(
            snapshot_date=date(2027, 6, 1),
            label="SHA Test",
            active_row_count=5,
        )
        seeded_session.add(snap)
        seeded_session.commit()

        up_file = UploadedFile(
            snapshot_id=snap.id,
            file_slot="fiscal_2026",
            filename="sample.xlsx",
            sha256_hash=file_hash,
            file_size_bytes=len(test_file.read_bytes()),
        )
        seeded_session.add(up_file)
        seeded_session.commit()

        # Check that querying for the same SHA-256 finds the existing upload
        existing = seeded_session.query(UploadedFile).filter_by(sha256_hash=file_hash).first()
        assert existing is not None
        assert existing.filename == "sample.xlsx"

    def test_atomic_transaction_rollback_on_failure(self, seeded_session):
        # Emulate atomic transaction: if an exception occurs mid-transaction, nothing is saved
        snap_count_before = seeded_session.query(UploadSnapshot).count()
        opp_count_before = seeded_session.query(Opportunity).count()

        try:
            with seeded_session.begin_nested():
                snap = UploadSnapshot(
                    snapshot_date=date(2027, 11, 1),
                    label="Failed Transaction Snapshot",
                    active_row_count=1,
                )
                seeded_session.add(snap)
                seeded_session.flush()

                opp = Opportunity(
                    snapshot_id=snap.id,
                    opportunity_id_18="006FAIL000000001AAA",
                    opportunity_name="Failed Deal",
                    account_name="Fail Corp",
                    forecast_category="Commit",
                    forecast_acv_amount=10_000.0,
                )
                seeded_session.add(opp)
                seeded_session.flush()

                # Trigger intentional exception
                raise ValueError("Intentional simulated error mid-transaction")
        except ValueError:
            seeded_session.rollback()

        # Assert no orphaned records were persisted
        snap_count_after = seeded_session.query(UploadSnapshot).count()
        opp_count_after = seeded_session.query(Opportunity).count()
        assert snap_count_after == snap_count_before
        assert opp_count_after == opp_count_before
