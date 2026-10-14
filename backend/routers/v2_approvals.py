from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from backend.database import get_db
from backend.services.context import UserContext
from backend.services.v2_approvals_service import V2ApprovalsService
from backend.services.scopes import FilterSpec
from backend.routers.deps import get_filter_spec

router = APIRouter(prefix="/api/v2/approvals", tags=["Approvals v2"])

@router.get("/distribution")
def get_approvals_distribution(
    as_of: Optional[str] = None,
    compare: Optional[str] = None,
    exclude_deleted_lost: bool = Query(False),
    filter_spec: FilterSpec = Depends(get_filter_spec),
    db: Session = Depends(get_db)
):
    ctx = UserContext()
    svc = V2ApprovalsService(db)
    return svc.get_distribution(
        ctx=ctx,
        as_of=as_of,
        compare=compare,
        exclude_deleted_lost=exclude_deleted_lost,
        filter_spec=filter_spec
    )

@router.get("/deals")
def get_approvals_deals(
    status: Optional[str] = None,
    category: Optional[str] = None,
    region: Optional[str] = None,
    business_unit: Optional[str] = None,
    as_of: Optional[str] = None,
    exclude_deleted_lost: bool = Query(False),
    filter_spec: FilterSpec = Depends(get_filter_spec),
    db: Session = Depends(get_db)
):
    ctx = UserContext()
    svc = V2ApprovalsService(db)
    return svc.get_deals(
        ctx=ctx,
        status=status,
        category=category,
        as_of=as_of,
        exclude_deleted_lost=exclude_deleted_lost,
        region=region,
        business_unit=business_unit,
        filter_spec=filter_spec
    )
