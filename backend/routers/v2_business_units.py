from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from backend.database import get_db
from backend.services.context import get_user_context, UserContext
from backend.services.v2_business_units_service import V2BusinessUnitsService
from backend.services.scopes import FilterSpec
from backend.routers.deps import get_filter_spec

router = APIRouter(prefix="/api/v2/business-units", tags=["business-units-v2"])


@router.get("/summary")
def get_bu_summary(
    filter_spec: FilterSpec = Depends(get_filter_spec),
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(get_user_context)
):
    svc = V2BusinessUnitsService(db)
    return svc.get_summary(ctx, filter_spec=filter_spec)


@router.get("/deals")
def get_bu_deals(
    bu: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    filter_spec: FilterSpec = Depends(get_filter_spec),
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(get_user_context)
):
    svc = V2BusinessUnitsService(db)
    return svc.get_deals(
        ctx,
        bu=bu,
        category=category,
        status=status,
        filter_spec=filter_spec,
    )


@router.get("/top-opportunities")
def get_bu_top_opportunities(
    bu: Optional[str] = None,
    limit: int = 10,
    filter_spec: FilterSpec = Depends(get_filter_spec),
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(get_user_context)
):
    svc = V2BusinessUnitsService(db)
    return svc.get_top_opportunities(ctx, bu=bu, limit=limit, filter_spec=filter_spec)
