from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.services.context import UserContext
from backend.services.v2_expiry_service import V2ExpiryService
from backend.services.scopes import FilterSpec
from backend.routers.deps import get_filter_spec

router = APIRouter(prefix="/api/v2/expiry", tags=["v2_expiry"])

@router.get("/summary")
def get_summary(
    as_of: str = Query(None),
    compare: str = Query("yesterday"),
    exclude_deleted_lost: bool = Query(False),
    filter_spec: FilterSpec = Depends(get_filter_spec),
    db: Session = Depends(get_db)
):
    ctx = UserContext()
    svc = V2ExpiryService(db)
    return svc.get_summary(ctx, as_of=as_of, compare=compare, exclude_deleted_lost=exclude_deleted_lost, filter_spec=filter_spec)

@router.get("/deals")
def get_deals(
    quarter: str = Query(None),
    category: str = Query(None),
    as_of: str = Query(None),
    exclude_deleted_lost: bool = Query(False),
    slippage: bool = Query(False),
    filter_spec: FilterSpec = Depends(get_filter_spec),
    db: Session = Depends(get_db)
):
    ctx = UserContext()
    svc = V2ExpiryService(db)
    return svc.get_deals(ctx, quarter=quarter, category=category, as_of=as_of, exclude_deleted_lost=exclude_deleted_lost, slippage=slippage, filter_spec=filter_spec)