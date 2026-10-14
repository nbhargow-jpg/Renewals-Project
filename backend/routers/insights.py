from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from backend.database import get_db
from backend.services.context import UserContext, get_user_context
from backend.services.risk_service import RiskService

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("")
def get_insights(
    snapshot_id: Optional[str] = Query(None),
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(False),
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(get_user_context),
):
    svc = RiskService(db)
    return svc.get_insights(ctx, snapshot_id, scope=scope, include_deleted_lost=include_deleted_lost)
