"""
Filters Router — /api/v2/filters/...
Provides dynamic options generated directly from the active snapshot:
available quarters, fiscal years, sales types, mapped regions (+ Other),
business units, forecast categories, approval statuses, with deal counts,
and available snapshot dates.
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.models.snapshot import UploadSnapshot
from backend.models.opportunity import Opportunity
from backend.services.scopes import (
    ScopeService,
    REGION_MAP,
    CANONICAL_FORECAST_CATEGORIES,
    CANONICAL_APPROVAL_STATUSES,
)

router = APIRouter(prefix="/api/v2/filters", tags=["v2-filters"])


@router.get("/options")
def get_filter_options(
    as_of: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    # 1. Resolve snapshot
    snap_q = db.query(UploadSnapshot)
    if as_of:
        try:
            from datetime import date
            d = date.fromisoformat(as_of)
            snap = snap_q.filter(UploadSnapshot.snapshot_date <= d).order_by(UploadSnapshot.snapshot_date.desc()).first()
        except ValueError:
            snap = snap_q.order_by(UploadSnapshot.snapshot_date.desc()).first()
    else:
        snap = (
            snap_q.filter(UploadSnapshot.is_active_today == True)
            .order_by(UploadSnapshot.snapshot_date.desc())
            .first()
        )
        if not snap:
            snap = snap_q.order_by(UploadSnapshot.snapshot_date.desc()).first()

    if not snap:
        return {
            "snapshot_dates": [],
            "current_quarter": "",
            "quarters": [],
            "fiscal_years": [],
            "sales_types": [],
            "regions": [],
            "business_units": [],
            "forecast_categories": [],
            "approval_statuses": [],
            "total_deals": 0,
        }

    # Available snapshots
    all_snaps = (
        db.query(UploadSnapshot)
        .order_by(UploadSnapshot.snapshot_date.desc())
        .all()
    )
    snapshot_dates = [
        {
            "id": s.id,
            "date": s.snapshot_date.isoformat(),
            "label": s.label or s.snapshot_date.isoformat(),
            "is_active_today": bool(s.is_active_today),
        }
        for s in all_snaps
    ]

    cq = ScopeService.quarter_of(snap.snapshot_date)

    # Query all opportunities in active snapshot
    opps = (
        db.query(Opportunity)
        .filter(Opportunity.snapshot_id == snap.id)
        .all()
    )

    total_deals = len(opps)

    # 1. Quarters & Fiscal Years
    q_counts: Dict[str, int] = {}
    fy_counts: Dict[str, int] = {}
    for o in opps:
        fp = (o.fiscal_period or "").strip()
        if fp and "-" in fp:
            q_counts[fp] = q_counts.get(fp, 0) + 1
            parts = fp.split("-")
            fy_label = f"FY{parts[1]}"
            fy_counts[fy_label] = fy_counts.get(fy_label, 0) + 1

    quarters = [
        {"key": q, "value": q, "label": ScopeService.quarter_label(q), "count": count}
        for q, count in sorted(q_counts.items())
    ]
    fiscal_years = [
        {"key": fy, "value": fy, "label": fy, "count": count}
        for fy, count in sorted(fy_counts.items())
    ]

    # 2. Sales Types
    st_counts: Dict[str, int] = {}
    for o in opps:
        st = (o.sales_type or "").strip()
        if st:
            st_counts[st] = st_counts.get(st, 0) + 1
    sales_types = [
        {"key": st, "value": st, "label": st, "count": count}
        for st, count in sorted(st_counts.items())
    ]

    # 3. Regions (mapped canonical names + Other)
    reg_counts: Dict[str, int] = {
        "North America": 0,
        "LATAM": 0,
        "Middle East and North Africa": 0,
        "APAC": 0,
        "Europe": 0,
        "Africa": 0,
        "Other": 0,
    }
    for o in opps:
        sub = (o.revised_sub_region or "").strip()
        can = REGION_MAP.get(sub, "Other")
        reg_counts[can] = reg_counts.get(can, 0) + 1

    regions = [
        {"key": r, "value": r, "label": r, "count": count}
        for r, count in reg_counts.items()
        if count > 0 or r != "Other"
    ]

    # 4. Business Units (Atomic pieces and raw combinations)
    atomic_bu_counts: Dict[str, int] = {}
    for o in opps:
        raw_bu = o.business_unit_raw or ""
        if raw_bu:
            pieces = set(p.strip() for p in raw_bu.split(";") if p.strip())
            for p in pieces:
                atomic_bu_counts[p] = atomic_bu_counts.get(p, 0) + 1

    business_units = [
        {"key": bu, "value": bu, "label": bu, "count": count}
        for bu, count in sorted(atomic_bu_counts.items())
    ]

    # 5. Forecast Categories (All 5 canonical always present)
    fc_counts = {cat: 0 for cat in CANONICAL_FORECAST_CATEGORIES}
    for o in opps:
        fc = (o.forecast_category or "").strip()
        if fc in ("Closed", "Commit", "Best Case", "Pipeline"):
            fc_counts[fc] += 1
        else:
            fc_counts["Not yet proposed"] += 1

    forecast_categories = [
        {"key": cat, "value": cat, "label": cat, "count": fc_counts[cat]}
        for cat in CANONICAL_FORECAST_CATEGORIES
    ]

    # 6. Approval Statuses
    app_counts = {st: 0 for st in CANONICAL_APPROVAL_STATUSES}
    rejected_count = 0
    for o in opps:
        ap = (o.approval_status or "").strip()
        if ap in ("Approved", "Approved - 2nd"):
            app_counts["Approved"] += 1
        elif ap in ("Pending Approval", "Pending-Approval"):
            app_counts["Pending Approval"] += 1
        elif ap == "Rejected":
            rejected_count += 1
        else:
            app_counts["Not submitted"] += 1

    approval_statuses = [
        {"key": st, "value": st, "label": st, "count": app_counts[st]}
        for st in CANONICAL_APPROVAL_STATUSES
    ]
    if rejected_count > 0:
        approval_statuses.append({"key": "Rejected", "value": "Rejected", "label": "Rejected", "count": rejected_count})

    return {
        "as_of": snap.snapshot_date.isoformat(),
        "current_quarter": cq,
        "current_quarter_label": ScopeService.quarter_label(cq),
        "total_deals": total_deals,
        "snapshot_dates": snapshot_dates,
        "quarters": quarters,
        "fiscal_years": fiscal_years,
        "sales_types": sales_types,
        "regions": regions,
        "business_units": business_units,
        "forecast_categories": forecast_categories,
        "approval_statuses": approval_statuses,
    }
