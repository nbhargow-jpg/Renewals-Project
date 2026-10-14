"""
V2 Overview router — /api/v2/overview/...
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.context import UserContext, get_user_context
from backend.services.v2_overview_service import V2OverviewService
from backend.services.scopes import FilterSpec
from backend.routers.deps import get_filter_spec

router = APIRouter(prefix="/api/v2/overview", tags=["v2-overview"])


def _svc(db: Session = Depends(get_db)) -> V2OverviewService:
    return V2OverviewService(db)


@router.get("/summary")
def overview_summary(
    filter_spec: FilterSpec = Depends(get_filter_spec),
    svc: V2OverviewService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_summary(ctx, filter_spec=filter_spec)


@router.get("/movements")
def overview_movements(
    compare: Optional[str] = Query(None),
    filter_spec: FilterSpec = Depends(get_filter_spec),
    svc: V2OverviewService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_movements(ctx, compare=compare, filter_spec=filter_spec)


@router.get("/regional-breakdown")
def overview_regional_breakdown(
    filter_spec: FilterSpec = Depends(get_filter_spec),
    svc: V2OverviewService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_regional_breakdown(ctx, filter_spec=filter_spec)


@router.get("/deals")
def overview_deals(
    category: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    approval_status: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    compare: Optional[str] = Query(None),
    filter_spec: FilterSpec = Depends(get_filter_spec),
    svc: V2OverviewService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_deals(
        ctx,
        category=category,
        region=region,
        approval_status=approval_status,
        kind=kind,
        compare=compare,
        filter_spec=filter_spec,
    )
