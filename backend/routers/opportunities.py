from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from typing import Optional, List

from backend.database import get_db
from backend.services.context import UserContext, get_user_context
from backend.services.opportunity_service import OpportunityService
from backend.services.scopes import FilterSpec
from backend.routers.deps import get_filter_spec

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def _svc(db: Session = Depends(get_db)) -> OpportunityService:
    return OpportunityService(db)


@router.get("")
def list_opportunities(
    snapshot_id: Optional[str] = Query(None),
    forecast_category: Optional[List[str]] = Query(None),
    approval_status: Optional[List[str]] = Query(None),
    sub_region: Optional[List[str]] = Query(None),
    business_unit: Optional[List[str]] = Query(None),
    business_unit_raw: Optional[List[str]] = Query(None),
    service_expiry_period: Optional[List[str]] = Query(None),
    closing_year: Optional[List[int]] = Query(None),
    min_acv: Optional[float] = Query(None),
    max_acv: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_dir: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(True),
    filter_spec: FilterSpec = Depends(get_filter_spec),
    svc: OpportunityService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.list_opportunities(
        ctx,
        snapshot_id=snapshot_id,
        forecast_category=forecast_category,
        approval_status=approval_status,
        sub_region=sub_region,
        business_unit=business_unit,
        business_unit_raw=business_unit_raw,
        service_expiry_period=service_expiry_period,
        closing_year=closing_year,
        min_acv=min_acv,
        max_acv=max_acv,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
        scope=scope,
        include_deleted_lost=include_deleted_lost,
        filter_spec=filter_spec,
    )


@router.get("/export")
def export_opportunities(
    snapshot_id: Optional[str] = Query(None),
    forecast_category: Optional[List[str]] = Query(None),
    approval_status: Optional[List[str]] = Query(None),
    sub_region: Optional[List[str]] = Query(None),
    business_unit: Optional[List[str]] = Query(None),
    business_unit_raw: Optional[List[str]] = Query(None),
    service_expiry_period: Optional[List[str]] = Query(None),
    closing_year: Optional[List[int]] = Query(None),
    min_acv: Optional[float] = Query(None),
    max_acv: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(False),
    svc: OpportunityService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    csv_data = svc.export_opportunities_csv(
        ctx,
        snapshot_id=snapshot_id,
        forecast_category=forecast_category,
        approval_status=approval_status,
        sub_region=sub_region,
        business_unit=business_unit,
        business_unit_raw=business_unit_raw,
        service_expiry_period=service_expiry_period,
        closing_year=closing_year,
        min_acv=min_acv,
        max_acv=max_acv,
        search=search,
        scope=scope,
        include_deleted_lost=include_deleted_lost,
    )
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=opportunities_export.csv"},
    )



@router.get("/filter-options")
def filter_options(
    snapshot_id: Optional[str] = Query(None),
    svc: OpportunityService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_filter_options(ctx, snapshot_id)


@router.get("/{opp_id}/history")
def opportunity_history(
    opp_id: str,
    svc: OpportunityService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_opportunity_history(ctx, opp_id)


@router.get("/{opp_id}/changelog")
def opportunity_changelog(
    opp_id: str,
    svc: OpportunityService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_opportunity_changelog(ctx, opp_id)


@router.get("/{opp_id}")
def get_opportunity(
    opp_id: str,
    snapshot_id: Optional[str] = Query(None),
    svc: OpportunityService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    result = svc.get_opportunity(ctx, opp_id, snapshot_id)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return result
