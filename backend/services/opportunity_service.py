"""
OpportunityService — paginated, filterable access to opportunities.
"""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot
from backend.models.change_log import ChangeLog
from backend.services.scopes import ScopeService
from backend.services.context import UserContext
from backend.services.analytics_service import AnalyticsService

log = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


class OpportunityService:
    def __init__(self, db: Session):
        self.db = db
        self._analytics = AnalyticsService(db)

    def _build_filtered_query(
        self,
        ctx: UserContext,
        snapshot_id: str | None = None,
        forecast_category: list[str] | None = None,
        approval_status: list[str] | None = None,
        sub_region: list[str] | None = None,
        business_unit: list[str] | None = None,
        business_unit_raw: list[str] | None = None,
        service_expiry_period: list[str] | None = None,
        closing_year: list[int] | None = None,
        min_acv: float | None = None,
        max_acv: float | None = None,
        search: str | None = None,
        scope: str = "all",
        include_deleted_lost: bool = True,
        filter_spec: Optional[ScopeService.FilterSpec] = None,
    ):
        snap = self._analytics._resolve_snapshot(ctx, snapshot_id)
        if snap is None:
            return None, None

        q = self.db.query(Opportunity).filter(Opportunity.snapshot_id == snap.id)

        if filter_spec:
            res = ScopeService.resolve(filter_spec, snapshot=snap, as_of_date=snap.snapshot_date)
            q = q.filter(*res.conditions)
        else:
            if not include_deleted_lost:
                q = q.filter(Opportunity.is_deleted_or_lost == False)

            s = (scope or "renewals").lower()
            if s == "renewals":
                q = q.filter(ScopeService.is_renewals())
            elif s == "all":
                pass
            else:
                # Fallback to resolve as period
                fs = ScopeService.FilterSpec(period=s)
                res = ScopeService.resolve(fs, snapshot=snap, as_of_date=snap.snapshot_date)
                q = q.filter(*res.conditions)

        if forecast_category:
            q = q.filter(Opportunity.forecast_category.in_(forecast_category))
        if approval_status:
            norm_statuses = []
            for s in approval_status:
                norm_statuses.append(s)
                if s in ["Pending Approval", "Pending-Approval"]:
                    norm_statuses.extend(["Pending Approval", "Pending-Approval"])
            q = q.filter(Opportunity.approval_status.in_(list(set(norm_statuses))))
        if sub_region:
            q = q.filter(Opportunity.sub_region.in_(sub_region))
        if business_unit:
            bu_conditions = [Opportunity.business_unit_primary.in_(business_unit)]
            for bu in business_unit:
                bu_conditions.append(Opportunity.business_unit_raw.ilike(f"%{bu}%"))
            q = q.filter(or_(*bu_conditions))
        if business_unit_raw:
            q = q.filter(Opportunity.business_unit_raw.in_(business_unit_raw))
        if service_expiry_period:
            q = q.filter(Opportunity.service_expiry_period.in_(service_expiry_period))
        if closing_year:
            q = q.filter(Opportunity.closing_year.in_(closing_year))
        if min_acv is not None:
            q = q.filter(Opportunity.forecast_acv_amount >= min_acv)
        if max_acv is not None:
            q = q.filter(Opportunity.forecast_acv_amount <= max_acv)
        if search:
            pattern = f"%{search}%"
            q = q.filter(
                or_(
                    Opportunity.opportunity_name.ilike(pattern),
                    Opportunity.account_name.ilike(pattern),
                    Opportunity.opportunity_id_18.ilike(pattern),
                    Opportunity.opportunity_owner.ilike(pattern),
                )
            )

        return q, snap

    def list_opportunities(
        self,
        ctx: UserContext,
        snapshot_id: str | None = None,
        forecast_category: list[str] | None = None,
        approval_status: list[str] | None = None,
        sub_region: list[str] | None = None,
        business_unit: list[str] | None = None,
        business_unit_raw: list[str] | None = None,
        service_expiry_period: list[str] | None = None,
        closing_year: list[int] | None = None,
        min_acv: float | None = None,
        max_acv: float | None = None,
        search: str | None = None,
        sort_by: str | None = None,
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        scope: str = "all",
        include_deleted_lost: bool = True,
        filter_spec: Optional[ScopeService.FilterSpec] = None,
    ) -> dict:
        q, snap = self._build_filtered_query(
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
            filter_spec=filter_spec,
        )
        if q is None:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}

        total = q.count()

        # Dynamic sorting
        sort_col = Opportunity.forecast_acv_amount
        if sort_by == "opportunity_name":
            sort_col = Opportunity.opportunity_name
        elif sort_by == "account_name":
            sort_col = Opportunity.account_name
        elif sort_by == "close_date":
            sort_col = Opportunity.close_date
        elif sort_by == "probability_pct":
            sort_col = Opportunity.probability_pct
        elif sort_by == "sub_region":
            sort_col = Opportunity.sub_region
        elif sort_by == "business_unit":
            sort_col = Opportunity.business_unit_primary
        elif sort_by == "forecast_category":
            sort_col = Opportunity.forecast_category
        elif sort_by == "approval_status":
            sort_col = Opportunity.approval_status
        elif sort_by == "service_expiry_period":
            sort_col = Opportunity.service_expiry_period

        if sort_dir.lower() == "asc":
            q = q.order_by(sort_col.asc().nullslast())
        else:
            q = q.order_by(sort_col.desc().nullslast())

        page_size = min(page_size, MAX_PAGE_SIZE)
        offset = (page - 1) * page_size
        items = q.offset(offset).limit(page_size).all()

        return {
            "items": [self._to_dict(o) for o in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if total > 0 else 0,
        }

    def export_opportunities_csv(
        self,
        ctx: UserContext,
        snapshot_id: str | None = None,
        forecast_category: list[str] | None = None,
        approval_status: list[str] | None = None,
        sub_region: list[str] | None = None,
        business_unit: list[str] | None = None,
        business_unit_raw: list[str] | None = None,
        service_expiry_period: list[str] | None = None,
        closing_year: list[int] | None = None,
        min_acv: float | None = None,
        max_acv: float | None = None,
        search: str | None = None,
        scope: str = "all",
        include_deleted_lost: bool = True,
    ) -> str:
        import csv
        import io

        q, snap = self._build_filtered_query(
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
        if q is None:
            return ""

        items = q.order_by(Opportunity.forecast_acv_amount.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Opportunity ID",
            "Opportunity Name",
            "Account Name",
            "Sub-Region",
            "Country / Territory",
            "Business Unit",
            "Forecast Category",
            "Forecast ACV ($)",
            "Approval Status",
            "Service Expiry Period",
            "Closing Year",
            "Close Date",
            "Probability (%)",
            "Owner",
        ])

        for o in items:
            writer.writerow([
                o.opportunity_id_18 or "",
                o.opportunity_name or "",
                o.account_name or "",
                o.sub_region or "",
                o.country_territory or "",
                o.business_unit_primary or o.business_unit_raw or "",
                o.forecast_category or "",
                f"{float(o.forecast_acv_amount):.2f}" if o.forecast_acv_amount else "0.00",
                o.approval_status or "",
                o.service_expiry_period or "",
                o.closing_year or "",
                o.close_date.isoformat() if o.close_date else "",
                o.probability_pct if o.probability_pct is not None else "",
                o.opportunity_owner or "",
            ])

        return output.getvalue()


    def get_opportunity(self, ctx: UserContext, opp_id: str, snapshot_id: str | None = None) -> dict | None:
        snap = self._analytics._resolve_snapshot(ctx, snapshot_id)
        if snap is None:
            return None
        opp = (
            self.db.query(Opportunity)
            .filter(Opportunity.snapshot_id == snap.id, Opportunity.opportunity_id_18 == opp_id)
            .first()
        )
        if not opp:
            return None
        data = self._to_dict(opp)
        from backend.services.risk_service import RiskService
        risk_svc = RiskService(self.db)
        risk = risk_svc.compute_deal_risk(opp, as_of_date=snap.snapshot_date)
        data["risk_score"] = risk["score"]
        data["risk_level"] = risk["level"]
        data["risk_factors"] = risk["factors"]
        data["risk_summary"] = risk["summary"]
        return data

    def get_opportunity_history(self, ctx: UserContext, opp_id: str) -> list[dict]:
        """Return field values across all snapshots for a single opportunity."""
        opps = (
            self.db.query(Opportunity, UploadSnapshot)
            .join(UploadSnapshot, Opportunity.snapshot_id == UploadSnapshot.id)
            .filter(Opportunity.opportunity_id_18 == opp_id)
            .order_by(UploadSnapshot.snapshot_date)
            .all()
        )
        return [
            {**self._to_dict(opp), "snapshot_date": snap.snapshot_date.isoformat(), "snapshot_label": snap.label}
            for opp, snap in opps
        ]

    def get_opportunity_changelog(self, ctx: UserContext, opp_id: str) -> list[dict]:
        """Return all changelog entries for a single opportunity."""
        changes = (
            self.db.query(ChangeLog)
            .filter(ChangeLog.opportunity_id_18 == opp_id)
            .order_by(ChangeLog.computed_at.desc())
            .all()
        )
        return [
            {
                "id": c.id,
                "opportunity_id_18": c.opportunity_id_18,
                "opportunity_name": c.opportunity_name,
                "changed_column": c.changed_column,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "change_type": c.change_type,
                "computed_at": c.computed_at.isoformat() if c.computed_at else None,
            }
            for c in changes
        ]

    def get_filter_options(self, ctx: UserContext, snapshot_id: str | None = None) -> dict:
        """Return unique values for all filterable dimensions."""
        snap = self._analytics._resolve_snapshot(ctx, snapshot_id)
        if snap is None:
            return {}

        opps = self.db.query(Opportunity).filter(Opportunity.snapshot_id == snap.id).all()
        acv_vals = [float(o.forecast_acv_amount) for o in opps if o.forecast_acv_amount]
        return {
            "forecast_categories": sorted({o.forecast_category for o in opps if o.forecast_category}),
            "approval_statuses": sorted({o.approval_status for o in opps if o.approval_status}),
            "sub_regions": sorted({o.sub_region for o in opps if o.sub_region}),
            "business_units": sorted({o.business_unit_primary for o in opps if o.business_unit_primary}),
            "service_expiry_periods": sorted({o.service_expiry_period for o in opps if o.service_expiry_period}),
            "closing_years": sorted({o.closing_year for o in opps if o.closing_year}),
            "min_acv": round(min(acv_vals), 2) if acv_vals else 0.0,
            "max_acv": round(max(acv_vals), 2) if acv_vals else 0.0,
        }

    def _to_dict(self, o: Opportunity) -> dict:
        return {
            "id": o.id,
            "opportunity_id_18": o.opportunity_id_18,
            "opportunity_name": o.opportunity_name,
            "account_name": o.account_name,
            "sub_region": o.sub_region,
            "revised_sub_region": o.revised_sub_region,
            "country_territory": o.country_territory,
            "business_unit_primary": o.business_unit_primary,
            "business_unit_raw": o.business_unit_raw,
            "forecast_category": o.forecast_category,
            "forecast_acv_amount": float(o.forecast_acv_amount) if o.forecast_acv_amount else None,
            "close_date": o.close_date.isoformat() if o.close_date else None,
            "probability_pct": o.probability_pct,
            "approval_status": o.approval_status,
            "service_expiry_period": o.service_expiry_period,
            "closing_year": o.closing_year,
            "renewal_category": o.renewal_category,
            "months_delayed": o.months_delayed,
            "opportunity_owner": o.opportunity_owner,
            "last_modified_date": o.last_modified_date.isoformat() if o.last_modified_date else None,
        }
