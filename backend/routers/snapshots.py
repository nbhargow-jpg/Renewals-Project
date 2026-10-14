from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Body, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional, List
import shutil, tempfile
from pathlib import Path

from backend.database import get_db
from backend.services.context import UserContext, get_user_context, require_admin_context
from backend.services.ingest_service import IngestService, compute_previous_working_day
from backend.services.analytics_service import AnalyticsService
from backend.models.snapshot import UploadSnapshot, UploadedFile, SnapshotCheck

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("")
def list_snapshots(db: Session = Depends(get_db), ctx: UserContext = Depends(get_user_context)):
    snaps = db.query(UploadSnapshot).order_by(UploadSnapshot.snapshot_date.desc()).all()
    results = []
    for s in snaps:
        # Compute Q-slice deals and ACV (Renewals in fiscal period matching snapshot's quarter)
        from backend.services.scopes import ScopeService
        from backend.models.opportunity import Opportunity
        from sqlalchemy import func
        quarter_str = ScopeService.quarter_of(s.snapshot_date)
        q_label = ScopeService.quarter_label(quarter_str)

        q_agg = (
            db.query(
                func.count(Opportunity.id),
                func.sum(Opportunity.forecast_acv_amount),
            )
            .filter(
                Opportunity.snapshot_id == s.id,
                Opportunity.fiscal_period == quarter_str,
                Opportunity.sales_type == "Renewals",
            )
            .first()
        )
        q_deals = int(q_agg[0] or 0)
        q_acv = float(q_agg[1] or 0.0)

        results.append({
            "id": s.id,
            "label": s.label,
            "snapshot_date": s.snapshot_date.isoformat(),
            "yesterday_date": s.yesterday_date.isoformat() if s.yesterday_date else None,
            "row_count": s.row_count,
            "active_row_count": s.active_row_count,
            "is_active_today": s.is_active_today,
            "uploaded_at": s.uploaded_at.isoformat(),
            "source_file_summary": s.source_file_summary,
            "source_file_comparison": s.source_file_comparison,
            "last_week_source": s.last_week_source,
            "last_week_is_partial": s.last_week_is_partial,
            "q_slice_label": q_label,
            "q_slice_deals": q_deals,
            "q_slice_acv": q_acv,
            "source_checks": {
                "total": len(s.checks),
                "passed": sum(1 for c in s.checks if c.status == "pass"),
                "failed": sum(1 for c in s.checks if c.status == "fail"),
                "badge": "red" if any(c.status == "fail" for c in s.checks) else ("green" if len(s.checks) > 0 else "none"),
            },
            "files": [
                {
                    "slot": f.file_slot,
                    "filename": f.filename,
                    "size_bytes": f.file_size_bytes,
                    "sha256": f.sha256_hash,
                }
                for f in s.uploaded_files
            ],
        })
    return results


@router.get("/history")
def upload_history(db: Session = Depends(get_db), ctx: UserContext = Depends(get_user_context)):
    """Return all uploads formatted for history displays."""
    snaps = (
        db.query(UploadSnapshot)
        .order_by(UploadSnapshot.snapshot_date.desc())
        .all()
    )
    from backend.services.scopes import ScopeService
    from backend.models.opportunity import Opportunity
    from sqlalchemy import func

    results = []
    for s in snaps:
        quarter_str = ScopeService.quarter_of(s.snapshot_date)
        q_label = ScopeService.quarter_label(quarter_str)
        q_agg = (
            db.query(
                func.count(Opportunity.id),
                func.sum(Opportunity.forecast_acv_amount),
            )
            .filter(
                Opportunity.snapshot_id == s.id,
                Opportunity.fiscal_period == quarter_str,
                Opportunity.sales_type == "Renewals",
            )
            .first()
        )
        q_deals = int(q_agg[0] or 0)
        q_acv = float(q_agg[1] or 0.0)

        results.append({
            "id": s.id,
            "label": s.label,
            "snapshot_date": s.snapshot_date.isoformat(),
            "yesterday_date": s.yesterday_date.isoformat() if s.yesterday_date else None,
            "uploaded_at": s.uploaded_at.isoformat(),
            "row_count": s.row_count,
            "active_row_count": s.active_row_count,
            "is_active_today": s.is_active_today,
            "last_week_source": s.last_week_source or "real_snapshot",
            "last_week_is_partial": s.last_week_is_partial,
            "q_slice_label": q_label,
            "q_slice_deals": q_deals,
            "q_slice_acv": q_acv,
            "status": "success",
            "source_checks": {
                "total": len(s.checks),
                "passed": sum(1 for c in s.checks if c.status == "pass"),
                "failed": sum(1 for c in s.checks if c.status == "fail"),
                "badge": "red" if any(c.status == "fail" for c in s.checks) else ("green" if len(s.checks) > 0 else "none"),
            },
            "files": [
                {
                    "slot": f.file_slot,
                    "filename": f.filename,
                    "size_bytes": f.file_size_bytes,
                    "sha256": f.sha256_hash,
                }
                for f in s.uploaded_files
            ],
        })
    return results


@router.get("/active")
def get_active_snapshot(db: Session = Depends(get_db), ctx: UserContext = Depends(get_user_context)):
    svc = AnalyticsService(db)
    snap = svc.get_active_snapshot(ctx)
    if snap is None:
        raise HTTPException(status_code=404, detail="No active snapshot. Run the seed script first.")
    return {
        "id": snap.id,
        "label": snap.label,
        "snapshot_date": snap.snapshot_date.isoformat(),
        "yesterday_date": snap.yesterday_date.isoformat() if snap.yesterday_date else None,
        "row_count": snap.row_count,
        "active_row_count": snap.active_row_count,
    }


@router.get("/{snapshot_id}")
def get_snapshot(snapshot_id: str, db: Session = Depends(get_db), ctx: UserContext = Depends(get_user_context)):
    snap = db.query(UploadSnapshot).filter(UploadSnapshot.id == snapshot_id).first()
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {
        "id": snap.id,
        "label": snap.label,
        "snapshot_date": snap.snapshot_date.isoformat(),
        "yesterday_date": snap.yesterday_date.isoformat() if snap.yesterday_date else None,
        "row_count": snap.row_count,
        "active_row_count": snap.active_row_count,
        "is_active_today": snap.is_active_today,
        "uploaded_at": snap.uploaded_at.isoformat(),
    }


@router.get("/{snapshot_id}/checks")
def get_snapshot_checks(
    snapshot_id: str,
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(get_user_context),
):
    """Return all source reconciliation checks for this snapshot."""
    checks = db.query(SnapshotCheck).filter(SnapshotCheck.snapshot_id == snapshot_id).all()
    passed = sum(1 for c in checks if c.status == "pass")
    failed = sum(1 for c in checks if c.status == "fail")
    badge = "red" if failed > 0 else ("green" if len(checks) > 0 else "none")
    return {
        "snapshot_id": snapshot_id,
        "badge": badge,
        "total_checks": len(checks),
        "passed_checks": passed,
        "failed_checks": failed,
        "items": [
            {
                "id": c.id,
                "workbook": c.workbook_name,
                "sheet": c.sheet_name,
                "cell_or_row": c.cell_or_row,
                "metric": c.metric_name,
                "excel_value": c.excel_value,
                "website_value": c.website_value,
                "diff": c.diff_value,
                "status": c.status,
            }
            for c in checks
        ],
    }


@router.delete("/{snapshot_id}", dependencies=[Depends(require_admin_context)])
def delete_snapshot(
    snapshot_id: str,
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(require_admin_context),
):
    """Admin-only deletion of a snapshot."""
    snap = db.query(UploadSnapshot).filter(UploadSnapshot.id == snapshot_id).first()
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    snap_date = snap.snapshot_date.isoformat()
    db.delete(snap)
    db.commit()
    return {"status": "ok", "deleted_snapshot_id": snapshot_id, "snapshot_date": snap_date}


@router.post("/{snapshot_id}/set-active", dependencies=[Depends(require_admin_context)])
def set_active_snapshot_endpoint(
    snapshot_id: str,
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(require_admin_context),
):
    """Admin-only action to mark a specific snapshot as active."""
    target_snap = db.query(UploadSnapshot).filter(UploadSnapshot.id == snapshot_id).first()
    if not target_snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    # Mark all others as inactive
    db.query(UploadSnapshot).filter(UploadSnapshot.id != snapshot_id).update({"is_active_today": False})
    target_snap.is_active_today = True
    db.commit()
    return {
        "status": "ok",
        "active_snapshot_id": target_snap.id,
        "snapshot_date": target_snap.snapshot_date.isoformat(),
        "is_active_today": True,
    }


@router.post("/validate")
async def validate_upload(
    request: Request,
    data_as_of_date: Optional[str] = Form(None),
    yesterday_date: Optional[str] = Form(None),
    comparison_tool: Optional[UploadFile] = File(None),
    fiscal_2026: Optional[UploadFile] = File(None),
    fiscal_2027: Optional[UploadFile] = File(None),
    fiscal_q4: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(require_admin_context),
):
    """
    Validate uploaded files, compute preview metrics and reconciliation warnings.
    Supports fixed slots as well as arbitrary dynamic files (Addendum C).
    Admin-only (Addendum D).
    """
    if not data_as_of_date:
        raise HTTPException(status_code=422, detail="data_as_of_date is required")
    try:
        as_of = date.fromisoformat(data_as_of_date)
    except ValueError:
        raise HTTPException(status_code=422, detail="data_as_of_date must be YYYY-MM-DD")

    if yesterday_date:
        try:
            yest = date.fromisoformat(yesterday_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="yesterday_date must be YYYY-MM-DD")
    else:
        yest = compute_previous_working_day(as_of)

    tmpdir = tempfile.mkdtemp()
    tmp = Path(tmpdir)
    files_dict: dict[str, Path] = {}

    try:
        # Collect all form files (both standard slot names and any dynamic uploads)
        uploaded_files_list: list[tuple[str, UploadFile]] = []
        for name, u_file in [
            ("comparison_tool", comparison_tool),
            ("fiscal_2026", fiscal_2026),
            ("fiscal_2027", fiscal_2027),
            ("fiscal_q4", fiscal_q4),
        ]:
            if u_file is not None and getattr(u_file, "filename", None):
                uploaded_files_list.append((name, u_file))

        try:
            form = await request.form()
            items_to_check = form.multi_items() if hasattr(form, "multi_items") else form.items()
            for field_name, value in items_to_check:
                if hasattr(value, "filename") and getattr(value, "filename", None):
                    if not any(getattr(f[1], "filename", None) == value.filename for f in uploaded_files_list):
                        uploaded_files_list.append((field_name, value))
        except Exception as exc:
            log.warning("Form parsing exception: %s", exc)

        if not uploaded_files_list:
            raise HTTPException(status_code=422, detail="No files were uploaded.")

        # Save files to disk and detect their content-based slot
        for field_name, u_file in uploaded_files_list:
            f_path = tmp / u_file.filename
            with f_path.open("wb") as f:
                shutil.copyfileobj(u_file.file, f)

            from backend.utils.excel_parser import detect_file_slot
            detected_slot, _ = detect_file_slot(f_path)
            # Use detected content slot or fallback to field_name
            slot_key = detected_slot if detected_slot != "unknown" else field_name
            files_dict[slot_key] = f_path

        svc = IngestService(db)
        result = svc.validate_upload(ctx, files_dict, as_of, yest)
        return result
    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


@router.post("/commit", dependencies=[Depends(require_admin_context)])
def commit_upload(
    session_id: str = Body(..., embed=True),
    replace: bool = Body(False, embed=True),
    make_active: Optional[bool] = Body(None, embed=True),
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(require_admin_context),
):
    """Atomic commit of previously validated upload session. Admin-only (Addendum D)."""
    svc = IngestService(db)
    try:
        snap = svc.commit_upload(ctx, session_id, replace=replace, make_active=make_active)
        return {
            "status": "ok",
            "snapshot_id": snap.id,
            "snapshot_date": snap.snapshot_date.isoformat(),
            "row_count": snap.row_count,
            "active_row_count": snap.active_row_count,
            "is_active_today": snap.is_active_today,
        }
    except ValueError as exc:
        msg = str(exc)
        if "replace=True" in msg:
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=400, detail=msg)


@router.post("/upload", dependencies=[Depends(require_admin_context)])
async def upload_files_legacy(
    snapshot_date: str = Form(...),
    label: str = Form("Today"),
    renewals_summary: UploadFile | None = File(None),
    comparison_tool: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(require_admin_context),
):
    """Legacy upload endpoint preserved for backward compatibility. Admin-only (Addendum D)."""
    if renewals_summary is None and comparison_tool is None:
        raise HTTPException(status_code=422, detail="At least one file is required.")

    try:
        snap_date = date.fromisoformat(snapshot_date)
    except ValueError:
        raise HTTPException(status_code=422, detail="snapshot_date must be YYYY-MM-DD")

    svc = IngestService(db)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        snap = None
        if renewals_summary:
            rs_path = tmp / renewals_summary.filename
            with rs_path.open("wb") as f:
                shutil.copyfileobj(renewals_summary.file, f)
            snap = svc.ingest_renewals_summary(ctx, rs_path, snap_date, label)

        if comparison_tool:
            ct_path = tmp / comparison_tool.filename
            with ct_path.open("wb") as f:
                shutil.copyfileobj(comparison_tool.file, f)
            if snap is None:
                analytics = AnalyticsService(db)
                snap = analytics.get_snapshot_by_date(ctx, snap_date)
                if snap is None:
                    raise HTTPException(status_code=422, detail="Upload Renewals Summary first for this date.")
            svc.ingest_comparison_tool(ctx, ct_path, snap)

        db.commit()

    return {"status": "ok", "snapshot_id": snap.id if snap else None, "snapshot_date": snap_date.isoformat()}
