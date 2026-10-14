"""
IngestService — handles daily 4-file upload, slot detection, pre-commit validation,
reconciliation against pivot sheets, and atomic commit of snapshot with scopes.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.snapshot import UploadSnapshot, UploadedFile, SnapshotCheck
from backend.models.opportunity import Opportunity
from backend.models.daily_summary import DailySummary
from backend.models.change_log import ChangeLog, ForecastMovementLog
from backend.services.context import UserContext
from backend.services.reconciliation import ReconciliationEngine
from backend.utils.excel_parser import (
    detect_file_slot,
    compute_file_sha256,
    detect_suggested_snapshot_date,
    _normalise_col,
    _map_columns,
    RENEWALS_COLUMN_MAP,
    parse_comparison_tool,
    parse_summary_workbook,
    parse_renewals_summary,
    parse_excel_date,
    parse_excel_datetime,
    clean_record,
    _open,
)
from backend.utils.normalise import (
    normalise_approval_status,
    normalise_forecast_category,
    primary_business_unit,
    to_decimal,
)

log = logging.getLogger(__name__)

_UPLOAD_SESSIONS: dict[str, dict[str, Any]] = {}

def detect_schema_drift(current_cols: list[str] | set[str], previous_cols: list[str] | set[str]) -> list[str]:
    """Detect schema drift both ways: new columns appeared or known columns disappeared."""
    curr = set(current_cols)
    prev = set(previous_cols)
    new_cols = curr - prev
    lost_cols = prev - curr
    warnings: list[str] = []
    if new_cols:
        for c in sorted(new_cols):
            warnings.append(f"Schema drift: New column '{c}' detected.")
    if lost_cols:
        for c in sorted(lost_cols):
            warnings.append(f"Schema drift: Known column '{c}' disappeared versus previous snapshot.")
    return warnings

def _get_sessions_storage_dir() -> Path:
    from backend.config import settings, ROOT_DIR
    upload_dir = getattr(settings, "UPLOAD_DIR", None)
    if upload_dir:
        base = Path(upload_dir) / "sessions"
    else:
        base = ROOT_DIR / "scratch" / "upload_sessions"
    base.mkdir(parents=True, exist_ok=True)
    return base

def _save_session_to_disk(session_id: str, data: dict[str, Any]) -> None:
    _UPLOAD_SESSIONS[session_id] = data
    try:
        import pickle
        p = _get_sessions_storage_dir() / f"{session_id}.pkl"
        with p.open("wb") as f:
            pickle.dump({
                "created_at": datetime.now(timezone.utc),
                "data": data,
            }, f)
    except Exception as exc:
        log.warning("Could not persist upload session %s to disk: %s", session_id, exc)

def _get_session_from_disk(session_id: str) -> dict[str, Any] | None:
    # Check in-memory first
    if session_id in _UPLOAD_SESSIONS:
        return _UPLOAD_SESSIONS[session_id]
    p = _get_sessions_storage_dir() / f"{session_id}.pkl"
    if p.exists():
        try:
            import pickle
            with p.open("rb") as f:
                saved = pickle.load(f)
            created_at = saved.get("created_at")
            if created_at and (datetime.now(timezone.utc) - created_at) > timedelta(hours=24):
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
                return None
            data = saved.get("data")
            if data:
                _UPLOAD_SESSIONS[session_id] = data
                return data
        except Exception as exc:
            log.warning("Could not load upload session %s from disk: %s", session_id, exc)
    return None

def _delete_session(session_id: str) -> None:
    _UPLOAD_SESSIONS.pop(session_id, None)
    try:
        p = _get_sessions_storage_dir() / f"{session_id}.pkl"
        p.unlink(missing_ok=True)
    except Exception:
        pass


def compute_previous_working_day(d: date) -> date:
    weekday = d.weekday()  # Monday=0, Sunday=6
    if weekday == 0:
        return d - timedelta(days=3)
    elif weekday == 6:
        return d - timedelta(days=2)
    elif weekday == 5:
        return d - timedelta(days=1)
    else:
        return d - timedelta(days=1)


def _coerce_date(val) -> date | None:
    return parse_excel_date(val)


def _coerce_datetime(val) -> datetime | None:
    return parse_excel_datetime(val)


# Snapshots built from the comparison/summary files of a LATER day (not uploaded as their own day)
AUTO_SNAPSHOT_SOURCES = ("comparison_tool_yesterday", "summary_lastweek_union")


def _coerce_float(val) -> float | None:
    if val is None:
        return None
    try:
        s = str(val).strip().replace(",", "")
        return float(s) if s and s.lower() != "nan" else None
    except (ValueError, TypeError):
        return None


def _coerce_int(val) -> int | None:
    f = _coerce_float(val)
    return int(f) if f is not None else None


def _safe_str(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ("nan", "none", "nat") else None


class IngestService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 4-File Upload Validation & Preview
    # ------------------------------------------------------------------

    def validate_upload(
        self,
        ctx: UserContext,
        files_dict: dict[str, Path],
        data_as_of: date,
        yesterday_date: date | None = None,
    ) -> dict[str, Any]:
        if yesterday_date is None:
            yesterday_date = compute_previous_working_day(data_as_of)

        errors: list[str] = []
        warnings: list[str] = []
        file_metadata: list[dict[str, Any]] = []

        # 1. Verify Comparison Tool is present
        comp_path = files_dict.get("comparison_tool")
        if not comp_path or not comp_path.exists():
            errors.append("Renewal Comparison Tool is mandatory but was not uploaded.")
            return {"errors": errors, "warnings": warnings, "can_commit": False, "session_id": None}

        # 2. Check slots, signatures, and SHA-256 hashes
        all_hashes: dict[str, str] = {}
        xf_cache: dict[str, pd.ExcelFile] = {}
        for slot, path in files_dict.items():
            if not path or not path.exists():
                continue
            sha = compute_file_sha256(path)
            all_hashes[slot] = sha

            try:
                xf_cache[slot] = _open(path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            detected_slot, detected_desc = detect_file_slot(path, xf_cache[slot])
            if detected_slot != "unknown" and detected_slot != slot:
                warnings.append(
                    f"File in slot '{slot}' ({path.name}) appears to be '{detected_slot}': {detected_desc}"
                )

            existing_upload = (
                self.db.query(UploadedFile)
                .filter(UploadedFile.sha256_hash == sha)
                .first()
            )
            if existing_upload:
                snap_date_str = (
                    str(existing_upload.snapshot.snapshot_date)
                    if existing_upload.snapshot
                    else "an earlier snapshot"
                )
                warnings.append(
                    f"File '{path.name}' has identical content (SHA-256) to an earlier upload on snapshot date {snap_date_str}."
                )

            file_metadata.append({
                "slot": slot,
                "detected_slot": detected_slot,
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": sha,
            })

        if errors:
            return {"errors": errors, "warnings": warnings, "can_commit": False, "session_id": None}

        # Check if snapshot already exists for this date
        existing_snap = (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.snapshot_date == data_as_of)
            .first()
        )
        snapshot_exists = existing_snap is not None
        if snapshot_exists:
            warnings.append(
                f"A snapshot already exists for {data_as_of.isoformat()} ({existing_snap.row_count} rows). Confirming will ask to replace."
            )

        if data_as_of.weekday() in (5, 6):
            warnings.append(
                f"Data as of date {data_as_of.isoformat()} falls on a weekend ({data_as_of.strftime('%A')})."
            )

        # 3. Parse Comparison Tool sheets
        try:
            comp_sheets = parse_comparison_tool(comp_path, xf_cache.get("comparison_tool"))
        except Exception as exc:
            errors.append(f"Failed to read Comparison Tool: {exc}")
            return {"errors": errors, "warnings": warnings, "can_commit": False, "session_id": None}

        today_raw = comp_sheets.get("today")
        yesterday_raw = comp_sheets.get("yesterday")

        if today_raw is None or today_raw.empty:
            errors.append("Comparison Tool is missing the mandatory 'today' sheet or it is empty.")
        if yesterday_raw is None:
            warnings.append("Comparison Tool is missing the 'yesterday' sheet; comparisons against yesterday will be limited.")

        if errors:
            return {"errors": errors, "warnings": warnings, "can_commit": False, "session_id": None}

        today_mapped = _map_columns(today_raw)
        required_cols = [
            ("opportunity_id_18", "Opportunity ID 18 Digit"),
            ("forecast_acv_amount", "Forecast ACV Amount"),
            ("forecast_category", "Forecast Category"),
            ("close_date", "Close Date"),
        ]
        # --- Item 2 & 3: Date detection and yesterday / last week resolution ---
        suggested_date = None
        for p in files_dict.values():
            if p and p.exists():
                sd = detect_suggested_snapshot_date(p, xf_cache.get(p.name))
                if sd:
                    suggested_date = sd
                    break

        if suggested_date and suggested_date != data_as_of:
            warnings.append(
                f"Suggested as-of date from uploaded workbook is {suggested_date.isoformat()}, but entered date is {data_as_of.isoformat()}."
            )

        # Yesterday resolution:
        # a) Latest snapshot ALREADY IN THE DATABASE before as-of within previous 5 days (e.g. Monday -> Friday, holiday gap)
        earliest_yesterday_window = data_as_of - timedelta(days=5)
        db_prev_snap = (
            self.db.query(UploadSnapshot)
            .filter(
                UploadSnapshot.snapshot_date < data_as_of,
                UploadSnapshot.snapshot_date >= earliest_yesterday_window,
                UploadSnapshot.uploaded_by.notin_(AUTO_SNAPSHOT_SOURCES)
            )
            .order_by(UploadSnapshot.snapshot_date.desc())
            .first()
        )
        if not db_prev_snap:
            # Fallback check any previous snapshot in DB within 5 days
            db_prev_snap = (
                self.db.query(UploadSnapshot)
                .filter(
                    UploadSnapshot.snapshot_date < data_as_of,
                    UploadSnapshot.snapshot_date >= earliest_yesterday_window
                )
                .order_by(UploadSnapshot.snapshot_date.desc())
                .first()
            )

        resolved_yesterday_date: date
        yesterday_source_desc: str
        if db_prev_snap:
            resolved_yesterday_date = db_prev_snap.snapshot_date
            yesterday_source_desc = f"from database snapshot ({db_prev_snap.snapshot_date.isoformat()})"
        else:
            if yesterday_date:
                resolved_yesterday_date = yesterday_date
            else:
                resolved_yesterday_date = compute_previous_working_day(data_as_of)
            yesterday_source_desc = "from file (bootstrapped from Yesterday_Data sheet)"

        # Last week resolution:
        last_week_target = data_as_of - timedelta(days=7)
        db_lw_snap = (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.snapshot_date == last_week_target)
            .first()
        )
        real_lw_snap = db_lw_snap if db_lw_snap and db_lw_snap.uploaded_by not in AUTO_SNAPSHOT_SOURCES else None
        last_week_source_desc: str
        last_week_is_partial: bool
        if real_lw_snap:
            last_week_source_desc = f"from database snapshot ({last_week_target.isoformat()})"
            last_week_is_partial = False
        else:
            last_week_source_desc = "from file (bootstrapped from Lastweek_Data sheet - flagged partial)"
            last_week_is_partial = True

        # Existing snapshot details if overwriting (Item 4)
        existing_snap_info = None
        if existing_snap:
            existing_acv = (
                self.db.query(func.sum(Opportunity.forecast_acv_amount))
                .filter(Opportunity.snapshot_id == existing_snap.id)
                .scalar()
            ) or 0.0
            existing_snap_info = {
                "snapshot_date": existing_snap.snapshot_date.isoformat(),
                "row_count": existing_snap.row_count,
                "active_row_count": existing_snap.active_row_count,
                "total_acv": float(existing_acv),
                "uploaded_at": existing_snap.uploaded_at.isoformat() if existing_snap.uploaded_at else None,
                "uploaded_by": existing_snap.uploaded_by or "system",
                "files": [f.filename for f in existing_snap.uploaded_files],
            }

        missing_columns: list[str] = []
        for col_key, col_display in required_cols:
            if col_key not in today_mapped.columns:
                missing_columns.append(col_display)
                errors.append(f"Comparison Tool 'today' sheet is missing required column '{col_display}'.")

        # Unmapped regions list (Item 5)
        unmapped_regions_list: list[str] = []
        if "revised_sub_region" in today_mapped.columns:
            unmapped_series = today_mapped[
                today_mapped["revised_sub_region"].isna() |
                (today_mapped["revised_sub_region"].astype(str).str.strip().isin(["", "nan", "None"]))
            ]
            if len(unmapped_series) > 0:
                raw_regs = today_mapped.loc[unmapped_series.index, "sub_region"].dropna().unique().tolist() if "sub_region" in today_mapped.columns else []
                unmapped_regions_list = [str(r) for r in raw_regs[:10]]
                warnings.append(
                    f"Comparison Tool 'today' sheet contains {len(unmapped_series)} rows with unmapped or blank revised sub-regions ({', '.join(unmapped_regions_list) if unmapped_regions_list else 'Blank'})."
                )

        today_ids = today_mapped["opportunity_id_18"].dropna().astype(str).str.strip()
        dupes = today_ids[today_ids.duplicated()].unique()
        if len(dupes) > 0:
            errors.append(f"Comparison Tool 'today' sheet contains duplicate Opportunity IDs: {list(dupes)[:5]}")

        acv_series = today_mapped["forecast_acv_amount"].dropna()
        non_numeric_acv = pd.to_numeric(acv_series.astype(str).str.replace(",", "").str.strip(), errors="coerce").isna().sum()
        if non_numeric_acv > 0:
            errors.append(f"Comparison Tool 'today' sheet contains {non_numeric_acv} non-numeric ACV entries.")

        if errors:
            return {
                "errors": errors,
                "warnings": warnings,
                "missing_columns": missing_columns,
                "unmapped_regions": unmapped_regions_list,
                "can_commit": False,
                "session_id": None,
                "files": file_metadata,
            }

        # 4. Parse Summary Workbooks (Addendum C: dynamic for any number of summary files)
        summary_dfs: dict[str, dict[str, pd.DataFrame]] = {}
        for slot, slot_path in files_dict.items():
            if slot == "comparison_tool" or not slot_path or not slot_path.exists():
                continue
            try:
                s_sheets = parse_summary_workbook(slot_path, xf_cache.get(slot))
                summary_dfs[slot] = s_sheets
            except Exception as exc:
                warnings.append(f"Warning reading {slot_path.name}: {exc}")

        # 5. Compute Scope Metrics
        from backend.services.scopes import ScopeService
        
        stage_col = next((c for c in today_mapped.columns if c in ("stage_number", "stage")), None)

        def _metrics_for(df_sub):
            raw_cnt = len(df_sub)
            raw_acv = float(df_sub["forecast_acv_amount"].astype(float).sum()) if "forecast_acv_amount" in df_sub.columns else 0.0
            if stage_col:
                del_mask = df_sub[stage_col].astype(str).str.strip().isin(["Deleted", "Lost"])
                active_sub = df_sub[~del_mask]
            else:
                active_sub = df_sub
            active_cnt = len(active_sub)
            active_acv = float(active_sub["forecast_acv_amount"].astype(float).sum()) if "forecast_acv_amount" in active_sub.columns else 0.0
            deleted_lost_cnt = raw_cnt - active_cnt
            return {
                "raw_count": raw_cnt,
                "raw_acv": round(raw_acv, 2),
                "active_count": active_cnt,
                "active_acv": round(active_acv, 2),
                "deleted_lost_count": deleted_lost_cnt,
            }

        ren_mask = today_mapped.get("sales_type", pd.Series(dtype=str)).astype(str).str.strip() == "Renewals"
        renewals_df = today_mapped[ren_mask]
        
        cq = ScopeService.current_quarter(data_as_of)
        cq_mask = today_mapped.get("fiscal_period", pd.Series(dtype=str)).astype(str).str.strip() == cq
        current_quarter_df = renewals_df[renewals_df.index.isin(today_mapped[cq_mask].index)]

        scopes_summary = {
            "all": {**_metrics_for(today_mapped), "available": True, "label": "All Opportunities"},
            "renewals": {
                **_metrics_for(renewals_df),
                "available": True,
                "label": "Renewals",
            },
            "current_quarter": {
                **_metrics_for(current_quarter_df),
                "available": True,
                "label": ScopeService.quarter_label(cq),
            },
        }

        # Two-way Schema Drift Detection (Addendum C: new columns and disappeared columns)
        schema_drift_warnings: list[str] = []
        prev_snap = (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.snapshot_date < data_as_of)
            .order_by(UploadSnapshot.snapshot_date.desc())
            .first()
        )
        if prev_snap:
            # Check extra_attributes of an opportunity from previous snapshot
            prev_opp = self.db.query(Opportunity).filter(Opportunity.snapshot_id == prev_snap.id).first()
            if prev_opp and prev_opp.extra_attributes:
                prev_cols = set(prev_opp.extra_attributes.keys())
                curr_cols = set(today_raw.columns) if today_raw is not None else set()
                drift_msgs = detect_schema_drift(curr_cols, prev_cols)
                warnings.extend(drift_msgs)
                schema_drift_warnings.extend(drift_msgs)

        if prev_snap and prev_snap.row_count > 0:
            diff_pct = abs(len(today_mapped) - prev_snap.row_count) / prev_snap.row_count * 100
            if diff_pct > 5.0:
                warnings.append(
                    f"Row count moved by {diff_pct:.1f}% vs previous snapshot ({prev_snap.snapshot_date}: {prev_snap.row_count} rows -> today: {len(today_mapped)} rows)."
                )

        # 6. Reconcile FinalChangeReport
        fcr = comp_sheets.get("finalchangereport")
        fcr_count = len(fcr) if fcr is not None and not fcr.empty else None

        # 7. Pre-compute Source Reconciliation Checks (Addendum B)
        reconciler = ReconciliationEngine()
        y_mapped = _map_columns(yesterday_raw) if yesterday_raw is not None and not yesterday_raw.empty else None
        preview_checks = reconciler.run_all_checks(
            snapshot_id="preview",
            files_dict=files_dict,
            comp_sheets=comp_sheets,
            summary_dfs=summary_dfs,
            today_mapped=today_mapped,
            yesterday_mapped=y_mapped,
        )
        checks_pass_count = sum(1 for c in preview_checks if c.status == "pass")
        checks_fail_count = sum(1 for c in preview_checks if c.status == "fail")
        checks_badge = "red" if checks_fail_count > 0 else "green"
        checks_preview_data = [
            {
                "workbook": c.workbook_name,
                "sheet": c.sheet_name,
                "cell_or_row": c.cell_or_row,
                "metric": c.metric_name,
                "excel_value": c.excel_value,
                "website_value": c.website_value,
                "diff": c.diff_value,
                "status": c.status,
            }
            for c in preview_checks
        ]

        # Cross-checks
        if scopes_summary["all"]["raw_count"] == 0:
            errors.append("Comparison Tool 'today' sheet has 0 data rows.")
        
        can_commit = len(errors) == 0
        session_id = str(uuid.uuid4())
        session_dict = {
            "data_as_of": data_as_of,
            "yesterday_date": resolved_yesterday_date,
            "files_dict": files_dict,
            "file_metadata": file_metadata,
            "today_mapped": today_mapped,
            "today_raw": today_raw,
            "yesterday_raw": yesterday_raw,
            "comp_sheets": comp_sheets,
            "summary_dfs": summary_dfs,
            "scopes_summary": scopes_summary,
            "snapshot_exists": snapshot_exists,
            "can_commit": can_commit,
        }
        _save_session_to_disk(session_id, session_dict)

        return {
            "session_id": session_id,
            "data_as_of_date": data_as_of.isoformat(),
            "suggested_date": suggested_date.isoformat() if suggested_date else None,
            "weekday": data_as_of.strftime("%A"),
            "quarter_label": ScopeService.quarter_label(cq),
            "yesterday_date": resolved_yesterday_date.isoformat(),
            "yesterday_source_desc": yesterday_source_desc,
            "last_week_date": last_week_target.isoformat(),
            "last_week_source_desc": last_week_source_desc,
            "last_week_is_partial": last_week_is_partial,
            "snapshot_exists": snapshot_exists,
            "existing_snapshot": existing_snap_info,
            "files": file_metadata,
            "scopes": scopes_summary,
            "current_quarter_renewals": scopes_summary["current_quarter"],
            "unmapped_regions": unmapped_regions_list,
            "missing_columns": missing_columns,
            "warnings": warnings,
            "errors": errors,
            "can_commit": can_commit,
            "fcr_changes_count": fcr_count,
            "schema_drift_warnings": schema_drift_warnings,
            "source_checks": {
                "badge": checks_badge,
                "total_checks": len(preview_checks),
                "passed_checks": checks_pass_count,
                "failed_checks": checks_fail_count,
                "items": checks_preview_data,
            },
        }

    # ------------------------------------------------------------------
    # Atomic Commit of Upload
    # ------------------------------------------------------------------

    def commit_upload(self, ctx: UserContext, session_id: str, replace: bool = False, make_active: bool | None = None) -> UploadSnapshot:
        session_data = _get_session_from_disk(session_id)
        if not session_data:
            raise ValueError("Upload session expired or invalid. Please re-upload and re-validate files.")
        if not session_data.get("can_commit", True):
            raise ValueError("Cannot commit: this upload session had validation errors. Please re-validate.")

        try:
            return self._commit_upload_impl(ctx, session_id, session_data, replace=replace, make_active=make_active)
        except Exception as exc:
            self.db.rollback()
            log.error("Commit failed for session %s: %s", session_id, exc)
            raise

    def _commit_upload_impl(self, ctx: UserContext, session_id: str, session_data: dict[str, Any], replace: bool = False, make_active: bool | None = None) -> UploadSnapshot:

        data_as_of: date = session_data["data_as_of"]
        yesterday_date: date = session_data["yesterday_date"]
        file_metadata: list[dict[str, Any]] = session_data["file_metadata"]
        today_mapped: pd.DataFrame = session_data["today_mapped"]
        today_raw: pd.DataFrame = session_data["today_raw"]
        yesterday_raw: pd.DataFrame | None = session_data.get("yesterday_raw")
        summary_dfs: dict[str, dict[str, pd.DataFrame]] = session_data["summary_dfs"]

        existing = (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.snapshot_date == data_as_of)
            .first()
        )
        if existing:
            if not replace:
                raise ValueError(
                    f"Snapshot already exists for {data_as_of.isoformat()}. Set replace=True to overwrite."
                )
            self.db.query(Opportunity).filter(Opportunity.snapshot_id == existing.id).delete()
            self.db.query(UploadedFile).filter(UploadedFile.snapshot_id == existing.id).delete()
            self.db.query(DailySummary).filter(DailySummary.snapshot_id == existing.id).delete()
            self.db.query(ChangeLog).filter(
                (ChangeLog.snapshot_from_id == existing.id) | (ChangeLog.snapshot_to_id == existing.id)
            ).delete()
            snap = existing
            snap.yesterday_date = yesterday_date
            if today_raw is not None and hasattr(today_raw, "columns"):
                snap.column_order = [str(c) for c in today_raw.columns]
        else:
            cols_order = [str(c) for c in today_raw.columns] if today_raw is not None and hasattr(today_raw, "columns") else None
            snap = UploadSnapshot(
                label="Today",
                snapshot_date=data_as_of,
                yesterday_date=yesterday_date,
                uploaded_by=getattr(ctx, "user_id", "system") or "system",
                column_order=cols_order,
            )
            self.db.add(snap)
            self.db.flush()

        # Out-of-order backfill: if uploading an older date, do NOT automatically make it today's active snapshot unless make_active is True.
        # Default: latest date in DB is active.
        max_date_in_db = (
            self.db.query(func.max(UploadSnapshot.snapshot_date))
            .filter(UploadSnapshot.id != snap.id)
            .scalar()
        )
        if make_active is True:
            should_be_active = True
        elif make_active is False:
            should_be_active = False
        else:
            should_be_active = (max_date_in_db is None or data_as_of >= max_date_in_db)

        if should_be_active:
            self.db.query(UploadSnapshot).filter(UploadSnapshot.id != snap.id).update(
                {"is_active_today": False}
            )
            snap.is_active_today = True
        else:
            snap.is_active_today = False

        last_week_target = data_as_of - timedelta(days=7)
        # A snapshot at date-7 is "real" only if it was uploaded as its own day. One that an earlier
        # upload derived from Lastweek_Data sheets is partial and gets rebuilt from this upload.
        existing_lw = (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.snapshot_date == last_week_target)
            .first()
        )
        real_lw_snap = existing_lw if existing_lw and existing_lw.uploaded_by not in AUTO_SNAPSHOT_SOURCES else None
        if real_lw_snap:
            snap.last_week_source = "real_snapshot"
            snap.last_week_is_partial = False
        else:
            snap.last_week_source = "embedded_summary_union"
            snap.last_week_is_partial = True

        for f_meta in file_metadata:
            uf = UploadedFile(
                snapshot_id=snap.id,
                file_slot=f_meta["slot"],
                filename=f_meta["filename"],
                file_size_bytes=f_meta["size_bytes"],
                sha256_hash=f_meta["sha256"],
                sheet_names=None,
                row_count=None,
            )
            self.db.add(uf)

        opp_objects: list[Opportunity] = []
        raw_rows_dict = [clean_record(r) for r in today_raw.to_dict(orient="records")] if today_raw is not None else []

        active_count = 0
        for i, (_, row) in enumerate(today_mapped.iterrows()):
            opp_id = _safe_str(row.get("opportunity_id_18"))
            flags = {}
            raw_dict = raw_rows_dict[i] if i < len(raw_rows_dict) else None
            opp = self._row_to_opportunity(snap.id, row, scope_flags=flags, raw_row_dict=raw_dict)
            if not opp.is_deleted_or_lost:
                active_count += 1
            opp_objects.append(opp)

        self.db.bulk_save_objects(opp_objects)
        snap.row_count = len(opp_objects)
        snap.active_row_count = active_count

        if yesterday_raw is not None and not yesterday_raw.empty:
            existing_yest = (
                self.db.query(UploadSnapshot)
                .filter(UploadSnapshot.snapshot_date == yesterday_date)
                .first()
            )
            if existing_yest is None or existing_yest.uploaded_by in AUTO_SNAPSHOT_SOURCES:
                if existing_yest is None:
                    yest_snap = UploadSnapshot(
                        label="Yesterday",
                        snapshot_date=yesterday_date,
                        uploaded_by="comparison_tool_yesterday",
                        is_active_today=False,
                    )
                    self.db.add(yest_snap)
                    self.db.flush()
                else:
                    yest_snap = existing_yest
                    self._clear_snapshot_rows(yest_snap.id)
                y_mapped = _map_columns(yesterday_raw)
                
                # Ensure sales_type and fiscal_period exist
                if "sales_type" not in y_mapped.columns:
                    y_mapped["sales_type"] = "Renewals"
                if "fiscal_period" not in y_mapped.columns:
                    from backend.services.scopes import ScopeService
                    y_mapped["fiscal_period"] = y_mapped["close_date"].apply(
                        lambda d: ScopeService.quarter_of(parse_excel_date(d)) if pd.notnull(d) else None
                    )
                
                def _y_flags(r):
                    # We store sales_type and fiscal_period in extra_attributes if they are missing?
                    # No, _row_to_opportunity uses row.get("sales_type") and row.get("fiscal_period") directly from mapped row.
                    # We just ensure the row has them. But we can inject them via _row_to_opportunity raw dict or just mapped row.
                    # _fill_snapshot passes mapped row. We can mutate mapped row or wait, we just return a dict of flags, but we need sales_type and fiscal_period populated.
                    # Wait, _row_to_opportunity expects them in `row` (pd.Series).
                    return {}

                self._fill_snapshot(yest_snap, y_mapped, yesterday_raw, _y_flags)
                self._build_daily_summaries_multi_scope(yest_snap)
            elif existing_yest.row_count and abs(existing_yest.row_count - len(yesterday_raw)) > 0:
                warnings_note = (
                    f"Kept the stored snapshot for {yesterday_date} ({existing_yest.row_count} rows); "
                    f"the uploaded 'yesterday' sheet has {len(yesterday_raw)} rows."
                )
                log.warning(warnings_note)

        if not real_lw_snap:
            lw_rows = []
            seen_ids = set()
            for slot_name, s_sheets in summary_dfs.items():
                lw_df = s_sheets.get("lastweek_data")
                if lw_df is not None and not lw_df.empty:
                    lw_m = _map_columns(lw_df)
                    for _, r in lw_m.iterrows():
                        opp_id = _safe_str(r.get("opportunity_id_18"))
                        if opp_id and opp_id not in seen_ids:
                            seen_ids.add(opp_id)
                            lw_rows.append(r)
            if lw_rows:
                if existing_lw is None:
                    lw_snap = UploadSnapshot(
                        label="Last Week (Partial)",
                        snapshot_date=last_week_target,
                        uploaded_by="summary_lastweek_union",
                        is_active_today=False,
                        last_week_source="embedded_summary_union",
                        last_week_is_partial=True,
                    )
                    self.db.add(lw_snap)
                    self.db.flush()
                else:
                    lw_snap = existing_lw
                    self._clear_snapshot_rows(lw_snap.id)
                lw_df_all = pd.DataFrame(lw_rows).reset_index(drop=True)

                if "sales_type" not in lw_df_all.columns:
                    lw_df_all["sales_type"] = "Renewals"
                else:
                    lw_df_all["sales_type"] = lw_df_all["sales_type"].fillna("Renewals")
                
                if "fiscal_period" not in lw_df_all.columns:
                    from backend.services.scopes import ScopeService
                    lw_df_all["fiscal_period"] = lw_df_all.get("close_date", pd.Series(dtype=object)).apply(
                        lambda d: ScopeService.quarter_of(parse_excel_date(d)) if pd.notnull(d) else None
                    )
                else:
                    from backend.services.scopes import ScopeService
                    def fill_fp(row):
                        if pd.isna(row.get("fiscal_period")):
                            d = row.get("close_date")
                            return ScopeService.quarter_of(parse_excel_date(d)) if pd.notnull(d) else None
                        return row["fiscal_period"]
                    lw_df_all["fiscal_period"] = lw_df_all.apply(fill_fp, axis=1)

                def _lw_flags(r):
                    return {}

                self._fill_snapshot(lw_snap, lw_df_all, None, _lw_flags)
                self._build_daily_summaries_multi_scope(lw_snap)

        self._build_daily_summaries_multi_scope(snap)

        if yesterday_raw is not None and not yesterday_raw.empty:
            self._compute_yesterday_changelog(snap, yesterday_raw)

        # Persist Source Reconciliation Checks (Addendum B)
        try:
            self.db.query(SnapshotCheck).filter(SnapshotCheck.snapshot_id == snap.id).delete()
            reconciler = ReconciliationEngine()
            y_mapped = _map_columns(yesterday_raw) if yesterday_raw is not None and not yesterday_raw.empty else None
            checks = reconciler.run_all_checks(
                snapshot_id=snap.id,
                files_dict=session_data.get("files_dict", {}),
                comp_sheets=session_data.get("comp_sheets", {}),
                summary_dfs=summary_dfs,
                today_mapped=today_mapped,
                yesterday_mapped=y_mapped,
            )
            for c in checks:
                self.db.add(c)
        except Exception as exc:
            log.warning("Could not persist source reconciliation checks for snapshot %s: %s", snap.id, exc)

        try:
            self.db.commit()
            _delete_session(session_id)
            log.info("Committed snapshot %s (%s) with %d rows (%d active)", snap.id, snap.snapshot_date, snap.row_count, snap.active_row_count)
            return snap
        except Exception as exc:
            self.db.rollback()
            log.error("Commit failed for snapshot %s: %s", getattr(snap, 'id', 'unknown'), exc)
            raise

    
    def _clear_snapshot_rows(self, snapshot_id: str) -> None:
        self.db.query(Opportunity).filter(Opportunity.snapshot_id == snapshot_id).delete()
        self.db.query(DailySummary).filter(DailySummary.snapshot_id == snapshot_id).delete()

    def _fill_snapshot(self, snap: UploadSnapshot, mapped: pd.DataFrame, raw: pd.DataFrame | None, flag_fn) -> None:
        raw_dicts = [clean_record(r) for r in raw.to_dict(orient="records")] if raw is not None else []
        objs, active = [], 0
        for i, (_, row) in enumerate(mapped.iterrows()):
            raw_d = raw_dicts[i] if i < len(raw_dicts) else None
            o = self._row_to_opportunity(snap.id, row, scope_flags=flag_fn(row), raw_row_dict=raw_d)
            if not o.is_deleted_or_lost:
                active += 1
            objs.append(o)
        self.db.bulk_save_objects(objs)
        snap.row_count = len(objs)
        snap.active_row_count = active

    def _row_to_opportunity(
        self,
        snapshot_id: str,
        row: pd.Series,
        scope_flags: dict[str, bool | None] | None = None,
        raw_row_dict: dict | None = None,
    ) -> Opportunity:
        bu_raw = _safe_str(row.get("business_unit_raw"))
        raw_approval = _safe_str(row.get("approval_status"))
        raw_forecast = _safe_str(row.get("forecast_category"))
        raw_stage = _safe_str(row.get("stage_number")) or _safe_str(row.get("stage"))
        flags = scope_flags or {}
        is_del_lost = (raw_stage or "").lower() in ("deleted", "lost")
        return Opportunity(
            snapshot_id=snapshot_id,
            opportunity_id_18=_safe_str(row.get("opportunity_id_18")),
            opportunity_name=_safe_str(row.get("opportunity_name")),
            account_name=_safe_str(row.get("account_name")),
            sub_region=_safe_str(row.get("sub_region")),
            revised_sub_region=_safe_str(row.get("revised_sub_region")),
            country_territory=_safe_str(row.get("country_territory")),
            business_unit_raw=bu_raw,
            business_unit_primary=primary_business_unit(bu_raw),
            forecast_category=normalise_forecast_category(raw_forecast),
            forecast_acv_amount=to_decimal(row.get("forecast_acv_amount")),
            close_date=_coerce_date(row.get("close_date")),
            last_modified_date=_coerce_datetime(row.get("last_modified_date")),
            probability_pct=_coerce_float(row.get("probability_pct")),
            approval_status=normalise_approval_status(raw_approval),
            service_expiry_period=_safe_str(row.get("service_expiry_period")),
            closing_year=_coerce_int(row.get("closing_year")),
            renewal_category=_safe_str(row.get("renewal_category")),
            months_delayed=_coerce_float(row.get("months_delayed")),
            opportunity_owner=_safe_str(row.get("opportunity_owner")),
            stage_number=raw_stage,
            is_deleted_or_lost=is_del_lost,
            sales_type=_safe_str(row.get("sales_type")),
            fiscal_period=_safe_str(row.get("fiscal_period")),
            in_renewals=flags.get("in_renewals"),
            in_fy2026=flags.get("in_fy2026"),
            in_fy2027=flags.get("in_fy2027"),
            in_q4_2026=flags.get("in_q4_2026"),
            extra_attributes=raw_row_dict,
        )

    def _build_daily_summaries_multi_scope(self, snapshot: UploadSnapshot) -> None:
        self.db.query(DailySummary).filter(DailySummary.snapshot_id == snapshot.id).delete()
        opps = self.db.query(Opportunity).filter(Opportunity.snapshot_id == snapshot.id).all()
        if not opps:
            return
        snap_date = snapshot.snapshot_date
        rows: list[DailySummary] = []

        def _make(metric, dimension, dim_val, value, count):
            return DailySummary(
                snapshot_id=snapshot.id,
                snapshot_date=snap_date,
                metric=metric,
                dimension=dimension,
                dimension_value=str(dim_val),
                value=Decimal(str(round(value, 2))),
                count=int(count),
            )

        total_acv = sum(float(o.forecast_acv_amount or 0) for o in opps)
        rows.append(_make("total_acv", "overall", "overall", total_acv, len(opps)))

        from collections import defaultdict
        cat_acv: dict[str, float] = defaultdict(float)
        cat_cnt: dict[str, int] = defaultdict(int)
        for o in opps:
            fc = o.forecast_category or "Blank"
            cat_acv[fc] += float(o.forecast_acv_amount or 0)
            cat_cnt[fc] += 1
        for fc, acv in cat_acv.items():
            rows.append(_make("forecast_acv", "forecast_category", fc, acv, cat_cnt[fc]))

        appr_acv: dict[str, float] = defaultdict(float)
        appr_cnt: dict[str, int] = defaultdict(int)
        for o in opps:
            st = o.approval_status or "Blank"
            appr_acv[st] += float(o.forecast_acv_amount or 0)
            appr_cnt[st] += 1
        for st, acv in appr_acv.items():
            rows.append(_make("approval_acv", "approval_status", st, acv, appr_cnt[st]))

        self.db.bulk_save_objects(rows)

    def _compute_yesterday_changelog(self, snapshot: UploadSnapshot, yesterday_df: pd.DataFrame) -> None:
        yesterday_mapped = _map_columns(yesterday_df)
        id_col = "opportunity_id_18"
        if id_col not in yesterday_mapped.columns:
            return

        y_dict: dict[str, dict] = {}
        for _, r in yesterday_mapped.iterrows():
            opp_id = _safe_str(r.get(id_col))
            if opp_id:
                stage = _safe_str(r.get("stage_number")) or _safe_str(r.get("stage"))
                y_dict[opp_id] = {
                    "name": _safe_str(r.get("opportunity_name")),
                    "stage": stage,
                    "is_deleted_or_lost": (stage or "").lower() in ("deleted", "lost"),
                    "acv": to_decimal(r.get("forecast_acv_amount")),
                    "forecast_category": normalise_forecast_category(_safe_str(r.get("forecast_category"))),
                    "approval_status": normalise_approval_status(_safe_str(r.get("approval_status"))),
                }

        today_opps = self.db.query(Opportunity).filter(Opportunity.snapshot_id == snapshot.id).all()
        t_dict = {o.opportunity_id_18: o for o in today_opps if o.opportunity_id_18}

        yesterday_snap = (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.snapshot_date == snapshot.yesterday_date)
            .first()
            if snapshot.yesterday_date
            else None
        )
        from_snap_id: str | None = yesterday_snap.id if yesterday_snap else None

        logs: list[ChangeLog] = []

        for opp_id, t_opp in t_dict.items():
            y_opp = y_dict.get(opp_id)
            if y_opp is None:
                if not t_opp.is_deleted_or_lost:
                    logs.append(ChangeLog(
                        snapshot_from_id=from_snap_id, snapshot_to_id=snapshot.id,
                        opportunity_id_18=opp_id, opportunity_name=t_opp.opportunity_name,
                        changed_column="opportunity_id_18", old_value=None, new_value=opp_id,
                        opportunity_status="New", change_type="New Opportunity",
                    ))
                continue

            if not y_opp["is_deleted_or_lost"] and t_opp.is_deleted_or_lost:
                logs.append(ChangeLog(
                    snapshot_from_id=from_snap_id, snapshot_to_id=snapshot.id,
                    opportunity_id_18=opp_id, opportunity_name=t_opp.opportunity_name,
                    changed_column="stage_number",
                    old_value=y_opp["stage"] or "Active", new_value=t_opp.stage_number or "Deleted/Lost",
                    opportunity_status="Existing", change_type="Moved to Deleted/Lost",
                ))

            if y_opp["forecast_category"] != t_opp.forecast_category:
                logs.append(ChangeLog(
                    snapshot_from_id=from_snap_id, snapshot_to_id=snapshot.id,
                    opportunity_id_18=opp_id, opportunity_name=t_opp.opportunity_name,
                    changed_column="forecast_category",
                    old_value=y_opp["forecast_category"], new_value=t_opp.forecast_category,
                    opportunity_status="Existing", change_type="Category Change",
                ))

            if y_opp["acv"] is not None and t_opp.forecast_acv_amount is not None:
                if abs(y_opp["acv"] - t_opp.forecast_acv_amount) >= Decimal("0.01"):
                    logs.append(ChangeLog(
                        snapshot_from_id=from_snap_id, snapshot_to_id=snapshot.id,
                        opportunity_id_18=opp_id, opportunity_name=t_opp.opportunity_name,
                        changed_column="forecast_acv_amount",
                        old_value=str(y_opp["acv"]), new_value=str(t_opp.forecast_acv_amount),
                        opportunity_status="Existing", change_type="ACV Change",
                    ))

        for opp_id, y_opp in y_dict.items():
            if opp_id not in t_dict and not y_opp["is_deleted_or_lost"]:
                logs.append(ChangeLog(
                    snapshot_from_id=from_snap_id, snapshot_to_id=snapshot.id,
                    opportunity_id_18=opp_id, opportunity_name=y_opp["name"],
                    changed_column="opportunity_id_18", old_value=opp_id, new_value=None,
                    opportunity_status="Existing", change_type="Opportunity Removed",
                ))

        if logs:
            self.db.bulk_save_objects(logs)

    # ------------------------------------------------------------------
    # Legacy compatibility methods
    # ------------------------------------------------------------------

    def ingest_renewals_summary(self, ctx: UserContext, path: Path, snapshot_date: date, label: str = "Today") -> UploadSnapshot:
        sheets = parse_renewals_summary(path)
        today_df = sheets.get("today", sheets.get("today_data", sheets.get("Today_Data", pd.DataFrame())))
        if today_df.empty:
            for k, df_k in sheets.items():
                if "today" in k.lower():
                    today_df = df_k
                    break

        if label == "Today":
            self.db.query(UploadSnapshot).update({"is_active_today": False})

        snap = self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == snapshot_date).first()
        if not snap:
            snap = UploadSnapshot(
                label=label, snapshot_date=snapshot_date,
                yesterday_date=compute_previous_working_day(snapshot_date),
                is_active_today=(label == "Today"), source_file_summary=path.name, uploaded_by="system",
            )
            self.db.add(snap)
            self.db.flush()
        else:
            if label == "Today":
                snap.is_active_today = True

        if not today_df.empty:
            if hasattr(today_df, "columns"):
                snap.column_order = [str(c) for c in today_df.columns]
            mapped_df = _map_columns(today_df)
            raw_rows_dict = today_df.to_dict(orient="records")
            self.db.query(Opportunity).filter(Opportunity.snapshot_id == snap.id).delete()
            rows: list[Opportunity] = []
            for idx_r, (_, r) in enumerate(mapped_df.iterrows()):
                st = _safe_str(r.get("sales_type"))
                flags = {"in_renewals": (st == "Renewals") if st else True, "in_fy2026": None, "in_fy2027": None, "in_q4_2026": None}
                raw_d = raw_rows_dict[idx_r] if idx_r < len(raw_rows_dict) else None
                rows.append(self._row_to_opportunity(snap.id, r, scope_flags=flags, raw_row_dict=raw_d))
            self.db.bulk_save_objects(rows)
            snap.row_count = len(rows)
            snap.active_row_count = sum(1 for r in rows if not r.is_deleted_or_lost)
            self._build_daily_summaries_multi_scope(snap)

        yest_df = sheets.get("yesterday", sheets.get("yesterday_data", sheets.get("Yesterday_Data", pd.DataFrame())))
        if not yest_df.empty:
            yest_date = compute_previous_working_day(snapshot_date)
            yest_snap = self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == yest_date).first()
            if not yest_snap:
                yest_snap = UploadSnapshot(label="Yesterday", snapshot_date=yest_date, is_active_today=False, source_file_summary=path.name, uploaded_by="system")
                self.db.add(yest_snap)
                self.db.flush()
            y_mapped = _map_columns(yest_df)
            y_raw_dict = yest_df.to_dict(orient="records")
            self.db.query(Opportunity).filter(Opportunity.snapshot_id == yest_snap.id).delete()
            y_rows = []
            for idx_y, (_, r) in enumerate(y_mapped.iterrows()):
                st = _safe_str(r.get("sales_type"))
                flags = {"in_renewals": (st == "Renewals") if st else True, "in_fy2026": None, "in_fy2027": None, "in_q4_2026": None}
                raw_d = y_raw_dict[idx_y] if idx_y < len(y_raw_dict) else None
                y_rows.append(self._row_to_opportunity(yest_snap.id, r, scope_flags=flags, raw_row_dict=raw_d))
            self.db.bulk_save_objects(y_rows)
            yest_snap.row_count = len(y_rows)
            yest_snap.active_row_count = sum(1 for r in y_rows if not r.is_deleted_or_lost)
            self._build_daily_summaries_multi_scope(yest_snap)

        lw_df = sheets.get("lastweek", sheets.get("lastweek_data", sheets.get("Lastweek_Data", pd.DataFrame())))
        if not lw_df.empty:
            lw_date = snapshot_date - timedelta(days=7)
            lw_snap = self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == lw_date).first()
            if not lw_snap:
                lw_snap = UploadSnapshot(label="Last Week", snapshot_date=lw_date, is_active_today=False, source_file_summary=path.name, uploaded_by="system")
                self.db.add(lw_snap)
                self.db.flush()
            lw_mapped = _map_columns(lw_df)
            lw_raw_dict = lw_df.to_dict(orient="records")
            self.db.query(Opportunity).filter(Opportunity.snapshot_id == lw_snap.id).delete()
            lw_rows = []
            for idx_lw, (_, r) in enumerate(lw_mapped.iterrows()):
                st = _safe_str(r.get("sales_type"))
                flags = {"in_renewals": (st == "Renewals") if st else True, "in_fy2026": None, "in_fy2027": None, "in_q4_2026": None}
                raw_d = lw_raw_dict[idx_lw] if idx_lw < len(lw_raw_dict) else None
                lw_rows.append(self._row_to_opportunity(lw_snap.id, r, scope_flags=flags, raw_row_dict=raw_d))
            self.db.bulk_save_objects(lw_rows)
            lw_snap.row_count = len(lw_rows)
            lw_snap.active_row_count = sum(1 for r in lw_rows if not r.is_deleted_or_lost)
            self._build_daily_summaries_multi_scope(lw_snap)

        self.db.commit()
        return snap

    def ingest_comparison_tool(self, ctx: UserContext, path: Path, snapshot: UploadSnapshot) -> None:
        from backend.services.diff_service import DiffService
        sheets = parse_comparison_tool(path)
        diff_svc = DiffService(self.db)
        diff_svc.ingest_from_comparison_tool(ctx, snapshot, sheets)
        self.db.commit()
