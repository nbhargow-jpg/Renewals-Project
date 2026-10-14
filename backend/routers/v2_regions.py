from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from backend.database import get_db
from backend.services.context import UserContext, get_user_context
from backend.services.v2_regions_service import V2RegionsService
from backend.services.scopes import FilterSpec
from backend.routers.deps import get_filter_spec

router = APIRouter(prefix="/api/v2/regions", tags=["v2-regions"])


def _svc(db: Session = Depends(get_db)) -> V2RegionsService:
    return V2RegionsService(db)


@router.get("/summary")
def get_regions_summary(
    filter_spec: FilterSpec = Depends(get_filter_spec),
    svc: V2RegionsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context)
):
    return svc.get_summary(ctx, filter_spec=filter_spec)


@router.get("/{region}/summary")
def get_single_region_summary(
    region: str,
    as_of: Optional[str] = Query(None),
    exclude_deleted_lost: bool = Query(False),
    svc: V2RegionsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context)
):
    return svc.get_region_summary(ctx, region=region, as_of=as_of, exclude_deleted_lost=exclude_deleted_lost)


@router.get("/{region}/movements")
def get_region_movements(
    region: str,
    compare: str = Query("yesterday", pattern="^(yesterday|last_week)$"),
    exclude_deleted_lost: bool = Query(False),
    svc: V2RegionsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context)
):
    return svc.get_movements(ctx, region=region, compare=compare, exclude_deleted_lost=exclude_deleted_lost)


@router.get("/deals")
def get_region_deals(
    region: str = Query(""),
    category: str = Query(""),
    status: str = Query(""),
    bu: str = Query(""),
    as_of: str = Query(""),
    filter_spec: FilterSpec = Depends(get_filter_spec),
    svc: V2RegionsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context)
):
    return svc.get_deals(ctx, region=region, category=category, status=status, bu=bu, as_of=as_of, filter_spec=filter_spec)


@router.get("/{region}/top-opportunities")
def get_region_top_opps(
    region: str,
    limit: int = Query(10),
    svc: V2RegionsService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context)
):
    return svc.get_top_opportunities(ctx, region=region, limit=limit)
