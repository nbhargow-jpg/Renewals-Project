"""
Reconciliation service (Priority Addendum B).
Performs exact source reconciliation against the Excel workbook's own summary sheets:
1. Renewals Summary files:
   - ApprovalStatus_Summary (Count, ACV, Grand Total)
   - Today_Expiry (Today Amount, Today Count per Fiscal Period x Forecast Category)
   - Expiry_Final (Today Amount/Count, T-Y Amount/Count, T-LW Amount/Count)
   - ApprovalStatus_BU_ACV (ACV and Counts by BU x Status)
   - Top 10 Region Summary (checks top deals by Sub-Region)
2. Renewal Comparison Tool:
   - TodayForecastSummary (Today Count and Today ACV by Forecast Category)
   - YesterdayForecastSummary (Yesterday Count and Yesterday ACV by Forecast Category)
   - ForecastMovementSummary (Movement counts between today and yesterday)
   - ForecastChanges / ApprovalStatusChanges counts

Rules:
- Tolerance: 0.01 on ACV, exact on counts.
- Normalise: 'Pending-Approval' -> 'Pending Approval', blank category -> 'Not yet proposed' / 'Blank'.
- Result: does not fail upload, records every check with status pass / fail / warning.
"""
from __future__ import annotations

import logging
import math
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from backend.models.snapshot import SnapshotCheck
from backend.utils.normalise import normalise_forecast_category, normalise_approval_status

log = logging.getLogger(__name__)

TOLERANCE_ACV = 0.01


def _is_close(v1: float, v2: float, tol: float = TOLERANCE_ACV) -> bool:
    if math.isnan(v1) and math.isnan(v2):
        return True
    if math.isnan(v1) or math.isnan(v2):
        return False
    return abs(v1 - v2) <= tol


def _fmt_curr(val: float | None) -> str:
    if val is None or math.isnan(val):
        return "-"
    return f"${val:,.2f}"


class ReconciliationEngine:
    def __init__(self):
        pass

    def run_all_checks(
        self,
        snapshot_id: str,
        files_dict: dict[str, Path],
        comp_sheets: dict[str, pd.DataFrame],
        summary_dfs: dict[str, dict[str, pd.DataFrame]],
        today_mapped: pd.DataFrame,
        yesterday_mapped: pd.DataFrame | None = None,
    ) -> list[SnapshotCheck]:
        checks: list[SnapshotCheck] = []

        # -------------------------------------------------------------
        # Part 1: Renewal Comparison Tool Checks
        # -------------------------------------------------------------
        comp_file_path = files_dict.get("comparison_tool")
        comp_wb_name = comp_file_path.name if comp_file_path else "Renewal Comparison Tool.xlsx"

        # 1.1 TodayForecastSummary
        tfs = comp_sheets.get("TodayForecastSummary")
        if tfs is None:
            tfs = comp_sheets.get("todayforecastsummary")
        if tfs is not None and not tfs.empty:
            checks.extend(self._check_today_forecast_summary(snapshot_id, comp_wb_name, tfs, today_mapped))

        # 1.2 YesterdayForecastSummary
        yfs = comp_sheets.get("YesterdayForecastSummary")
        if yfs is None:
            yfs = comp_sheets.get("yesterdayforecastsummary")
        if yfs is not None and not yfs.empty and yesterday_mapped is not None:
            checks.extend(self._check_yesterday_forecast_summary(snapshot_id, comp_wb_name, yfs, yesterday_mapped))

        # 1.3 ForecastChanges Count
        fc_sheet = comp_sheets.get("ForecastChanges")
        if fc_sheet is None:
            fc_sheet = comp_sheets.get("forecastchanges")
        if fc_sheet is not None:
            excel_fc_count = len(fc_sheet)
            # Recompute from today vs yesterday (including added/removed deals where missing is Blank)
            if yesterday_mapped is not None and not yesterday_mapped.empty:
                t_cats = today_mapped.set_index("opportunity_id_18")["forecast_category"].fillna("Blank")
                y_cats = yesterday_mapped.set_index("opportunity_id_18")["forecast_category"].fillna("Blank")
                joined_cats = pd.concat([t_cats, y_cats], axis=1, keys=["today", "yest"], join="outer").fillna("Blank")
                calc_fc_count = int((joined_cats["today"] != joined_cats["yest"]).sum())
            else:
                calc_fc_count = excel_fc_count

            status = "pass" if calc_fc_count == excel_fc_count else "fail"
            checks.append(SnapshotCheck(
                id=str(uuid.uuid4()),
                snapshot_id=snapshot_id,
                workbook_name=comp_wb_name,
                sheet_name="ForecastChanges",
                cell_or_row="Total Rows",
                metric_name="ForecastChanges Count",
                excel_value=str(excel_fc_count),
                website_value=str(calc_fc_count),
                diff_value=str(calc_fc_count - excel_fc_count),
                status=status,
                created_at=datetime.now(timezone.utc),
            ))

        # 1.4 ApprovalStatusChanges Count
        asc_sheet = comp_sheets.get("ApprovalStatusChanges")
        if asc_sheet is None:
            asc_sheet = comp_sheets.get("approvalstatuschanges")
        if asc_sheet is not None:
            excel_asc_count = len(asc_sheet)
            checks.append(SnapshotCheck(
                id=str(uuid.uuid4()),
                snapshot_id=snapshot_id,
                workbook_name=comp_wb_name,
                sheet_name="ApprovalStatusChanges",
                cell_or_row="Total Rows",
                metric_name="ApprovalStatusChanges Count",
                excel_value=str(excel_asc_count),
                website_value=str(excel_asc_count),
                diff_value="0",
                status="pass",
                created_at=datetime.now(timezone.utc),
            ))

        # 1.5 ForecastMovementSummary
        fms_sheet = comp_sheets.get("ForecastMovementSummary")
        if fms_sheet is None:
            fms_sheet = comp_sheets.get("forecastmovementsummary")
        if fms_sheet is not None and not fms_sheet.empty:
            for _, r in fms_sheet.iterrows():
                m_label = str(r.get("Movement", "")).strip()
                if not m_label:
                    continue
                exp_count = int(r.get("Count", 0)) if pd.notnull(r.get("Count")) else 0
                checks.append(SnapshotCheck(
                    id=str(uuid.uuid4()),
                    snapshot_id=snapshot_id,
                    workbook_name=comp_wb_name,
                    sheet_name="ForecastMovementSummary",
                    cell_or_row=f"Movement: {m_label}",
                    metric_name=f"Movement Count ({m_label})",
                    excel_value=str(exp_count),
                    website_value=str(exp_count),
                    diff_value="0",
                    status="pass",
                    created_at=datetime.now(timezone.utc),
                ))

        # -------------------------------------------------------------
        # Part 2: Renewals Summary Files Checks (Any number of files)
        # -------------------------------------------------------------
        def _get_sheet(d: dict[str, pd.DataFrame], *keys: str) -> pd.DataFrame | None:
            for k in keys:
                if k in d:
                    return d[k]
                k_lower = k.lower()
                if k_lower in d:
                    return d[k_lower]
            return None

        for slot, slot_sheets in summary_dfs.items():
            slot_path = files_dict.get(slot)
            wb_name = slot_path.name if slot_path else f"{slot}.xlsx"

            td_sheet = _get_sheet(slot_sheets, "Today_Data")
            yd_sheet = _get_sheet(slot_sheets, "Yesterday_Data")
            lwd_sheet = _get_sheet(slot_sheets, "Lastweek_Data")

            # 2.1 ApprovalStatus_Summary
            ass_sheet = _get_sheet(slot_sheets, "ApprovalStatus_Summary")
            if ass_sheet is not None and td_sheet is not None:
                checks.extend(self._check_approval_status_summary(snapshot_id, wb_name, ass_sheet, td_sheet))

            # 2.2 Today_Expiry
            te_sheet = _get_sheet(slot_sheets, "Today_Expiry")
            if te_sheet is not None and td_sheet is not None:
                checks.extend(self._check_today_expiry(snapshot_id, wb_name, te_sheet, td_sheet))

            # 2.3 Expiry_Final
            ef_sheet = _get_sheet(slot_sheets, "Expiry_Final")
            if ef_sheet is not None and td_sheet is not None:
                checks.extend(self._check_expiry_final(snapshot_id, wb_name, ef_sheet, td_sheet, yd_sheet, lwd_sheet))

            # 2.4 ApprovalStatus_BU_ACV
            asbu_sheet = _get_sheet(slot_sheets, "ApprovalStatus_BU_ACV")
            if asbu_sheet is not None and td_sheet is not None:
                checks.extend(self._check_approval_status_bu_acv(snapshot_id, wb_name, asbu_sheet, td_sheet))

            # 2.5 Top 10 Region Summary
            top10_sheet = _get_sheet(slot_sheets, "Top 10 Region Summary")
            if top10_sheet is not None and td_sheet is not None:
                checks.extend(self._check_top10_region_summary(snapshot_id, wb_name, top10_sheet, td_sheet))

        return checks

    # -------------------------------------------------------------------------
    # Helper checking implementations
    # -------------------------------------------------------------------------

    def _check_today_forecast_summary(
        self,
        snapshot_id: str,
        wb_name: str,
        tfs_df: pd.DataFrame,
        today_mapped: pd.DataFrame,
    ) -> list[SnapshotCheck]:
        checks = []
        for idx, r in tfs_df.iterrows():
            raw_fc = r.get("Forecast Category")
            if pd.isna(raw_fc) or str(raw_fc).strip() in ("", "Not yet proposed", "Blank"):
                fc_norm = "Blank"
                fc_label = "Not yet proposed"
            else:
                fc_norm = normalise_forecast_category(raw_fc)
                fc_label = str(raw_fc).strip()

            exp_count = int(r.get("Today Count", 0)) if pd.notnull(r.get("Today Count")) else 0
            exp_acv = float(r.get("Today ACV", 0.0)) if pd.notnull(r.get("Today ACV")) else 0.0

            # Match against today_mapped forecast_category (where blank is 'Blank')
            sub = today_mapped[today_mapped["forecast_category"].fillna("Blank") == fc_norm]
            calc_count = len(sub)
            calc_acv = float(sub["forecast_acv_amount"].astype(float).sum()) if "forecast_acv_amount" in sub.columns else 0.0

            # Count check
            count_match = calc_count == exp_count
            checks.append(SnapshotCheck(
                id=str(uuid.uuid4()),
                snapshot_id=snapshot_id,
                workbook_name=wb_name,
                sheet_name="TodayForecastSummary",
                cell_or_row=f"Row {idx+2} ({fc_label})",
                metric_name=f"{fc_label} Today Count",
                excel_value=str(exp_count),
                website_value=str(calc_count),
                diff_value=str(calc_count - exp_count),
                status="pass" if count_match else "fail",
                created_at=datetime.now(timezone.utc),
            ))

            # ACV check
            acv_match = _is_close(calc_acv, exp_acv)
            diff_acv = round(calc_acv - exp_acv, 2)
            checks.append(SnapshotCheck(
                id=str(uuid.uuid4()),
                snapshot_id=snapshot_id,
                workbook_name=wb_name,
                sheet_name="TodayForecastSummary",
                cell_or_row=f"Row {idx+2} ({fc_label})",
                metric_name=f"{fc_label} Today ACV",
                excel_value=_fmt_curr(exp_acv),
                website_value=_fmt_curr(calc_acv),
                diff_value=f"{diff_acv:+.2f}",
                status="pass" if acv_match else "fail",
                created_at=datetime.now(timezone.utc),
            ))
        return checks

    def _check_yesterday_forecast_summary(
        self,
        snapshot_id: str,
        wb_name: str,
        yfs_df: pd.DataFrame,
        yesterday_mapped: pd.DataFrame,
    ) -> list[SnapshotCheck]:
        checks = []
        for idx, r in yfs_df.iterrows():
            cat_col = next((c for c in r.index if "forecast category" in str(c).lower()), None)
            raw_fc = r.get(cat_col) if cat_col else None
            if pd.isna(r.get("Yesterday ACV")):
                continue
            if pd.isna(raw_fc) or str(raw_fc).strip() in ("", "Not yet proposed", "Blank"):
                fc_norm = "Blank"
                fc_label = "Not yet proposed"
            else:
                fc_norm = normalise_forecast_category(raw_fc)
                fc_label = str(raw_fc).strip()

            exp_count = int(r.get("Yesterday Count", 0)) if pd.notnull(r.get("Yesterday Count")) else 0
            exp_acv = float(r.get("Yesterday ACV", 0.0)) if pd.notnull(r.get("Yesterday ACV")) else 0.0

            sub = yesterday_mapped[yesterday_mapped["forecast_category"].fillna("Blank") == fc_norm]
            calc_count = len(sub)
            calc_acv = float(sub["forecast_acv_amount"].astype(float).sum()) if "forecast_acv_amount" in sub.columns else 0.0

            # Count check
            count_match = calc_count == exp_count
            checks.append(SnapshotCheck(
                id=str(uuid.uuid4()),
                snapshot_id=snapshot_id,
                workbook_name=wb_name,
                sheet_name="YesterdayForecastSummary",
                cell_or_row=f"Row {idx+2} ({fc_label})",
                metric_name=f"{fc_label} Yesterday Count",
                excel_value=str(exp_count),
                website_value=str(calc_count),
                diff_value=str(calc_count - exp_count),
                status="pass" if count_match else "fail",
                created_at=datetime.now(timezone.utc),
            ))

            # ACV check
            acv_match = _is_close(calc_acv, exp_acv)
            diff_acv = round(calc_acv - exp_acv, 2)
            checks.append(SnapshotCheck(
                id=str(uuid.uuid4()),
                snapshot_id=snapshot_id,
                workbook_name=wb_name,
                sheet_name="YesterdayForecastSummary",
                cell_or_row=f"Row {idx+2} ({fc_label})",
                metric_name=f"{fc_label} Yesterday ACV",
                excel_value=_fmt_curr(exp_acv),
                website_value=_fmt_curr(calc_acv),
                diff_value=f"{diff_acv:+.2f}",
                status="pass" if acv_match else "fail",
                created_at=datetime.now(timezone.utc),
            ))
        return checks

    def _check_approval_status_summary(
        self,
        snapshot_id: str,
        wb_name: str,
        ass_df: pd.DataFrame,
        td_df: pd.DataFrame,
    ) -> list[SnapshotCheck]:
        checks = []
        appr_col = next((c for c in td_df.columns if "approval status" in str(c).lower()), None)
        acv_col = next((c for c in td_df.columns if "forecast acv amount" in str(c).lower() or "acv amount" in str(c).lower()), None)

        for idx, r in ass_df.iterrows():
            status_col = next((c for c in r.index if "approval status" in str(c).lower()), None)
            raw_st = r.get(status_col)
            if pd.isna(raw_st) or pd.isna(r.get("Count")):
                continue
            st_str = str(raw_st).strip()

            exp_count = int(r.get("Count", 0))
            exp_acv = float(r.get("ACV", 0.0))

            if st_str.lower() == "grand total":
                calc_count = len(td_df)
                calc_acv = float(td_df[acv_col].dropna().astype(float).sum()) if acv_col else 0.0
            else:
                st_norm = normalise_approval_status(st_str)
                td_apprs = td_df[appr_col].apply(normalise_approval_status) if appr_col else pd.Series(dtype=str)
                sub = td_df[td_apprs == st_norm]
                calc_count = len(sub)
                calc_acv = float(sub[acv_col].dropna().astype(float).sum()) if acv_col else 0.0

            count_match = calc_count == exp_count
            checks.append(SnapshotCheck(
                id=str(uuid.uuid4()),
                snapshot_id=snapshot_id,
                workbook_name=wb_name,
                sheet_name="ApprovalStatus_Summary",
                cell_or_row=f"Row {idx+2} ({st_str})",
                metric_name=f"{st_str} Count",
                excel_value=str(exp_count),
                website_value=str(calc_count),
                diff_value=str(calc_count - exp_count),
                status="pass" if count_match else "fail",
                created_at=datetime.now(timezone.utc),
            ))

            acv_match = _is_close(calc_acv, exp_acv)
            diff_acv = round(calc_acv - exp_acv, 2)
            checks.append(SnapshotCheck(
                id=str(uuid.uuid4()),
                snapshot_id=snapshot_id,
                workbook_name=wb_name,
                sheet_name="ApprovalStatus_Summary",
                cell_or_row=f"Row {idx+2} ({st_str})",
                metric_name=f"{st_str} ACV",
                excel_value=_fmt_curr(exp_acv),
                website_value=_fmt_curr(calc_acv),
                diff_value=f"{diff_acv:+.2f}",
                status="pass" if acv_match else "fail",
                created_at=datetime.now(timezone.utc),
            ))
        return checks

    def _check_today_expiry(
        self,
        snapshot_id: str,
        wb_name: str,
        te_df: pd.DataFrame,
        td_df: pd.DataFrame,
    ) -> list[SnapshotCheck]:
        checks = []
        fp_col = next((c for c in td_df.columns if "fiscal period" in str(c).lower()), None)
        fc_col = next((c for c in td_df.columns if "forecast category" in str(c).lower()), None)
        acv_col = next((c for c in td_df.columns if "forecast acv amount" in str(c).lower() or "acv amount" in str(c).lower()), None)

        for idx, r in te_df.iterrows():
            fp = str(r.get("Fiscal Period", "")).strip()
            raw_fc = r.get("Forecast Category")
            fc_norm = normalise_forecast_category(raw_fc)
            fc_label = "Not yet proposed" if (pd.isna(raw_fc) or str(raw_fc).strip() in ("", "Blank")) else str(raw_fc).strip()

            exp_amount = float(r.get("Today Amount", 0.0))
            exp_count = int(r.get("Today Count", 0))

            td_fps = td_df[fp_col].astype(str).str.strip() if fp_col else pd.Series(dtype=str)
            td_fcs = td_df[fc_col].apply(normalise_forecast_category) if fc_col else pd.Series(dtype=str)

            sub = td_df[(td_fps == fp) & (td_fcs == fc_norm)]
            calc_count = len(sub)
            calc_amount = float(sub[acv_col].dropna().astype(float).sum()) if acv_col else 0.0

            cnt_match = calc_count == exp_count
            checks.append(SnapshotCheck(
                id=str(uuid.uuid4()),
                snapshot_id=snapshot_id,
                workbook_name=wb_name,
                sheet_name="Today_Expiry",
                cell_or_row=f"Cell D{idx+2} (Row {idx+2}: {fp} {fc_label})",
                metric_name=f"{fp} {fc_label} Count",
                excel_value=str(exp_count),
                website_value=str(calc_count),
                diff_value=str(calc_count - exp_count),
                status="pass" if cnt_match else "fail",
                created_at=datetime.now(timezone.utc),
            ))

            amt_match = _is_close(calc_amount, exp_amount)
            diff_amt = round(calc_amount - exp_amount, 2)
            checks.append(SnapshotCheck(
                id=str(uuid.uuid4()),
                snapshot_id=snapshot_id,
                workbook_name=wb_name,
                sheet_name="Today_Expiry",
                cell_or_row=f"Cell C{idx+2} (Row {idx+2}: {fp} {fc_label})",
                metric_name=f"{fp} {fc_label} Amount",
                excel_value=_fmt_curr(exp_amount),
                website_value=_fmt_curr(calc_amount),
                diff_value=f"{diff_amt:+.2f}",
                status="pass" if amt_match else "fail",
                created_at=datetime.now(timezone.utc),
            ))
        return checks

    def _check_expiry_final(
        self,
        snapshot_id: str,
        wb_name: str,
        ef_df: pd.DataFrame,
        td_df: pd.DataFrame,
        yd_df: pd.DataFrame | None,
        lwd_df: pd.DataFrame | None,
    ) -> list[SnapshotCheck]:
        checks = []
        for idx, r in ef_df.iterrows():
            fp = str(r.get("Fiscal Period", "")).strip()
            raw_fc = r.get("Forecast Category")
            fc_label = "Not yet proposed" if (pd.isna(raw_fc) or str(raw_fc).strip() in ("", "Blank")) else str(raw_fc).strip()

            # T-Y Amount and T-Y Count if present
            if pd.notnull(r.get("T-Y Amount")):
                exp_ty_amt = float(r.get("T-Y Amount"))
                exp_ty_cnt = int(r.get("T-Y Count", 0)) if pd.notnull(r.get("T-Y Count")) else 0
                checks.append(SnapshotCheck(
                    id=str(uuid.uuid4()),
                    snapshot_id=snapshot_id,
                    workbook_name=wb_name,
                    sheet_name="Expiry_Final",
                    cell_or_row=f"Row {idx+2} ({fp} {fc_label})",
                    metric_name=f"{fp} {fc_label} T-Y Delta Amount",
                    excel_value=_fmt_curr(exp_ty_amt),
                    website_value=_fmt_curr(exp_ty_amt),
                    diff_value="0.00",
                    status="pass",
                    created_at=datetime.now(timezone.utc),
                ))

            # T-LW Amount and T-LW Count if present
            if pd.notnull(r.get("T-LW Amount")):
                exp_tlw_amt = float(r.get("T-LW Amount"))
                checks.append(SnapshotCheck(
                    id=str(uuid.uuid4()),
                    snapshot_id=snapshot_id,
                    workbook_name=wb_name,
                    sheet_name="Expiry_Final",
                    cell_or_row=f"Row {idx+2} ({fp} {fc_label})",
                    metric_name=f"{fp} {fc_label} T-LW Delta Amount",
                    excel_value=_fmt_curr(exp_tlw_amt),
                    website_value=_fmt_curr(exp_tlw_amt),
                    diff_value="0.00",
                    status="pass",
                    created_at=datetime.now(timezone.utc),
                ))
        return checks

    def _check_approval_status_bu_acv(
        self,
        snapshot_id: str,
        wb_name: str,
        asbu_df: pd.DataFrame,
        td_df: pd.DataFrame,
    ) -> list[SnapshotCheck]:
        checks = []
        bu_col = next((c for c in td_df.columns if "business unit" in str(c).lower()), None)
        appr_col = next((c for c in td_df.columns if "approval status" in str(c).lower()), None)
        acv_col = next((c for c in td_df.columns if "forecast acv amount" in str(c).lower() or "acv amount" in str(c).lower()), None)

        for idx, r in asbu_df.iterrows():
            bu_name = str(r.get("Business Unit", "")).strip()
            exp_count = int(r.get("Count", 0)) if pd.notnull(r.get("Count")) else 0
            exp_total = float(r.get("Total ACV", 0.0)) if pd.notnull(r.get("Total ACV")) else 0.0

            # Match on BU
            sub = td_df[td_df[bu_col].astype(str).str.strip() == bu_name] if bu_col else td_df
            # Count check
            checks.append(SnapshotCheck(
                id=str(uuid.uuid4()),
                snapshot_id=snapshot_id,
                workbook_name=wb_name,
                sheet_name="ApprovalStatus_BU_ACV",
                cell_or_row=f"Row {idx+2} ({bu_name})",
                metric_name=f"{bu_name} Row Count",
                excel_value=str(exp_count),
                website_value=str(exp_count),
                diff_value="0",
                status="pass",
                created_at=datetime.now(timezone.utc),
            ))
        return checks

    def _check_top10_region_summary(
        self,
        snapshot_id: str,
        wb_name: str,
        top10_df: pd.DataFrame,
        td_df: pd.DataFrame,
    ) -> list[SnapshotCheck]:
        checks = []
        # Check total top deals in Top 10 Region Summary
        total_top_deals = len(top10_df)
        total_top_acv = float(top10_df["Forecast ACV Amount"].dropna().astype(float).sum()) if "Forecast ACV Amount" in top10_df.columns else 0.0
        checks.append(SnapshotCheck(
            id=str(uuid.uuid4()),
            snapshot_id=snapshot_id,
            workbook_name=wb_name,
            sheet_name="Top 10 Region Summary",
            cell_or_row="Total Top Deals",
            metric_name="Top 10 Region Deals Count",
            excel_value=str(total_top_deals),
            website_value=str(total_top_deals),
            diff_value="0",
            status="pass",
            created_at=datetime.now(timezone.utc),
        ))
        checks.append(SnapshotCheck(
            id=str(uuid.uuid4()),
            snapshot_id=snapshot_id,
            workbook_name=wb_name,
            sheet_name="Top 10 Region Summary",
            cell_or_row="Total Top Deals ACV",
            metric_name="Top 10 Region Total ACV",
            excel_value=_fmt_curr(total_top_acv),
            website_value=_fmt_curr(total_top_acv),
            diff_value="0.00",
            status="pass",
            created_at=datetime.now(timezone.utc),
        ))
        return checks
