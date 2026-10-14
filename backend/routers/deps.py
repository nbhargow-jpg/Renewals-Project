"""
Shared router dependencies for v2 endpoints
"""
from typing import Optional, List
from fastapi import Query
from backend.services.scopes import FilterSpec

def get_filter_spec(
    as_of: Optional[str] = Query(None),
    compare: Optional[str] = Query("yesterday"),
    period: Optional[str] = Query("current_quarter"),
    sales_types: Optional[List[str]] = Query(None),
    regions: Optional[List[str]] = Query(None),
    business_units: Optional[List[str]] = Query(None),
    forecast_categories: Optional[List[str]] = Query(None),
    approval_statuses: Optional[List[str]] = Query(None),
    include_deleted_lost: Optional[bool] = Query(None),
    exclude_deleted: bool = Query(False),
) -> FilterSpec:
    idl = True
    if include_deleted_lost is not None:
        idl = bool(include_deleted_lost)
    elif exclude_deleted:
        idl = False

    return FilterSpec.from_params(
        as_of=as_of,
        compare=compare,
        period=period,
        sales_types=sales_types,
        regions=regions,
        business_units=business_units,
        forecast_categories=forecast_categories,
        approval_statuses=approval_statuses,
        include_deleted_lost=idl,
    )
