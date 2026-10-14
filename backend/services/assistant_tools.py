"""
assistant_tools.py — Strictly validated, read-only tools for the AI data assistant.

Safety Architecture:
- LLM never has database, SQL, or file access.
- All tools are strictly read-only, going through SQLAlchemy ORM / service layer.
- Parameter arguments are strictly validated against whitelists (fields, operators, dates).
- Cap 'n' at 50; row cap at 200 per call.
- Any invalid argument returns a clear, structured error dict instead of crashing.
- Every tool returns numbers calculated in code, plus link targets (page and params).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from decimal import Decimal

from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from backend.models.snapshot import UploadSnapshot
from backend.models.opportunity import Opportunity
from backend.models.change_log import ChangeLog, ForecastMovementLog
from backend.services.context import UserContext, ADMIN_CONTEXT
from backend.services.analytics_service import AnalyticsService

log = logging.getLogger(__name__)

WHITELIST_FIELDS = {
    "sub_region",
    "revised_sub_region",
    "country_territory",
    "business_unit",
    "business_unit_primary",
    "business_unit_raw",
    "forecast_category",
    "approval_status",
    "service_expiry_period",
    "closing_year",
    "opportunity_owner",
    "account_name",
    "opportunity_id_18",
    "min_acv",
    "max_acv",
    "search",
}

WHITELIST_OPERATORS = {"eq", "in", "gte", "lte", "like", "contains"}
ALLOWED_GROUP_BY = {"none", "region", "bu", "category", "expiry_quarter"}

MAX_N = 50
MAX_ROW_CAP = 200


class AssistantTools:
    """Read-only analytical tools with strict whitelist enforcement."""

    def __init__(
        self,
        db: Session,
        user_context: Optional[UserContext] = None,
        scope: str = "all",
        include_deleted_lost: bool = True,
    ):
        self.db = db
        self.ctx = user_context or ADMIN_CONTEXT
        self.analytics = AnalyticsService(db)
        self.scope = scope
        self.include_deleted_lost = include_deleted_lost

    # -----------------------------------------------------------------------
    # Validation Helpers
    # -----------------------------------------------------------------------

    def _parse_and_validate_date(self, d_val: Any, field_name: str = "date") -> tuple[Optional[date], Optional[str]]:
        """Validate that a date string or object corresponds to an existing snapshot."""
        if not d_val:
            return None, f"Missing required parameter '{field_name}'."

        if isinstance(d_val, str):
            try:
                target_date = datetime.strptime(d_val.strip(), "%Y-%m-%d").date()
            except ValueError:
                return None, f"Invalid date format for '{field_name}': '{d_val}'. Expected YYYY-MM-DD."
        elif isinstance(d_val, (date, datetime)):
            target_date = d_val if isinstance(d_val, date) else d_val.date()
        else:
            return None, f"Unsupported date type for '{field_name}': {type(d_val).__name__}."

        exists = self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == target_date).first()
        if not exists:
            # List available dates to help the user/LLM
            avail = [
                s.snapshot_date.isoformat()
                for s in self.db.query(UploadSnapshot.snapshot_date).order_by(UploadSnapshot.snapshot_date.desc()).all()
            ]
            return None, f"Date '{target_date.isoformat()}' does not exist as a snapshot. Available dates: {', '.join(avail)}."

        return target_date, None

    def _get_default_dates(self) -> tuple[date, date]:
        """Return the active today snapshot date and yesterday snapshot date."""
        today_snap = self.db.query(UploadSnapshot).filter(UploadSnapshot.is_active_today == True).first()
        if not today_snap:
            today_snap = self.db.query(UploadSnapshot).order_by(UploadSnapshot.snapshot_date.desc()).first()

        d_today = today_snap.snapshot_date if today_snap else date.today()

        yest_snap = (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.snapshot_date < d_today)
            .order_by(UploadSnapshot.snapshot_date.desc())
            .first()
        )
        d_yest = yest_snap.snapshot_date if yest_snap else d_today
        return d_today, d_yest

    # -----------------------------------------------------------------------
    # Tool 1: get_kpis(date)
    # -----------------------------------------------------------------------

    def get_kpis(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get high-level pipeline KPIs (total ACV, count, Commit, Closed) for a specific snapshot date.
        """
        if date:
            target_date, err = self._parse_and_validate_date(date, "date")
            if err:
                return {"tool": "get_kpis", "status": "error", "error": err}
        else:
            target_date, _ = self._get_default_dates()

        snap = self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == target_date).first()
        if not snap:
            return {"tool": "get_kpis", "status": "error", "error": f"Snapshot for date {target_date} not found."}

        # Query all opportunities for this snapshot
        opps = self.analytics._opps_for(snap, scope=self.scope, include_deleted_lost=self.include_deleted_lost)
        total_count = len(opps)
        total_acv = sum(float(o.forecast_acv_amount or 0) for o in opps)

        commit_opps = [o for o in opps if (o.forecast_category or "").strip() == "Commit"]
        commit_acv = sum(float(o.forecast_acv_amount or 0) for o in commit_opps)
        commit_count = len(commit_opps)

        closed_opps = [o for o in opps if (o.forecast_category or "").strip() == "Closed"]
        closed_acv = sum(float(o.forecast_acv_amount or 0) for o in closed_opps)
        closed_count = len(closed_opps)

        pipeline_opps = [o for o in opps if (o.forecast_category or "").strip() == "Pipeline"]
        pipeline_acv = sum(float(o.forecast_acv_amount or 0) for o in pipeline_opps)

        best_case_opps = [o for o in opps if (o.forecast_category or "").strip() == "Best Case"]
        best_case_acv = sum(float(o.forecast_acv_amount or 0) for o in best_case_opps)

        numbers = {
            "total_count": total_count,
            "total_acv": round(total_acv, 2),
            "commit_acv": round(commit_acv, 2),
            "commit_count": commit_count,
            "closed_acv": round(closed_acv, 2),
            "closed_count": closed_count,
            "pipeline_acv": round(pipeline_acv, 2),
            "best_case_acv": round(best_case_acv, 2),
        }

        return {
            "tool": "get_kpis",
            "status": "success",
            "numbers": numbers,
            "date_used": target_date.isoformat(),
            "link": {
                "page": "/pipeline",
                "params": {"snapshot_date": target_date.isoformat()},
            },
        }

    # -----------------------------------------------------------------------
    # Tool 2: compare(date_a, date_b)
    # -----------------------------------------------------------------------

    def compare(self, date_a: Optional[str] = None, date_b: Optional[str] = None) -> Dict[str, Any]:
        """
        Compare pipeline between two dates. Computes waterfall, net deltas, and counts.
        date_a is baseline (e.g. yesterday), date_b is current (e.g. today).
        """
        def_today, def_yest = self._get_default_dates()
        d_a_str = date_a or def_yest.isoformat()
        d_b_str = date_b or def_today.isoformat()

        d_a, err_a = self._parse_and_validate_date(d_a_str, "date_a")
        if err_a:
            return {"tool": "compare", "status": "error", "error": err_a}

        d_b, err_b = self._parse_and_validate_date(d_b_str, "date_b")
        if err_b:
            return {"tool": "compare", "status": "error", "error": err_b}

        # Use AnalyticsService to compute full comparison & waterfall
        comp = self.analytics.get_comparison(self.ctx, d_a, d_b)
        waterfall = comp.get("waterfall", {})
        delta_acv = round(waterfall.get("end_acv", 0) - waterfall.get("start_acv", 0), 2)
        delta_count = waterfall.get("end_count", 0) - waterfall.get("start_count", 0)

        numbers = {
            "start_acv": waterfall.get("start_acv", 0),
            "end_acv": waterfall.get("end_acv", 0),
            "delta_acv": delta_acv,
            "start_count": waterfall.get("start_count", 0),
            "end_count": waterfall.get("end_count", 0),
            "delta_count": delta_count,
            "new_acv": waterfall.get("new_acv", 0),
            "increases_acv": waterfall.get("increases_acv", 0),
            "decreases_acv": waterfall.get("decreases_acv", 0),
            "removed_acv": waterfall.get("removed_acv", 0),
        }

        return {
            "tool": "compare",
            "status": "success",
            "numbers": numbers,
            "dates_used": {"date_a": d_a.isoformat(), "date_b": d_b.isoformat()},
            "waterfall": waterfall,
            "link": {
                "page": "/history",
                "params": {"date_a": d_a.isoformat(), "date_b": d_b.isoformat()},
            },
        }

    # -----------------------------------------------------------------------
    # Tool 3: top_opportunities(filters, n)
    # -----------------------------------------------------------------------

    def top_opportunities(self, filters: Optional[Dict[str, Any]] = None, n: int = 10) -> Dict[str, Any]:
        """
        Get the top N opportunities ranked by Forecast ACV Amount descending.
        n is capped at 50.
        """
        if not isinstance(n, int) or n <= 0 or n > MAX_N:
            return {
                "tool": "top_opportunities",
                "status": "error",
                "error": f"Parameter 'n' must be an integer between 1 and {MAX_N} (received {n}).",
            }

        filters = filters or {}
        # Validate filter keys
        for key in filters.keys():
            if key not in WHITELIST_FIELDS and key not in ("snapshot_date", "date"):
                return {
                    "tool": "top_opportunities",
                    "status": "error",
                    "error": f"Unknown filter field: '{key}'. Whitelisted fields are: {', '.join(sorted(WHITELIST_FIELDS))}.",
                }

        # Resolve snapshot
        snap_date_str = filters.get("snapshot_date") or filters.get("date")
        if snap_date_str:
            snap_date, err = self._parse_and_validate_date(snap_date_str, "snapshot_date")
            if err:
                return {"tool": "top_opportunities", "status": "error", "error": err}
            snap = self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == snap_date).first()
        else:
            snap = self.analytics.get_active_snapshot(self.ctx)

        if not snap:
            return {"tool": "top_opportunities", "status": "error", "error": "No snapshot available."}

        opps = self.analytics._opps_for(snap, scope=self.scope, include_deleted_lost=self.include_deleted_lost)

        # Apply in-memory filters safely
        filtered_opps = []
        for o in opps:
            match = True
            if "sub_region" in filters and o.sub_region != filters["sub_region"]:
                match = False
            if "business_unit" in filters and (o.business_unit_primary != filters["business_unit"] and (filters["business_unit"] not in (o.business_unit_raw or ""))):
                match = False
            if "forecast_category" in filters and o.forecast_category != filters["forecast_category"]:
                match = False
            if "approval_status" in filters and o.approval_status != filters["approval_status"]:
                match = False
            if match:
                filtered_opps.append(o)

        filtered_opps.sort(key=lambda o: float(o.forecast_acv_amount or 0), reverse=True)
        top_slice = filtered_opps[:n]

        total_acv = sum(float(o.forecast_acv_amount or 0) for o in top_slice)
        results = [
            {
                "opportunity_id_18": o.opportunity_id_18,
                "opportunity_name": o.opportunity_name,
                "account_name": o.account_name,
                "sub_region": o.sub_region,
                "business_unit": o.business_unit_primary,
                "forecast_category": o.forecast_category,
                "approval_status": o.approval_status,
                "forecast_acv_amount": round(float(o.forecast_acv_amount or 0), 2),
            }
            for o in top_slice
        ]

        numbers = {
            "returned_count": len(results),
            "matched_total_count": len(filtered_opps),
            "top_n_total_acv": round(total_acv, 2),
        }

        # Prepare chart data for UX
        chart_data = {
            "type": "bar",
            "title": f"Top {len(results)} Opportunities by ACV",
            "items": [
                {"name": (r["opportunity_name"] or r["opportunity_id_18"])[:24], "value": r["forecast_acv_amount"], "id": r["opportunity_id_18"]}
                for r in results
            ],
        }

        link_params = {"sort_by": "forecast_acv_amount", "sort_dir": "desc"}
        for k, v in filters.items():
            if k not in ("snapshot_date", "date"):
                link_params[k] = v

        return {
            "tool": "top_opportunities",
            "status": "success",
            "numbers": numbers,
            "filters_used": filters,
            "opportunities": results,
            "chart_data": chart_data,
            "link": {
                "page": "/opportunities",
                "params": link_params,
            },
        }

    # -----------------------------------------------------------------------
    # Tool 4: movement_summary(date_a, date_b, group_by)
    # -----------------------------------------------------------------------

    def movement_summary(
        self,
        date_a: Optional[str] = None,
        date_b: Optional[str] = None,
        group_by: str = "none",
    ) -> Dict[str, Any]:
        """
        Movement and variance summary between two dates, optionally grouped by region, bu, category, or expiry_quarter.
        Identifies largest gainers and losers.
        """
        if group_by not in ALLOWED_GROUP_BY:
            return {
                "tool": "movement_summary",
                "status": "error",
                "error": f"Invalid group_by '{group_by}'. Allowed options: {', '.join(sorted(ALLOWED_GROUP_BY))}.",
            }

        def_today, def_yest = self._get_default_dates()
        d_a_str = date_a or def_yest.isoformat()
        d_b_str = date_b or def_today.isoformat()

        d_a, err_a = self._parse_and_validate_date(d_a_str, "date_a")
        if err_a:
            return {"tool": "movement_summary", "status": "error", "error": err_a}

        d_b, err_b = self._parse_and_validate_date(d_b_str, "date_b")
        if err_b:
            return {"tool": "movement_summary", "status": "error", "error": err_b}

        snap_a = self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == d_a).first()
        snap_b = self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == d_b).first()

        opps_a = {o.opportunity_id_18: o for o in self.analytics._opps_for(snap_a, scope=self.scope, include_deleted_lost=self.include_deleted_lost)}
        opps_b = {o.opportunity_id_18: o for o in self.analytics._opps_for(snap_b, scope=self.scope, include_deleted_lost=self.include_deleted_lost)}

        all_ids = set(opps_a.keys()) | set(opps_b.keys())

        # Group variances
        groups: Dict[str, Dict[str, float]] = {}

        def get_grp(o: Optional[Opportunity]) -> str:
            if not o:
                return "Unknown"
            if group_by == "region":
                return o.sub_region or "Unknown"
            elif group_by == "bu":
                return o.business_unit_primary or "Unknown"
            elif group_by == "category":
                return o.forecast_category or "Unknown"
            elif group_by == "expiry_quarter":
                return o.service_expiry_period or "Unknown"
            return "Overall"

        for oid in all_ids:
            oa = opps_a.get(oid)
            ob = opps_b.get(oid)
            grp = get_grp(ob or oa)
            if grp not in groups:
                groups[grp] = {"start_acv": 0.0, "end_acv": 0.0, "delta_acv": 0.0, "count_change": 0}

            val_a = float(oa.forecast_acv_amount or 0) if oa else 0.0
            val_b = float(ob.forecast_acv_amount or 0) if ob else 0.0

            groups[grp]["start_acv"] += val_a
            groups[grp]["end_acv"] += val_b
            groups[grp]["delta_acv"] += (val_b - val_a)
            if ob and not oa:
                groups[grp]["count_change"] += 1
            elif oa and not ob:
                groups[grp]["count_change"] -= 1

        rows = []
        for g_name, vals in groups.items():
            rows.append({
                "group": g_name,
                "start_acv": round(vals["start_acv"], 2),
                "end_acv": round(vals["end_acv"], 2),
                "delta_acv": round(vals["delta_acv"], 2),
                "count_change": vals["count_change"],
            })

        rows.sort(key=lambda r: r["delta_acv"], reverse=True)
        top_gainer = rows[0] if rows and rows[0]["delta_acv"] > 0 else None
        top_loser = rows[-1] if rows and rows[-1]["delta_acv"] < 0 else None

        # Also specifically check Commit losses if asking about Commit
        # Calculate Commit movements by group
        commit_movements: Dict[str, float] = {}
        for oid in all_ids:
            oa = opps_a.get(oid)
            ob = opps_b.get(oid)
            grp = get_grp(ob or oa)
            val_a = float(oa.forecast_acv_amount or 0) if (oa and oa.forecast_category == "Commit") else 0.0
            val_b = float(ob.forecast_acv_amount or 0) if (ob and ob.forecast_category == "Commit") else 0.0
            commit_movements[grp] = commit_movements.get(grp, 0.0) + (val_b - val_a)

        commit_rows = [{"group": k, "commit_delta": round(v, 2)} for k, v in commit_movements.items()]
        commit_rows.sort(key=lambda x: x["commit_delta"])
        top_commit_loser = commit_rows[0] if commit_rows and commit_rows[0]["commit_delta"] < 0 else None

        numbers = {
            "group_count": len(rows),
            "top_gainer": top_gainer,
            "top_loser": top_loser,
            "top_commit_loser": top_commit_loser,
        }

        target_page = "/regions" if group_by == "region" else "/business-units" if group_by == "bu" else "/pipeline"

        return {
            "tool": "movement_summary",
            "status": "success",
            "numbers": numbers,
            "group_by": group_by,
            "dates_used": {"date_a": d_a.isoformat(), "date_b": d_b.isoformat()},
            "rows": rows,
            "commit_movements": commit_rows,
            "link": {
                "page": target_page,
                "params": {"date_a": d_a.isoformat(), "date_b": d_b.isoformat()},
            },
        }

    # -----------------------------------------------------------------------
    # Tool 5: approval_breakdown(filters)
    # -----------------------------------------------------------------------

    def approval_breakdown(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Counts and ACV grouped by Approval Status (Approved, Approved - 2nd, Pending Approval, Blank, Rejected).
        """
        filters = filters or {}
        for key in filters.keys():
            if key not in WHITELIST_FIELDS and key not in ("snapshot_date", "date"):
                return {
                    "tool": "approval_breakdown",
                    "status": "error",
                    "error": f"Unknown filter field: '{key}'. Whitelisted fields: {', '.join(sorted(WHITELIST_FIELDS))}.",
                }

        snap_date_str = filters.get("snapshot_date") or filters.get("date")
        if snap_date_str:
            snap_date, err = self._parse_and_validate_date(snap_date_str, "snapshot_date")
            if err:
                return {"tool": "approval_breakdown", "status": "error", "error": err}
            snap = self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == snap_date).first()
        else:
            snap = self.analytics.get_active_snapshot(self.ctx)

        if not snap:
            return {"tool": "approval_breakdown", "status": "error", "error": "No snapshot available."}

        opps = self.analytics._opps_for(snap, scope=self.scope, include_deleted_lost=self.include_deleted_lost)

        # Apply any secondary filters
        if "sub_region" in filters:
            opps = [o for o in opps if o.sub_region == filters["sub_region"]]
        if "business_unit" in filters:
            opps = [o for o in opps if o.business_unit_primary == filters["business_unit"]]

        status_counts = {"Approved": 0, "Approved - 2nd": 0, "Pending Approval": 0, "Blank": 0, "Rejected": 0}
        status_acvs = {"Approved": 0.0, "Approved - 2nd": 0.0, "Pending Approval": 0.0, "Blank": 0.0, "Rejected": 0.0}

        for o in opps:
            st = o.approval_status or "Blank"
            if st == "Pending-Approval":
                st = "Pending Approval"
            if st not in status_counts:
                st = "Blank"
            status_counts[st] += 1
            status_acvs[st] += float(o.forecast_acv_amount or 0)

        total_cnt = sum(status_counts.values())
        total_acv = sum(status_acvs.values())

        rows = [
            {
                "status": s,
                "count": status_counts[s],
                "acv": round(status_acvs[s], 2),
                "pct_count": round(status_counts[s] / total_cnt * 100, 1) if total_cnt > 0 else 0.0,
                "pct_acv": round(status_acvs[s] / total_acv * 100, 1) if total_acv > 0 else 0.0,
            }
            for s in ["Approved", "Approved - 2nd", "Pending Approval", "Blank", "Rejected"]
        ]

        numbers = {
            "total_count": total_cnt,
            "total_acv": round(total_acv, 2),
            "pending_count": status_counts["Pending Approval"],
            "pending_acv": round(status_acvs["Pending Approval"], 2),
            "approved_count": status_counts["Approved"] + status_counts["Approved - 2nd"],
            "approved_acv": round(status_acvs["Approved"] + status_acvs["Approved - 2nd"], 2),
            "rejected_count": status_counts["Rejected"],
            "rejected_acv": round(status_acvs["Rejected"], 2),
        }

        chart_data = {
            "type": "bar",
            "title": "Opportunities by Approval Status",
            "items": [
                {"name": r["status"], "value": r["count"], "acv": r["acv"]}
                for r in rows
            ],
        }

        return {
            "tool": "approval_breakdown",
            "status": "success",
            "numbers": numbers,
            "breakdown": rows,
            "chart_data": chart_data,
            "filters_used": filters,
            "link": {
                "page": "/approvals",
                "params": filters,
            },
        }

    # -----------------------------------------------------------------------
    # Tool 6: opportunity_history(id)
    # -----------------------------------------------------------------------

    def opportunity_history(self, id: str) -> Dict[str, Any]:
        """
        Retrieve field timeline and change history across all snapshots for an opportunity ID.
        """
        if not id or not isinstance(id, str):
            return {"tool": "opportunity_history", "status": "error", "error": "Opportunity ID must be a non-empty string."}

        clean_id = id.strip()
        opp_records = (
            self.db.query(Opportunity, UploadSnapshot)
            .join(UploadSnapshot, Opportunity.snapshot_id == UploadSnapshot.id)
            .filter(Opportunity.opportunity_id_18 == clean_id)
            .order_by(UploadSnapshot.snapshot_date.asc())
            .all()
        )

        if not opp_records:
            # Try fuzzy match if partial string provided
            fuzzy = (
                self.db.query(Opportunity)
                .filter(Opportunity.opportunity_id_18.ilike(f"%{clean_id}%"))
                .first()
            )
            if fuzzy and fuzzy.opportunity_id_18:
                clean_id = fuzzy.opportunity_id_18
                opp_records = (
                    self.db.query(Opportunity, UploadSnapshot)
                    .join(UploadSnapshot, Opportunity.snapshot_id == UploadSnapshot.id)
                    .filter(Opportunity.opportunity_id_18 == clean_id)
                    .order_by(UploadSnapshot.snapshot_date.asc())
                    .all()
                )

        if not opp_records:
            return {
                "tool": "opportunity_history",
                "status": "error",
                "error": f"Opportunity ID '{id}' was not found in any snapshot.",
            }

        timeline = []
        for opp, snap in opp_records:
            timeline.append({
                "snapshot_date": snap.snapshot_date.isoformat(),
                "snapshot_label": snap.label,
                "opportunity_name": opp.opportunity_name,
                "account_name": opp.account_name,
                "forecast_acv_amount": round(float(opp.forecast_acv_amount or 0), 2),
                "forecast_category": opp.forecast_category,
                "approval_status": opp.approval_status,
                "sub_region": opp.sub_region,
                "business_unit": opp.business_unit_primary,
                "probability_pct": opp.probability_pct,
            })

        latest = timeline[-1]
        earliest = timeline[0]
        acv_change = round(latest["forecast_acv_amount"] - earliest["forecast_acv_amount"], 2)

        # Changelog entries
        changes = (
            self.db.query(ChangeLog)
            .filter(ChangeLog.opportunity_id_18 == clean_id)
            .order_by(ChangeLog.computed_at.desc())
            .all()
        )
        changelog = [
            {
                "changed_column": c.changed_column,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "computed_at": c.computed_at.isoformat() if c.computed_at else None,
            }
            for c in changes
        ]

        numbers = {
            "snapshots_present": len(timeline),
            "current_acv": latest["forecast_acv_amount"],
            "initial_acv": earliest["forecast_acv_amount"],
            "net_acv_change": acv_change,
            "current_category": latest["forecast_category"],
            "current_approval": latest["approval_status"],
        }

        # Line chart data across snapshots
        chart_data = {
            "type": "line",
            "title": f"ACV Trend: {clean_id}",
            "items": [
                {"date": t["snapshot_date"], "value": t["forecast_acv_amount"]}
                for t in timeline
            ],
        }

        return {
            "tool": "opportunity_history",
            "status": "success",
            "numbers": numbers,
            "opportunity_id_18": clean_id,
            "opportunity_name": latest["opportunity_name"],
            "account_name": latest["account_name"],
            "timeline": timeline,
            "changelog": changelog,
            "chart_data": chart_data,
            "link": {
                "page": "/opportunities",
                "params": {"search": clean_id, "opp_id": clean_id},
            },
        }

    # -----------------------------------------------------------------------
    # Tool 7: run_filtered_query(structured_filters)
    # -----------------------------------------------------------------------

    def run_filtered_query(self, structured_filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a flexible, multi-dimensional query with whitelist validation.
        Row cap 200 per call. Computes totals, counts, and returns items.
        """
        if not isinstance(structured_filters, dict):
            return {
                "tool": "run_filtered_query",
                "status": "error",
                "error": "structured_filters must be a dictionary.",
            }

        # Validate keys
        for key in structured_filters.keys():
            if key not in WHITELIST_FIELDS and key not in ("snapshot_date", "date"):
                return {
                    "tool": "run_filtered_query",
                    "status": "error",
                    "error": f"Unknown filter field: '{key}'. Whitelisted fields: {', '.join(sorted(WHITELIST_FIELDS))}.",
                }

        # Resolve snapshot
        snap_date_str = structured_filters.get("snapshot_date") or structured_filters.get("date")
        if snap_date_str:
            snap_date, err = self._parse_and_validate_date(snap_date_str, "snapshot_date")
            if err:
                return {"tool": "run_filtered_query", "status": "error", "error": err}
            snap = self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == snap_date).first()
        else:
            snap = self.analytics.get_active_snapshot(self.ctx)

        if not snap:
            return {"tool": "run_filtered_query", "status": "error", "error": "No snapshot available."}

        opps = self.analytics._opps_for(snap, scope=self.scope, include_deleted_lost=self.include_deleted_lost)

        # Apply filters
        filtered: List[Opportunity] = []
        for o in opps:
            match = True
            for k, v in structured_filters.items():
                if k in ("snapshot_date", "date"):
                    continue
                if k == "sub_region":
                    if isinstance(v, list):
                        if o.sub_region not in v:
                            match = False
                    elif o.sub_region != v:
                        match = False
                elif k == "business_unit":
                    if isinstance(v, list):
                        if o.business_unit_primary not in v and not any(bu in (o.business_unit_raw or "") for bu in v):
                            match = False
                    elif o.business_unit_primary != v and v not in (o.business_unit_raw or ""):
                        match = False
                elif k == "forecast_category":
                    if isinstance(v, list):
                        if o.forecast_category not in v:
                            match = False
                    elif o.forecast_category != v:
                        match = False
                elif k == "approval_status":
                    norm_v = [v] if isinstance(v, str) else v
                    norm_v = ["Pending Approval" if x == "Pending-Approval" else x for x in norm_v]
                    opp_norm = "Pending Approval" if o.approval_status == "Pending-Approval" else (o.approval_status or "Blank")
                    if opp_norm not in norm_v:
                        match = False
                elif k == "min_acv":
                    if float(o.forecast_acv_amount or 0) < float(v):
                        match = False
                elif k == "max_acv":
                    if float(o.forecast_acv_amount or 0) > float(v):
                        match = False
                elif k == "search":
                    s_str = str(v).lower()
                    haystack = f"{o.opportunity_name or ''} {o.account_name or ''} {o.opportunity_id_18 or ''}".lower()
                    if s_str not in haystack:
                        match = False
            if match:
                filtered.append(o)

        total_count = len(filtered)
        total_acv = sum(float(o.forecast_acv_amount or 0) for o in filtered)

        # Sort by ACV descending
        filtered.sort(key=lambda o: float(o.forecast_acv_amount or 0), reverse=True)
        capped_items = filtered[:MAX_ROW_CAP]

        items_summary = [
            {
                "opportunity_id_18": o.opportunity_id_18,
                "opportunity_name": o.opportunity_name,
                "account_name": o.account_name,
                "sub_region": o.sub_region,
                "business_unit": o.business_unit_primary,
                "forecast_category": o.forecast_category,
                "approval_status": o.approval_status,
                "forecast_acv_amount": round(float(o.forecast_acv_amount or 0), 2),
            }
            for o in capped_items
        ]

        numbers = {
            "matched_count": total_count,
            "total_acv": round(total_acv, 2),
            "returned_rows": len(items_summary),
        }

        # Dynamic link
        link_params = {k: v for k, v in structured_filters.items() if k not in ("snapshot_date", "date")}

        return {
            "tool": "run_filtered_query",
            "status": "success",
            "numbers": numbers,
            "filters_used": structured_filters,
            "items": items_summary,
            "link": {
                "page": "/opportunities",
                "params": link_params,
            },
        }
