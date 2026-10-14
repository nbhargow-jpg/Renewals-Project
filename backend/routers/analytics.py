from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from backend.database import get_db
from backend.services.context import UserContext, get_user_context
from backend.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _svc(db: Session = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db)


@router.get("/kpis")
def kpis(
    snapshot_id: Optional[str] = Query(None),
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(False),
    svc: AnalyticsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_kpis(ctx, snapshot_id, scope=scope, include_deleted_lost=include_deleted_lost)


@router.get("/forecast-summary")
def forecast_summary(
    snapshot_id: Optional[str] = Query(None),
    compare_to: Optional[str] = Query(None),
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(False),
    svc: AnalyticsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_forecast_summary(ctx, snapshot_id, compare_to, scope=scope, include_deleted_lost=include_deleted_lost)


@router.get("/approval-status")
def approval_status(
    snapshot_id: Optional[str] = Query(None),
    compare_to: Optional[str] = Query(None),
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(False),
    svc: AnalyticsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_approval_status(ctx, snapshot_id, compare_to, scope=scope, include_deleted_lost=include_deleted_lost)


@router.get("/approval-by-bu")
def approval_by_bu(
    snapshot_id: Optional[str] = Query(None),
    mode: Optional[str] = Query("as_in_excel"),
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(False),
    svc: AnalyticsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_approval_by_bu(ctx, snapshot_id, mode, scope=scope, include_deleted_lost=include_deleted_lost)


@router.get("/regions")
@router.get("/regions-overview")
def regions_overview(
    snapshot_id: Optional[str] = Query(None),
    compare_to: Optional[str] = Query(None),
    mode: str = Query("as_in_excel"),
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(False),
    svc: AnalyticsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_sub_regions_overview(ctx, snapshot_id, compare_to, mode, scope=scope, include_deleted_lost=include_deleted_lost)


@router.get("/history-overview")
def history_overview(
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(False),
    svc: AnalyticsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_history_overview(ctx, scope=scope, include_deleted_lost=include_deleted_lost)


@router.get("/top-regions")
def top_regions(
    snapshot_id: Optional[str] = Query(None),
    top_n: int = Query(10, ge=1, le=50),
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(False),
    svc: AnalyticsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_top_regions(ctx, snapshot_id, top_n, scope=scope, include_deleted_lost=include_deleted_lost)


@router.get("/top-regions-bu")
def top_regions_bu(
    snapshot_id: Optional[str] = Query(None),
    top_n: int = Query(10, ge=1, le=50),
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(False),
    svc: AnalyticsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_top_regions_bu(ctx, snapshot_id, top_n, scope=scope, include_deleted_lost=include_deleted_lost)


@router.get("/forecast-movement")
def forecast_movement(
    snapshot_id: Optional[str] = Query(None),
    compare_to: Optional[str] = Query(None),
    svc: AnalyticsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_forecast_movement(ctx, snapshot_id, compare_to)



@router.get("/acv-changes")
def acv_changes(
    snapshot_id: Optional[str] = Query(None),
    compare_to: Optional[str] = Query(None),
    svc: AnalyticsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_acv_changes(ctx, snapshot_id, compare_to)



@router.get("/expiry-quarters")
def expiry_quarters(
    snapshot_id: Optional[str] = Query(None),
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(False),
    svc: AnalyticsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_expiry_quarters(ctx, snapshot_id, scope=scope, include_deleted_lost=include_deleted_lost)


@router.get("/closing-year-trend")
def closing_year_trend(
    snapshot_id: Optional[str] = Query(None),
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(False),
    svc: AnalyticsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_closing_year_trend(ctx, snapshot_id, scope=scope, include_deleted_lost=include_deleted_lost)


@router.get("/trend-sparklines")
def trend_sparklines(
    metric: str = Query("total_acv"),
    days: int = Query(30, ge=7, le=365),
    svc: AnalyticsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_trend_sparklines(ctx, metric, days)


@router.get("/compare")
def compare_dates(
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(False),
    svc: AnalyticsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    from datetime import date
    from fastapi import HTTPException
    try:
        f_date = date.fromisoformat(from_date)
        t_date = date.fromisoformat(to_date)
    except ValueError:
        raise HTTPException(status_code=422, detail="Both 'from' and 'to' must be formatted as YYYY-MM-DD")
    
    res = svc.get_comparison(ctx, f_date, t_date, scope=scope, include_deleted_lost=include_deleted_lost)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res
