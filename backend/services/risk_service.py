"""
RiskService — computes rule-based Deal Risk Scores (0-100) and Insights summary.
Transparent, deterministic, fully auditable.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
import pandas as pd
from sqlalchemy.orm import Session

from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot
from backend.models.change_log import ChangeLog
from backend.services.context import UserContext, ADMIN_CONTEXT


class RiskService:
    def __init__(self, db: Session):
        self.db = db

    def compute_deal_risk(
        self,
        opp: Opportunity,
        as_of_date: date | None = None,
        changelog_downgrades: set[str] | None = None,
    ) -> dict[str, Any]:
        """
        Compute transparent, rule-based risk score (0-100) and factors for an opportunity.
        All factor points sum exactly to the final score.
        """
        cat = (opp.forecast_category or "").strip()
        stage = (opp.renewal_category or "").lower()
        if cat.lower() == "closed" or "won" in stage:
            return {
                "score": 0,
                "level": "low",
                "factors": [
                    {
                        "name": "Won & Closed",
                        "points": 0,
                        "max_points": 0,
                        "description": "Opportunity is already won and closed; no renewal risk.",
                    }
                ],
                "summary": "Closed / Won deal (0 risk)",
            }

        if as_of_date is not None:
            ref_date = as_of_date
        elif getattr(opp, "snapshot_id", None):
            snap = self.db.query(UploadSnapshot).filter(UploadSnapshot.id == opp.snapshot_id).first()
            ref_date = snap.snapshot_date if (snap and snap.snapshot_date) else date.today()
        else:
            ref_date = date.today()

        factors: list[dict[str, Any]] = []

        # 1. Win Probability (0-25 pts)
        prob = opp.probability_pct
        if prob is not None and prob > 1.0:
            prob = prob / 100.0

        if prob is None or prob <= 0.20:
            p_pts = 25
            p_desc = f"Very low win probability ({f'{int(prob*100)}%' if prob is not None else 'Unset'})"
        elif prob <= 0.50:
            p_pts = 18
            p_desc = f"Low win probability ({int(prob*100)}%)"
        elif prob <= 0.70:
            p_pts = 10
            p_desc = f"Moderate win probability ({int(prob*100)}%)"
        else:
            p_pts = 0
            p_desc = f"Healthy win probability ({int(prob*100)}%)"

        factors.append({
            "name": "Probability Risk",
            "points": p_pts,
            "max_points": 25,
            "description": p_desc,
        })

        # 2. Months Delayed (0-20 pts)
        delayed = float(opp.months_delayed or 0.0)
        if delayed > 6.0:
            d_pts = 20
            d_desc = f"Severe schedule delay ({delayed:.1f} months delayed)"
        elif delayed > 3.0:
            d_pts = 14
            d_desc = f"Moderate schedule delay ({delayed:.1f} months delayed)"
        elif delayed > 0.0:
            d_pts = 8
            d_desc = f"Minor schedule delay ({delayed:.1f} months delayed)"
        else:
            d_pts = 0
            d_desc = "On schedule (no months delayed)"

        factors.append({
            "name": "Schedule Delay",
            "points": d_pts,
            "max_points": 20,
            "description": d_desc,
        })

        # 3. Approval Status (0-20 pts)
        status = (opp.approval_status or "Blank").strip()
        if status.lower() == "rejected":
            a_pts = 20
            a_desc = "Opportunity approval rejected by management"
        elif status.lower() in ("blank", ""):
            a_pts = 15
            a_desc = "Approval workflow not initiated (status is Blank)"
        elif "pending" in status.lower():
            a_pts = 10
            a_desc = "Approval decision is currently pending"
        else:
            a_pts = 0
            a_desc = f"Opportunity is approved ({status})"

        factors.append({
            "name": "Approval Status",
            "points": a_pts,
            "max_points": 20,
            "description": a_desc,
        })

        # 4. Close Date Proximity / Passed (0-15 pts)
        c_date = opp.close_date
        if c_date:
            if c_date < ref_date:
                c_pts = 15
                c_desc = f"Target close date ({c_date.isoformat()}) has passed without closing"
            elif (c_date - ref_date).days <= 30:
                days_left = (c_date - ref_date).days
                c_pts = 8
                c_desc = f"Close date is imminent ({days_left} days remaining)"
            else:
                c_pts = 0
                c_desc = f"Close date safely in future ({c_date.isoformat()})"
        else:
            c_pts = 8
            c_desc = "Target close date is unspecified"

        factors.append({
            "name": "Close Date Proximity",
            "points": c_pts,
            "max_points": 15,
            "description": c_desc,
        })

        # 5. Inactivity / Days Since Last Change (0-10 pts)
        mod_date = opp.last_modified_date
        if mod_date:
            mod_dt = mod_date.date() if isinstance(mod_date, datetime) else mod_date
            days_stale = (ref_date - mod_dt).days
            if days_stale > 60:
                s_pts = 10
                s_desc = f"Stale opportunity ({days_stale} days since last update)"
            elif days_stale > 30:
                s_pts = 5
                s_desc = f"Low recent activity ({days_stale} days since last update)"
            else:
                s_pts = 0
                s_desc = f"Recently active ({max(0, days_stale)} days since update)"
        else:
            s_pts = 5
            s_desc = "Last modified timestamp unavailable"

        factors.append({
            "name": "Activity & Staleness",
            "points": s_pts,
            "max_points": 10,
            "description": s_desc,
        })

        # 6. Forecast Category Slippage / Volatility (0-10 pts)
        is_downgraded = (
            changelog_downgrades is not None
            and opp.opportunity_id_18 in changelog_downgrades
        )
        if is_downgraded:
            v_pts = 10
            v_desc = "Downgraded from Commit across recent snapshots"
        elif cat == "Pipeline":
            acv = float(opp.forecast_acv_amount or 0)
            if acv >= 500_000:
                v_pts = 8
                v_desc = "Large renewal ACV (>$500k) remains uncommitted in Pipeline"
            else:
                v_pts = 5
                v_desc = "Early Pipeline stage (not yet in Commit or Best Case)"
        elif cat == "Best Case":
            v_pts = 3
            v_desc = "Best Case category (upside only, not firm Commit)"
        else:
            v_pts = 0
            v_desc = f"Committed forecast category ({cat})"

        factors.append({
            "name": "Forecast Volatility",
            "points": v_pts,
            "max_points": 10,
            "description": v_desc,
        })

        total_score = sum(f["points"] for f in factors)
        total_score = min(100, max(0, total_score))

        if total_score >= 65:
            level = "high"
        elif total_score >= 35:
            level = "medium"
        else:
            level = "low"

        return {
            "score": total_score,
            "level": level,
            "factors": factors,
            "summary": f"{level.capitalize()} risk score ({total_score}/100) driven by {factors[0]['name']}",
        }

    def get_insights(
        self,
        ctx: UserContext,
        snapshot_id: str | None = None,
        scope: str = "renewals",
        include_deleted_lost: bool = False,
    ) -> dict[str, Any]:
        """
        Generate full Insights payload:
        1. Top 15 at-risk deals
        2. Renewals at risk (expiring soon + unapproved or Pipeline)
        3. Commit slippage summary across available snapshots
        4. Collecting history card status
        5. Transparent model card
        """
        # Resolve snapshot
        from backend.services.analytics_service import AnalyticsService
        analytics_svc = AnalyticsService(self.db)
        snap = analytics_svc._resolve_snapshot(ctx, snapshot_id)
        if not snap:
            return {}

        opps = analytics_svc._opps_for(snap, scope=scope, include_deleted_lost=include_deleted_lost)
        as_of = snap.snapshot_date

        # Look up category downgrades from ChangeLog
        downgraded_opp_ids: set[str] = set()
        slippage_rows: list[dict[str, Any]] = []

        changes = (
            self.db.query(ChangeLog)
            .filter(ChangeLog.snapshot_to_id == snap.id)
            .all()
        )
        for ch in changes:
            field = (ch.changed_column or "").lower()
            if "forecast" in field or "category" in field:
                old_v = (ch.old_value or "").strip()
                new_v = (ch.new_value or "").strip()
                if old_v.lower() == "commit" and new_v.lower() != "commit":
                    if ch.opportunity_id_18:
                        downgraded_opp_ids.add(ch.opportunity_id_18)
                    slippage_rows.append({
                        "opportunity_id_18": ch.opportunity_id_18,
                        "opportunity_name": ch.opportunity_name,
                        "old_category": old_v,
                        "new_category": new_v,
                        "reason": f"Forecast category slipped from {old_v} to {new_v}",
                    })

        # Calculate deal risk scores
        scored_opps: list[dict[str, Any]] = []
        renewals_at_risk: list[dict[str, Any]] = []

        # Derive current quarter and next quarter dynamically from selected snapshot date
        q_num = (as_of.month - 1) // 3 + 1
        curr_q = f"Q{q_num}-{as_of.year}"
        next_q = f"Q1-{as_of.year + 1}" if q_num == 4 else f"Q{q_num + 1}-{as_of.year}"
        target_quarters = {curr_q, next_q}

        for o in opps:
            risk = self.compute_deal_risk(o, as_of_date=as_of, changelog_downgrades=downgraded_opp_ids)
            cat = (o.forecast_category or "").strip()
            status = (o.approval_status or "Blank").strip()

            deal_info = {
                "id": o.id,
                "opportunity_id_18": o.opportunity_id_18,
                "opportunity_name": o.opportunity_name,
                "account_name": o.account_name,
                "sub_region": o.sub_region,
                "business_unit": o.business_unit_raw or o.business_unit_primary,
                "forecast_category": cat,
                "forecast_acv_amount": float(o.forecast_acv_amount or 0),
                "approval_status": status,
                "probability_pct": o.probability_pct,
                "months_delayed": o.months_delayed,
                "service_expiry_period": o.service_expiry_period,
                "close_date": o.close_date.isoformat() if o.close_date else None,
                "opportunity_owner": o.opportunity_owner,
                "risk_score": risk["score"],
                "risk_level": risk["level"],
                "risk_factors": risk["factors"],
                "risk_summary": risk["summary"],
            }

            if cat.lower() != "closed":
                scored_opps.append(deal_info)

            # Check Renewals at Risk criteria:
            # Expiring soon (derived current/next quarter from selected snapshot, or close date within 90 days of snapshot)
            # AND (unapproved OR Pipeline)
            period = (o.service_expiry_period or "").strip()
            is_near_expiry = any(tq in period for tq in target_quarters) or (
                o.close_date and 0 <= (o.close_date - as_of).days <= 90
            )
            is_unapproved = status.lower() in ["blank", "pending-approval", "pending approval", "rejected"]
            is_pipeline = cat.lower() == "pipeline"

            if cat.lower() != "closed" and is_near_expiry and (is_unapproved or is_pipeline):
                renewals_at_risk.append(deal_info)

        # 1. Top 15 at-risk deals: sorted by risk_score desc, then ACV desc
        scored_opps.sort(key=lambda d: (-d["risk_score"], -d["forecast_acv_amount"]))
        top_15_at_risk = scored_opps[:15]

        # 2. Renewals at risk: sorted by ACV desc
        renewals_at_risk.sort(key=lambda d: -d["forecast_acv_amount"])

        # 3. Total snapshots count for History Card
        all_snapshots = self.db.query(UploadSnapshot).order_by(UploadSnapshot.snapshot_date.asc()).all()
        n_snaps = len(all_snapshots)

        # 4. Model Card definition
        model_card = {
            "title": "Deterministic Deal Risk Scoring Model",
            "version": "1.0.0 (Rule-Based)",
            "purpose": "Identify at-risk renewal contracts prior to service expiration.",
            "target": "Integer score from 0 (lowest risk) to 100 (highest risk). Closed/Won deals score 0.",
            "scoring_breakdown": [
                {"factor": "Probability Risk", "max_points": 25, "rule": "<=20%: 25pts, <=50%: 18pts, <=70%: 10pts, >70%: 0pts"},
                {"factor": "Schedule Delay", "max_points": 20, "rule": ">6mo: 20pts, 3-6mo: 14pts, 0-3mo: 8pts, none: 0pts"},
                {"factor": "Approval Status", "max_points": 20, "rule": "Rejected: 20pts, Blank: 15pts, Pending: 10pts, Approved: 0pts"},
                {"factor": "Close Date Proximity", "max_points": 15, "rule": "Passed: 15pts, Within 30d: 8pts, Future: 0pts"},
                {"factor": "Activity & Staleness", "max_points": 10, "rule": ">60d stale: 10pts, 30-60d: 5pts, recent: 0pts"},
                {"factor": "Forecast Volatility", "max_points": 10, "rule": "Commit slippage: 10pts, Large Pipeline: 8pts, Pipeline: 5pts, Best Case: 3pts, Commit: 0pts"},
            ],
            "limitations": [
                "Rule-based deterministic heuristic without external macroeconomic factors.",
                "Assumes historical timestamp accuracy from source SFDC data.",
                "Anomaly detection & machine learning models activate once 7 snapshots are collected.",
            ],
        }

        return {
            "snapshot_id": snap.id,
            "snapshot_date": snap.snapshot_date.isoformat(),
            "target_quarters": [curr_q, next_q],
            "top_at_risk": top_15_at_risk,
            "renewals_at_risk": renewals_at_risk[:25],
            "commit_slippage": slippage_rows,
            "history_status": {
                "available_snapshots": n_snaps,
                "target_snapshots": 7,
                "message": f"Collecting history \u2013 {n_snaps} of 7 snapshots",
                "is_collecting": n_snaps < 7,
            },
            "model_card": model_card,
        }
