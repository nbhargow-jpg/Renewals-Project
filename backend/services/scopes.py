from __future__ import annotations

import re
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Tuple, List, Optional, Any, Dict
from pydantic import BaseModel, Field
from sqlalchemy import or_, and_, ColumnElement

from backend.config import settings
from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot


REGION_MAP: dict[str, str] = {
    "Europe":        "Europe",
    "APAC":          "APAC",
    "AFRICA":        "Africa",
    "MENA":          "Middle East and North Africa",
    "NAMR":          "North America",
    "South America": "LATAM",
}

CANONICAL_TO_REV: dict[str, list[str]] = {}
for rev, can in REGION_MAP.items():
    CANONICAL_TO_REV.setdefault(can, []).append(rev)

CANONICAL_FORECAST_CATEGORIES = [
    "Closed",
    "Commit",
    "Best Case",
    "Pipeline",
    "Not yet proposed",
]

CANONICAL_APPROVAL_STATUSES = [
    "Approved",
    "Pending Approval",
    "Not submitted",
]


class FilterSpec(BaseModel):
    as_of: Optional[str] = None
    compare: Optional[str] = "yesterday"
    period: str = "current_quarter"
    sales_types: List[str] = Field(default_factory=lambda: ["Renewals"])
    regions: List[str] = Field(default_factory=list)
    business_units: List[str] = Field(default_factory=list)
    forecast_categories: List[str] = Field(default_factory=list)
    approval_statuses: List[str] = Field(default_factory=list)
    include_deleted_lost: bool = True

    @classmethod
    def from_params(
        cls,
        as_of: Optional[str] = None,
        compare: Optional[str] = "yesterday",
        period: Optional[str] = "current_quarter",
        sales_types: Optional[List[str] | str] = None,
        regions: Optional[List[str] | str] = None,
        business_units: Optional[List[str] | str] = None,
        forecast_categories: Optional[List[str] | str] = None,
        approval_statuses: Optional[List[str] | str] = None,
        include_deleted_lost: Optional[bool] = True,
    ) -> FilterSpec:
        def _parse_list(val: Any, default: List[str]) -> List[str]:
            if val is None:
                return default
            if isinstance(val, list):
                res = []
                for item in val:
                    for part in str(item).split(","):
                        p = part.strip()
                        if p:
                            res.append(p)
                return res
            if isinstance(val, str):
                parts = [p.strip() for p in val.split(",") if p.strip()]
                return parts
            return default

        st = _parse_list(sales_types, ["Renewals"])
        reg = _parse_list(regions, [])
        bu = _parse_list(business_units, [])
        fc = _parse_list(forecast_categories, [])
        appr = _parse_list(approval_statuses, [])

        return cls(
            as_of=as_of,
            compare=compare or "yesterday",
            period=period or "current_quarter",
            sales_types=st,
            regions=reg,
            business_units=bu,
            forecast_categories=fc,
            approval_statuses=appr,
            include_deleted_lost=True if include_deleted_lost is None else bool(include_deleted_lost),
        )


class ScopeResolution:
    def __init__(
        self,
        conditions: list,
        resolved_quarter: str,
        data_slice: str,
        filters_applied: dict[str, Any],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ):
        self.conditions = conditions
        self.resolved_quarter = resolved_quarter
        self.data_slice = data_slice
        self.filters_applied = filters_applied
        self.start_date = start_date
        self.end_date = end_date

    @property
    def label(self) -> str:
        return self.data_slice

    @property
    def period(self) -> str:
        return self.resolved_quarter

    def to_criterion(self) -> ColumnElement[bool]:
        if not self.conditions:
            return True
        if len(self.conditions) == 1:
            return self.conditions[0]
        return and_(*self.conditions)


class ScopeService:
    @staticmethod
    def quarter_of(d: date) -> str:
        """Returns the fiscal quarter of a date, e.g., 'Q4-2026'."""
        if not d:
            return ""
        start_month = settings.FISCAL_YEAR_START_MONTH
        m = d.month - start_month
        if m < 0:
            m += 12
            fy = d.year
        else:
            fy = d.year + (1 if start_month > 1 else 0)
        
        q = (m // 3) + 1
        return f"Q{q}-{fy}"

    @staticmethod
    def quarter_label(q_str: str) -> str:
        """Converts 'Q4-2026' to 'Q4 FY26'."""
        if not q_str or "-" not in q_str:
            return q_str
        q, y = q_str.split("-")
        return f"{q} FY{y[-2:]}"

    @staticmethod
    def current_quarter(snapshot_date: date) -> str:
        return ScopeService.quarter_of(snapshot_date)

    @staticmethod
    def offset_quarter(q_str: str, offset: int) -> str:
        """Returns quarter offset by N quarters, e.g. Q4-2026 + 1 -> Q1-2027."""
        if not q_str or "-" not in q_str:
            return q_str
        q_part, y_part = q_str.split("-")
        q = int(q_part[1])
        y = int(y_part)
        total_q = (y * 4 + (q - 1)) + offset
        res_y = total_q // 4
        res_q = (total_q % 4) + 1
        return f"Q{res_q}-{res_y}"

    @staticmethod
    def quarter_bounds(q_str: str) -> Tuple[date, date]:
        """Returns (start_date, end_date) for a given quarter 'Qx-YYYY'."""
        if not q_str or "-" not in q_str:
            return date.today(), date.today()
        q_part, y_part = q_str.split("-")
        q = int(q_part[1])
        y = int(y_part)
        
        start_month = settings.FISCAL_YEAR_START_MONTH
        
        if start_month > 1:
            calendar_year = y - 1
        else:
            calendar_year = y
            
        q_start_month = start_month + (q - 1) * 3
        if q_start_month > 12:
            q_start_month -= 12
            calendar_year += 1
            
        start_date = date(calendar_year, q_start_month, 1)
        end_date = start_date + relativedelta(months=3, days=-1)
        return start_date, end_date

    @staticmethod
    def is_renewals() -> ColumnElement[bool]:
        """Scope: renewals = sales_type == 'Renewals'"""
        return Opportunity.sales_type == "Renewals"

    @staticmethod
    def current_quarter_slice(quarter: str) -> ColumnElement[bool]:
        """Scope: renewals AND fiscal_period == current quarter"""
        return and_(
            ScopeService.is_renewals(),
            Opportunity.fiscal_period == quarter
        )

    @staticmethod
    def slippage(quarter: str) -> ColumnElement[bool]:
        """Scope: current_quarter_slice AND close_date after the quarter end"""
        _, end_date = ScopeService.quarter_bounds(quarter)
        return and_(
            ScopeService.current_quarter_slice(quarter),
            Opportunity.close_date > end_date
        )

    @staticmethod
    def delayed(quarter: str) -> ColumnElement[bool]:
        """Scope: renewals AND fiscal_period an earlier quarter of the SAME fiscal year AND forecast_category != 'Closed'"""
        cq = quarter
        if not cq or "-" not in cq:
            return False
        
        q_part, y_part = cq.split("-")
        current_q = int(q_part[1])
        current_y = int(y_part)
        
        earlier_quarters = [f"Q{q}-{current_y}" for q in range(1, current_q)]
        
        return and_(
            ScopeService.is_renewals(),
            Opportunity.fiscal_period.in_(earlier_quarters),
            Opportunity.forecast_category != "Closed"
        )

    @staticmethod
    def expiry_window(quarter: str) -> ColumnElement[bool]:
        """Scope: renewals AND service_expiry_period in current fiscal year + next fiscal year"""
        cq = quarter
        if not cq or "-" not in cq:
            return False
        _, y_part = cq.split("-")
        current_y = int(y_part)
        next_y = current_y + 1
        
        valid_periods = []
        for y in (current_y, next_y):
            for q in range(1, 5):
                valid_periods.append(f"Q{q}-{y}")
                
        return and_(
            ScopeService.is_renewals(),
            Opportunity.service_expiry_period.in_(valid_periods)
        )

    @staticmethod
    def resolve(
        filter_spec: FilterSpec,
        snapshot: UploadSnapshot | None = None,
        as_of_date: Optional[date] = None,
    ) -> ScopeResolution:
        """
        Single entry point for resolving a FilterSpec into SQL / Pandas conditions.
        """
        ref_date = as_of_date
        if not ref_date and filter_spec.as_of:
            try:
                ref_date = date.fromisoformat(filter_spec.as_of)
            except ValueError:
                pass
        if not ref_date and snapshot:
            ref_date = snapshot.snapshot_date
        if not ref_date:
            ref_date = date.today()

        cq = ScopeService.quarter_of(ref_date)
        period = (filter_spec.period or "current_quarter").strip()

        conditions: list = []
        start_date: Optional[date] = None
        end_date: Optional[date] = None
        resolved_quarter = cq
        data_slice = ScopeService.quarter_label(cq)

        # 1. Period resolution
        if period == "current_quarter":
            resolved_quarter = cq
            data_slice = ScopeService.quarter_label(cq)
            conditions.append(Opportunity.fiscal_period == cq)
            start_date, end_date = ScopeService.quarter_bounds(cq)

        elif period == "previous_quarter":
            pq = ScopeService.offset_quarter(cq, -1)
            resolved_quarter = pq
            data_slice = ScopeService.quarter_label(pq)
            conditions.append(Opportunity.fiscal_period == pq)
            start_date, end_date = ScopeService.quarter_bounds(pq)

        elif period == "next_quarter":
            nq = ScopeService.offset_quarter(cq, 1)
            resolved_quarter = nq
            data_slice = ScopeService.quarter_label(nq)
            conditions.append(Opportunity.fiscal_period == nq)
            start_date, end_date = ScopeService.quarter_bounds(nq)

        elif re.match(r"^Q[1-4]-\d{4}$", period, re.IGNORECASE):
            norm_q = period.upper()
            resolved_quarter = norm_q
            data_slice = ScopeService.quarter_label(norm_q)
            conditions.append(Opportunity.fiscal_period == norm_q)
            start_date, end_date = ScopeService.quarter_bounds(norm_q)

        elif re.match(r"^FY\d{4}$", period, re.IGNORECASE):
            year_str = period[2:]
            fy_int = int(year_str)
            resolved_quarter = f"Q4-{year_str}"
            data_slice = f"FY{year_str[-2:]}"
            fy_quarters = [f"Q{i}-{year_str}" for i in range(1, 5)]
            conditions.append(Opportunity.fiscal_period.in_(fy_quarters))
            s1, _ = ScopeService.quarter_bounds(f"Q1-{year_str}")
            _, e4 = ScopeService.quarter_bounds(f"Q4-{year_str}")
            start_date, end_date = s1, e4

        elif ":" in period:
            parts = period.split(":")
            try:
                start_date = date.fromisoformat(parts[0].strip())
                end_date = date.fromisoformat(parts[1].strip())
                data_slice = f"{start_date.isoformat()} to {end_date.isoformat()}"
                conditions.append(Opportunity.close_date >= start_date)
                conditions.append(Opportunity.close_date <= end_date)
            except Exception:
                pass

        elif period == "all_periods" or period == "all":
            data_slice = "All Periods"
            resolved_quarter = cq

        else:
            resolved_quarter = cq
            data_slice = ScopeService.quarter_label(cq)
            conditions.append(Opportunity.fiscal_period == cq)

        # 2. Sales Types
        st = filter_spec.sales_types
        if st and not ("all" in [s.lower() for s in st] or "" in st):
            if len(st) == 1:
                conditions.append(Opportunity.sales_type == st[0])
            else:
                conditions.append(Opportunity.sales_type.in_(st))

        # 3. Regions (mapped canonical names + Other)
        regs = filter_spec.regions
        if regs and not ("all" in [r.lower() for r in regs] or "" in regs):
            reg_conds = []
            for r in regs:
                r_clean = r.strip()
                if r_clean == "Other":
                    mapped_revs = [rev for rev in REGION_MAP.keys()]
                    reg_conds.append(
                        or_(
                            Opportunity.revised_sub_region == None,
                            ~Opportunity.revised_sub_region.in_(mapped_revs),
                        )
                    )
                elif r_clean in CANONICAL_TO_REV:
                    revs = CANONICAL_TO_REV[r_clean]
                    reg_conds.append(Opportunity.revised_sub_region.in_(revs))
                elif r_clean in REGION_MAP:
                    reg_conds.append(Opportunity.revised_sub_region == r_clean)
            if reg_conds:
                conditions.append(or_(*reg_conds))

        # 4. Business Units (supports exact BU raw matches)
        bus = filter_spec.business_units
        if bus and not ("all" in [b.lower() for b in bus] or "" in bus):
            bu_conds = []
            for b in bus:
                b_clean = b.strip()
                if b_clean:
                    bu_conds.append(Opportunity.business_unit_raw == b_clean)
            if bu_conds:
                conditions.append(or_(*bu_conds))

        # 5. Forecast Categories
        fcs = filter_spec.forecast_categories
        if fcs and not ("all" in [f.lower() for f in fcs] or "" in fcs):
            fc_conds = []
            for f in fcs:
                f_clean = f.strip()
                if f_clean in ("Not yet proposed", "Blank", ""):
                    fc_conds.append(
                        or_(
                            Opportunity.forecast_category == None,
                            Opportunity.forecast_category == "",
                            Opportunity.forecast_category == "Blank",
                            ~Opportunity.forecast_category.in_(["Closed", "Commit", "Best Case", "Pipeline"]),
                        )
                    )
                else:
                    fc_conds.append(Opportunity.forecast_category == f_clean)
            if fc_conds:
                conditions.append(or_(*fc_conds))

        # 6. Approval Statuses
        apps = filter_spec.approval_statuses
        if apps and not ("all" in [a.lower() for a in apps] or "" in apps):
            app_conds = []
            for a in apps:
                a_clean = a.strip()
                if a_clean == "Approved":
                    app_conds.append(Opportunity.approval_status.in_(["Approved", "Approved - 2nd"]))
                elif a_clean in ("Pending Approval", "Pending-Approval"):
                    app_conds.append(Opportunity.approval_status.in_(["Pending Approval", "Pending-Approval"]))
                elif a_clean in ("Not submitted", "Blank"):
                    app_conds.append(
                        or_(
                            Opportunity.approval_status == None,
                            Opportunity.approval_status == "",
                            Opportunity.approval_status == "Blank",
                            Opportunity.approval_status == "Not submitted",
                        )
                    )
                elif a_clean == "Rejected":
                    app_conds.append(Opportunity.approval_status == "Rejected")
                else:
                    app_conds.append(Opportunity.approval_status == a_clean)
            if app_conds:
                conditions.append(or_(*app_conds))

        # 7. Include Deleted & Lost
        if not filter_spec.include_deleted_lost:
            conditions.append(Opportunity.is_deleted_or_lost == False)

        filters_applied = {
            "period": period,
            "sales_types": filter_spec.sales_types,
            "regions": filter_spec.regions,
            "business_units": filter_spec.business_units,
            "forecast_categories": filter_spec.forecast_categories,
            "approval_statuses": filter_spec.approval_statuses,
            "include_deleted_lost": filter_spec.include_deleted_lost,
            "as_of": filter_spec.as_of or (snapshot.snapshot_date.isoformat() if snapshot else None),
            "compare": filter_spec.compare,
        }

        return ScopeResolution(
            conditions=conditions,
            resolved_quarter=resolved_quarter,
            data_slice=data_slice,
            filters_applied=filters_applied,
            start_date=start_date,
            end_date=end_date,
        )
