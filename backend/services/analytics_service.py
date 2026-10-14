"""
AnalyticsService — all aggregation logic, powered by pandas.
All numbers in the API come from here; nothing is hard-coded.
Every method accepts user_context as first argument for future RBAC.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
from sqlalchemy.orm import Session

from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot
from backend.models.daily_summary import DailySummary
from backend.models.change_log import ChangeLog, ForecastMovementLog
from backend.services.scopes import ScopeService
from backend.services.context import UserContext
from backend.utils.normalise import (
    CANONICAL_FORECAST_CATEGORIES,
    CANONICAL_APPROVAL_STATUSES,
)

log = logging.getLogger(__name__)


def _opps_to_df(opps: list[Opportunity]) -> pd.DataFrame:
    """Convert a list of Opportunity ORM objects to a pandas DataFrame."""
    if not opps:
        return pd.DataFrame()
    records = [
        {
            "opportunity_id_18": o.opportunity_id_18,
            "opportunity_name": o.opportunity_name,
            "account_name": o.account_name,
            "sub_region": o.sub_region,
            "revised_sub_region": o.revised_sub_region,
            "country_territory": o.country_territory,
            "business_unit_primary": o.business_unit_primary,
            "business_unit_raw": o.business_unit_raw,
            "forecast_category": o.forecast_category or "Blank",
            "forecast_acv_amount": float(o.forecast_acv_amount or 0),
            "close_date": o.close_date,
            "probability_pct": o.probability_pct,
            "approval_status": o.approval_status or "Blank",
            "service_expiry_period": o.service_expiry_period,
            "closing_year": o.closing_year,
            "renewal_category": o.renewal_category,
            "months_delayed": o.months_delayed,
            "opportunity_owner": o.opportunity_owner,
        }
        for o in opps
    ]
    return pd.DataFrame(records)


EXPIRY_PIVOT_PERIODS = [
    "Q1-2026", "Q2-2026", "Q3-2026", "Q4-2026",
    "Q1-2027", "Q2-2027", "Q3-2027", "Q4-2027",
]


def filter_expiry_scope(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expiry Q3 Summary pivot scope includes only rows where:
    (a) Service Expiry Period is one of Q1-2026 .. Q4-2027
        (blank and 2025-and-earlier periods are excluded).
    (b) Forecast Category is not blank.
    """
    if df.empty:
        return df
    return df[
        df["service_expiry_period"].isin(EXPIRY_PIVOT_PERIODS) &
        df["forecast_category"].notna() &
        (df["forecast_category"].str.strip() != "") &
        (df["forecast_category"].str.lower() != "blank")
    ]


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    # Snapshot helpers
    # ------------------------------------------------------------------ #

    def get_active_snapshot(self, ctx: UserContext) -> UploadSnapshot | None:
        return (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.is_active_today == True)  # noqa: E712
            .order_by(UploadSnapshot.snapshot_date.desc())
            .first()
        )

    def get_snapshot_by_id(self, ctx: UserContext, snapshot_id: str) -> UploadSnapshot | None:
        return self.db.query(UploadSnapshot).filter(UploadSnapshot.id == snapshot_id).first()

    def get_snapshot_by_date(self, ctx: UserContext, snap_date: date) -> UploadSnapshot | None:
        return (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.snapshot_date == snap_date)
            .first()
        )

    def _resolve_snapshot(self, ctx: UserContext, snapshot_id: str | None) -> UploadSnapshot | None:
        if snapshot_id:
            return self.get_snapshot_by_id(ctx, snapshot_id)
        return self.get_active_snapshot(ctx)

    def _opps_for(
        self,
        snapshot: UploadSnapshot,
        scope: str = "all",
        include_deleted_lost: bool = True,
    ) -> list[Opportunity]:
        q = self.db.query(Opportunity).filter(Opportunity.snapshot_id == snapshot.id)

        # Exclude Deleted & Lost unless explicitly requested
        if not include_deleted_lost:
            q = q.filter(Opportunity.is_deleted_or_lost == False)

        # Filter by scope
        s = (scope or "renewals").lower()
        if s == "renewals":
            q = q.filter(ScopeService.is_renewals())
        elif s == "fy2026":
            q = q.filter(ScopeService.is_renewals(), Opportunity.fiscal_period.in_(["Q1-2026", "Q2-2026", "Q3-2026", "Q4-2026"]))
        elif s == "fy2027":
            q = q.filter(ScopeService.is_renewals(), Opportunity.fiscal_period.in_(["Q1-2027", "Q2-2027", "Q3-2027", "Q4-2027"]))
        elif s == "q4_2026":
            q = q.filter(ScopeService.current_quarter_slice(ScopeService.current_quarter(snapshot.snapshot_date)))
        elif s == "all":
            pass

        return q.all()

    def is_scope_available(self, snapshot_id: str, scope: str) -> bool:
        s = (scope or "renewals").lower()
        if s in ("all", "renewals"):
            return True
        col = getattr(Opportunity, f"in_{s}", None)
        if col is not None:
            has_val = (
                self.db.query(Opportunity.id)
                .filter(Opportunity.snapshot_id == snapshot_id, col.isnot(None))
                .first()
            )
            return has_val is not None
        return True

    def _get_adjacent_snapshot(
        self, snapshot: UploadSnapshot, days_back: int = 1
    ) -> UploadSnapshot | None:
        """
        Return the snapshot corresponding to yesterday or last week.
        Never substitute an arbitrary older snapshot for yesterday.
        """
        if days_back == 1:
            if getattr(snapshot, "yesterday_date", None):
                y_snap = self.get_snapshot_by_date(UserContext(), snapshot.yesterday_date)
                if y_snap:
                    return y_snap
            target_date = snapshot.snapshot_date - timedelta(days=1)
            snap = self.get_snapshot_by_date(UserContext(), target_date)
            return snap

        if days_back == 7:
            target_date = snapshot.snapshot_date - timedelta(days=7)
            snap = self.get_snapshot_by_date(UserContext(), target_date)
            return snap

        target_date = snapshot.snapshot_date - timedelta(days=days_back)
        snap = self.get_snapshot_by_date(UserContext(), target_date)
        if snap:
            return snap
        return (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.snapshot_date <= target_date)
            .order_by(UploadSnapshot.snapshot_date.desc())
            .first()
        )

    # ------------------------------------------------------------------ #
    # KPIs
    # ------------------------------------------------------------------ #

    def get_kpis(
        self,
        ctx: UserContext,
        snapshot_id: str | None = None,
        scope: str = "all",
        include_deleted_lost: bool = True,
    ) -> dict:
        snap = self._resolve_snapshot(ctx, snapshot_id)
        if snap is None:
            return {}

        opps = self._opps_for(snap, scope=scope, include_deleted_lost=include_deleted_lost)
        df = _opps_to_df(opps)

        total_acv    = df["forecast_acv_amount"].sum() if not df.empty else 0.0
        total_count  = len(df)
        weighted_acv = (
            (df["forecast_acv_amount"] * df["probability_pct"].fillna(0) / 100).sum()
            if not df.empty else 0.0
        )
        commit_acv = df[df["forecast_category"] == "Commit"]["forecast_acv_amount"].sum() if not df.empty else 0.0
        closed_acv = df[df["forecast_category"] == "Closed"]["forecast_acv_amount"].sum() if not df.empty else 0.0

        # Expiry scope KPIs (scoped to Expiry Q3 Summary rule)
        exp_df = filter_expiry_scope(df)
        expiry_scope_acv = round(float(exp_df["forecast_acv_amount"].sum()), 2) if not exp_df.empty else 0.0
        expiry_scope_count = len(exp_df)

        # Compute deltas vs yesterday snapshot
        delta_acv = delta_count = delta_commit_acv = None
        expiry_scope_delta_acv = expiry_scope_delta_count = None
        yest_snap = self._get_adjacent_snapshot(snap, days_back=1)
        compare_label = None
        days_between = 1
        is_monday = False

        if yest_snap:
            days_between = max(1, (snap.snapshot_date - yest_snap.snapshot_date).days)
            is_monday = bool(snap.snapshot_date.weekday() == 0 and days_between == 3)
            compare_label = f"vs {yest_snap.snapshot_date.strftime('%a %d %b')}"

            yest_opps = self._opps_for(yest_snap, scope=scope, include_deleted_lost=include_deleted_lost)
            yest_df   = _opps_to_df(yest_opps)
            yest_acv  = yest_df["forecast_acv_amount"].sum() if not yest_df.empty else 0.0
            yest_commit = yest_df[yest_df["forecast_category"] == "Commit"]["forecast_acv_amount"].sum() if not yest_df.empty else 0.0
            delta_acv        = round(total_acv - yest_acv, 2)
            delta_count      = total_count - len(yest_df)
            delta_commit_acv = round(commit_acv - yest_commit, 2)

            yest_exp_df = filter_expiry_scope(yest_df)
            yest_exp_acv = float(yest_exp_df["forecast_acv_amount"].sum()) if not yest_exp_df.empty else 0.0
            expiry_scope_delta_acv = round(expiry_scope_acv - yest_exp_acv, 2)
            expiry_scope_delta_count = expiry_scope_count - len(yest_exp_df)

        return {
            "snapshot_id":      snap.id,
            "snapshot_date":    snap.snapshot_date.isoformat(),
            "yesterday_date":   yest_snap.snapshot_date.isoformat() if yest_snap else None,
            "compare_label":    compare_label,
            "is_monday_comparison": is_monday,
            "days_between":     days_between,
            "scope":            scope,
            "include_deleted_lost": include_deleted_lost,
            "label":            snap.label,
            "total_acv":        round(total_acv, 2),
            "total_count":      total_count,
            "weighted_acv":     round(weighted_acv, 2),
            "commit_acv":       round(commit_acv, 2),
            "closed_acv":       round(closed_acv, 2),
            # Deltas vs yesterday (None if no yesterday snapshot)
            "delta_acv":        delta_acv,
            "delta_count":      delta_count,
            "delta_commit_acv": delta_commit_acv,
            # Expiry scope KPIs
            "expiry_scope_acv": expiry_scope_acv,
            "expiry_scope_count": expiry_scope_count,
            "expiry_scope_delta_acv": expiry_scope_delta_acv,
            "expiry_scope_delta_count": expiry_scope_delta_count,
        }

    # ------------------------------------------------------------------ #
    # Forecast summary (expiry × category pivot)
    # ------------------------------------------------------------------ #

    def get_forecast_summary(
        self,
        ctx: UserContext,
        snapshot_id: str | None = None,
        compare_to: str | None = None,
        scope: str = "all",
        include_deleted_lost: bool = True,
    ) -> dict:
        snap = self._resolve_snapshot(ctx, snapshot_id)
        if snap is None:
            return {}

        # Resolve comparison snapshot
        comp_snap = None
        if compare_to:
            comp_snap = self.get_snapshot_by_id(ctx, compare_to)
        else:
            comp_snap = self._get_adjacent_snapshot(snap, days_back=1)

        lw_snap = self._get_adjacent_snapshot(snap, days_back=7)

        today_df = filter_expiry_scope(_opps_to_df(self._opps_for(snap, scope=scope, include_deleted_lost=include_deleted_lost)))
        yest_df = filter_expiry_scope(_opps_to_df(self._opps_for(comp_snap, scope=scope, include_deleted_lost=include_deleted_lost))) if comp_snap else pd.DataFrame()
        lw_df = filter_expiry_scope(_opps_to_df(self._opps_for(lw_snap, scope=scope, include_deleted_lost=include_deleted_lost))) if lw_snap else pd.DataFrame()

        categories = [c for c in CANONICAL_FORECAST_CATEGORIES if c != "Blank"]

        def get_cell_map(df: pd.DataFrame):
            cm = {}
            if not df.empty:
                for (p, c), grp in df.groupby(["service_expiry_period", "forecast_category"]):
                    cm[(p, c)] = {
                        "acv": round(float(grp["forecast_acv_amount"].sum()), 2),
                        "count": int(grp["opportunity_id_18"].count()),
                    }
            return cm

        t_map = get_cell_map(today_df)
        y_map = get_cell_map(yest_df)
        lw_map = get_cell_map(lw_df)

        def get_quarter_map(df: pd.DataFrame):
            qm = {}
            if not df.empty:
                for p, grp in df.groupby("service_expiry_period"):
                    qm[p] = {
                        "acv": round(float(grp["forecast_acv_amount"].sum()), 2),
                        "count": int(grp["opportunity_id_18"].count()),
                    }
            return qm

        t_qmap = get_quarter_map(today_df)
        y_qmap = get_quarter_map(yest_df)
        lw_qmap = get_quarter_map(lw_df)

        # Union of all cells across periods and canonical categories
        all_cells = sorted(set(
            [(p, c) for p in EXPIRY_PIVOT_PERIODS for c in categories] +
            list(t_map.keys()) + list(y_map.keys()) + list(lw_map.keys())
        ))

        today_records = []
        yesterday_records = []
        lastweek_records = []
        by_cell = {}

        for p, c in all_cells:
            t_data = t_map.get((p, c), {"acv": 0.0, "count": 0})
            y_data = y_map.get((p, c), {"acv": 0.0, "count": 0})
            lw_data = lw_map.get((p, c), {"acv": 0.0, "count": 0})

            today_records.append({
                "service_expiry_period": p,
                "forecast_category": c,
                "acv": t_data["acv"],
                "count": t_data["count"],
            })
            yesterday_records.append({
                "service_expiry_period": p,
                "forecast_category": c,
                "acv": y_data["acv"],
                "count": y_data["count"],
            })
            lastweek_records.append({
                "service_expiry_period": p,
                "forecast_category": c,
                "acv": lw_data["acv"],
                "count": lw_data["count"],
            })

            cell_info = {
                "period": p,
                "category": c,
                "today": t_data,
                "yesterday": y_data,
                "lastweek": lw_data,
                "delta_vs_yesterday": {
                    "acv": round(t_data["acv"] - y_data["acv"], 2),
                    "count": t_data["count"] - y_data["count"],
                },
                "delta_vs_lastweek": {
                    "acv": round(t_data["acv"] - lw_data["acv"], 2),
                    "count": t_data["count"] - lw_data["count"],
                },
            }
            by_cell[f"{p}|{c}"] = cell_info
            # NOTE: tuple key (p, c) removed — FastAPI JSON encoder cannot serialize tuple keys

        # By quarter totals and deltas
        by_quarter = {}
        for p in EXPIRY_PIVOT_PERIODS:
            t_q = t_qmap.get(p, {"acv": 0.0, "count": 0})
            y_q = y_qmap.get(p, {"acv": 0.0, "count": 0})
            lw_q = lw_qmap.get(p, {"acv": 0.0, "count": 0})
            by_quarter[p] = {
                "today": t_q,
                "yesterday": y_q,
                "lastweek": lw_q,
                "delta_vs_yesterday": {
                    "acv": round(t_q["acv"] - y_q["acv"], 2),
                    "count": t_q["count"] - y_q["count"],
                },
                "delta_vs_lastweek": {
                    "acv": round(t_q["acv"] - lw_q["acv"], 2),
                    "count": t_q["count"] - lw_q["count"],
                },
            }

        t_acv = round(float(today_df["forecast_acv_amount"].sum()), 2) if not today_df.empty else 0.0
        t_cnt = len(today_df)

        y_acv = round(float(yest_df["forecast_acv_amount"].sum()), 2) if not yest_df.empty else 0.0
        y_cnt = len(yest_df)

        lw_acv = round(float(lw_df["forecast_acv_amount"].sum()), 2) if not lw_df.empty else 0.0
        lw_cnt = len(lw_df)

        delta_ty_acv = round(t_acv - y_acv, 2) if not yest_df.empty else None
        delta_ty_cnt = t_cnt - y_cnt if not yest_df.empty else None

        delta_tlw_acv = round(t_acv - lw_acv, 2) if not lw_df.empty else None
        delta_tlw_cnt = t_cnt - lw_cnt if not lw_df.empty else None

        return {
            "today": today_records,
            "yesterday": yesterday_records,
            "lastweek": lastweek_records,
            "categories": categories,
            "by_cell": by_cell,
            "by_quarter": by_quarter,
            "totals": {
                "today": {"acv": t_acv, "count": t_cnt},
                "yesterday": {"acv": y_acv, "count": y_cnt},
                "lastweek": {"acv": lw_acv, "count": lw_cnt},
                "delta_vs_yesterday": {"acv": delta_ty_acv, "count": delta_ty_cnt},
                "delta_vs_lastweek": {"acv": delta_tlw_acv, "count": delta_tlw_cnt},
            },
        }



    # ------------------------------------------------------------------ #
    # Approval status
    # ------------------------------------------------------------------ #

    def get_approval_status(
        self,
        ctx: UserContext,
        snapshot_id: str | None = None,
        compare_to: str | None = None,
        scope: str = "all",
        include_deleted_lost: bool = True,
    ) -> dict:
        snap = self._resolve_snapshot(ctx, snapshot_id)
        if snap is None:
            return {}

        opps = self._opps_for(snap, scope=scope, include_deleted_lost=include_deleted_lost)
        df = _opps_to_df(opps)
        if df.empty:
            return {"rows": [], "total_count": 0, "total_acv": 0.0, "history_trend": [], "changes": {}}

        total_count = len(df)
        total_acv = round(float(df["forecast_acv_amount"].sum()), 2)

        def norm_status(s: str | None) -> str:
            if not s or s == "Blank":
                return "Blank"
            if s in ["Pending-Approval", "Pending Approval"]:
                return "Pending-Approval"
            return s

        df["norm_status"] = df["approval_status"].apply(norm_status)
        canonical_statuses = ["Approved", "Approved - 2nd", "Pending-Approval", "Blank", "Rejected"]
        status_map = {s: {"count": 0, "acv": 0.0} for s in canonical_statuses}

        for s, grp in df.groupby("norm_status"):
            st = s if s in status_map else "Blank"
            status_map[st]["count"] = int(grp["opportunity_id_18"].count())
            status_map[st]["acv"] = round(float(grp["forecast_acv_amount"].sum()), 2)

        rows = []
        for s in canonical_statuses:
            c = status_map[s]["count"]
            a = status_map[s]["acv"]
            rows.append({
                "approval_status": s,
                "count": c,
                "acv": a,
                "pct_count": round(c / total_count * 100, 1) if total_count else 0.0,
                "pct_acv": round(a / total_acv * 100, 1) if total_acv else 0.0,
            })

        # Ensure total_acv is exactly the sum of the 5 statuses down to the cent
        total_acv = round(sum(r["acv"] for r in rows), 2)
        for r in rows:
            r["pct_acv"] = round(r["acv"] / total_acv * 100, 1) if total_acv else 0.0

        # History trend across all snapshots
        all_snaps = (
            self.db.query(UploadSnapshot)
            .order_by(UploadSnapshot.snapshot_date.asc())
            .all()
        )
        history_trend = []
        for s_item in all_snaps:
            scope_avail = self.is_scope_available(s_item.id, scope)
            if not scope_avail:
                history_trend.append({
                    "snapshot_id": s_item.id,
                    "snapshot_date": s_item.snapshot_date.isoformat(),
                    "label": s_item.label,
                    "counts": None,
                    "acv": None,
                    "total_count": None,
                    "total_acv": None,
                    "scope_available": False,
                })
                continue

            s_opps = self._opps_for(s_item, scope=scope, include_deleted_lost=include_deleted_lost)
            s_df = _opps_to_df(s_opps)
            s_counts = {st: 0 for st in canonical_statuses}
            s_acv = {st: 0.0 for st in canonical_statuses}
            if not s_df.empty:
                s_df["norm_st"] = s_df["approval_status"].apply(norm_status)
                for st, grp in s_df.groupby("norm_st"):
                    st_key = st if st in s_counts else "Blank"
                    s_counts[st_key] += int(grp["opportunity_id_18"].count())
                    s_acv[st_key] = round(s_acv[st_key] + float(grp["forecast_acv_amount"].sum()), 2)

            history_trend.append({
                "snapshot_id": s_item.id,
                "snapshot_date": s_item.snapshot_date.isoformat(),
                "label": s_item.label,
                "counts": s_counts,
                "acv": s_acv,
                "total_count": len(s_df),
                "total_acv": round(float(s_df["forecast_acv_amount"].sum()), 2) if not s_df.empty else 0.0,
                "scope_available": True,
            })

        collecting_history = len(all_snaps) < 7
        history_note = (
            f"Collecting history ({len(all_snaps)} of 7 snapshots available)"
            if collecting_history else None
        )

        # Changes vs compare snapshot (or adjacent yesterday)
        comp_snap = None
        if compare_to:
            comp_snap = self.get_snapshot_by_id(ctx, compare_to)
        if not comp_snap:
            comp_snap = self._get_adjacent_snapshot(snap, days_back=1)

        newly_approved = []
        newly_pending = []
        newly_rejected = []

        if comp_snap:
            comp_opps = self._opps_for(comp_snap, scope=scope, include_deleted_lost=include_deleted_lost)
            comp_map = {o.opportunity_id_18: o for o in comp_opps}

            for o in opps:
                curr_st = norm_status(o.approval_status)
                prev_o = comp_map.get(o.opportunity_id_18)
                prev_st = norm_status(prev_o.approval_status) if prev_o else None

                item_info = {
                    "opportunity_id_18": o.opportunity_id_18,
                    "opportunity_name": o.opportunity_name,
                    "account_name": o.account_name,
                    "forecast_acv_amount": float(o.forecast_acv_amount or 0),
                    "forecast_category": o.forecast_category,
                    "business_unit_primary": o.business_unit_primary,
                    "service_expiry_period": o.service_expiry_period,
                    "old_status": prev_st or "New Deal",
                    "new_status": curr_st,
                }

                # Newly approved: currently Approved or Approved - 2nd, but previously wasn't (or brand new)
                if curr_st in ["Approved", "Approved - 2nd"]:
                    if prev_st not in ["Approved", "Approved - 2nd"]:
                        newly_approved.append(item_info)

                # Newly pending: currently Pending-Approval, but previously wasn't
                if curr_st == "Pending-Approval":
                    if prev_st != "Pending-Approval":
                        newly_pending.append(item_info)

                # Newly rejected: currently Rejected, but previously wasn't
                if curr_st == "Rejected":
                    if prev_st != "Rejected":
                        newly_rejected.append(item_info)

        changes = {
            "newly_approved": newly_approved,
            "newly_pending": newly_pending,
            "newly_rejected": newly_rejected,
            "newly_approved_count": len(newly_approved),
            "newly_pending_count": len(newly_pending),
            "newly_rejected_count": len(newly_rejected),
            "compare_date": comp_snap.snapshot_date.isoformat() if comp_snap else None,
        }

        return {
            "rows": rows,
            "total_count": total_count,
            "total_acv": total_acv,
            "history_trend": history_trend,
            "collecting_history": collecting_history,
            "history_note": history_note,
            "changes": changes,
        }

    # ------------------------------------------------------------------ #
    # Approval status × Business Unit
    # ------------------------------------------------------------------
    def get_approval_by_bu(
        self,
        ctx: UserContext,
        snapshot_id: str | None = None,
        mode: str = "as_in_excel",
        scope: str = "all",
        include_deleted_lost: bool = True,
    ) -> dict:
        snap = self._resolve_snapshot(ctx, snapshot_id)
        if snap is None:
            return {}

        opps = self._opps_for(snap, scope=scope, include_deleted_lost=include_deleted_lost)
        if not opps:
            return {"rows": [], "total": {}, "mode": mode}

        from backend.utils.normalise import split_business_units

        def norm_status(s: str | None) -> str:
            if not s or s == "Blank":
                return "Blank"
            if s in ["Pending-Approval", "Pending Approval"]:
                return "Pending-Approval"
            return s

        def compute_table(row_list: list[dict]) -> list[dict]:
            df_in = pd.DataFrame(row_list)
            result_rows = []
            for bu, grp in df_in.groupby("bu"):
                tot_c = len(grp)
                tot_a = round(float(grp["acv"].sum()), 2)
                st_counts = grp["status"].value_counts().to_dict()

                app = st_counts.get("Approved", 0)
                app2 = st_counts.get("Approved - 2nd", 0)
                pend = st_counts.get("Pending-Approval", 0)
                blank = st_counts.get("Blank", 0)
                rej = st_counts.get("Rejected", 0)

                result_rows.append({
                    "business_unit": bu,
                    "total_count": tot_c,
                    "acv": tot_a,
                    "approved_count": app,
                    "approved_2nd_count": app2,
                    "pending_count": pend,
                    "blank_count": blank,
                    "rejected_count": rej,
                    "mix": {
                        "Approved": round(app / tot_c * 100, 1) if tot_c else 0.0,
                        "Approved - 2nd": round(app2 / tot_c * 100, 1) if tot_c else 0.0,
                        "Pending-Approval": round(pend / tot_c * 100, 1) if tot_c else 0.0,
                        "Blank": round(blank / tot_c * 100, 1) if tot_c else 0.0,
                        "Rejected": round(rej / tot_c * 100, 1) if tot_c else 0.0,
                    }
                })
            result_rows.sort(key=lambda r: r["total_count"], reverse=True)
            return result_rows

        # 1. As in Excel rows (exact raw string, 16 rows)
        excel_raw_rows = [
            {
                "bu": o.business_unit_raw or "Unknown",
                "status": norm_status(o.approval_status),
                "acv": float(o.forecast_acv_amount or 0),
            }
            for o in opps
        ]
        excel_table = compute_table(excel_raw_rows)
        excel_table.sort(key=lambda r: r["business_unit"].lower())

        # 2. Split rows (multi-BU counted under each BU)
        split_raw_rows = []
        for o in opps:
            bus = split_business_units(o.business_unit_raw) or ["Unknown"]
            for bu in bus:
                split_raw_rows.append({
                    "bu": bu,
                    "status": norm_status(o.approval_status),
                    "acv": float(o.forecast_acv_amount or 0),
                })
        split_table = compute_table(split_raw_rows)

        # Overall total row
        tot_c = len(opps)
        tot_a = round(sum(r["acv"] for r in excel_table), 2)
        all_statuses = [norm_status(o.approval_status) for o in opps]
        tot_app = sum(1 for s in all_statuses if s == "Approved")
        tot_app2 = sum(1 for s in all_statuses if s == "Approved - 2nd")
        tot_pend = sum(1 for s in all_statuses if s == "Pending-Approval")
        tot_blank = sum(1 for s in all_statuses if s == "Blank")
        tot_rej = sum(1 for s in all_statuses if s == "Rejected")

        total_row = {
            "business_unit": "Total",
            "total_count": tot_c,
            "acv": tot_a,
            "approved_count": tot_app,
            "approved_2nd_count": tot_app2,
            "pending_count": tot_pend,
            "blank_count": tot_blank,
            "rejected_count": tot_rej,
            "mix": {
                "Approved": round(tot_app / tot_c * 100, 1) if tot_c else 0.0,
                "Approved - 2nd": round(tot_app2 / tot_c * 100, 1) if tot_c else 0.0,
                "Pending-Approval": round(tot_pend / tot_c * 100, 1) if tot_c else 0.0,
                "Blank": round(tot_blank / tot_c * 100, 1) if tot_c else 0.0,
                "Rejected": round(tot_rej / tot_c * 100, 1) if tot_c else 0.0,
            }
        }

        active_rows = split_table if mode == "split" else excel_table

        return {
            "mode": mode,
            "rows": active_rows,
            "total": total_row,
            "as_in_excel_rows": excel_table,
            "split_rows": split_table,
            "statuses": ["Approved", "Approved - 2nd", "Pending-Approval", "Blank", "Rejected"],
        }

    # ------------------------------------------------------------------ #
    # Top regions
    # ------------------------------------------------------------------ #

    def get_top_regions(
        self,
        ctx: UserContext,
        snapshot_id: str | None = None,
        top_n: int = 10,
        scope: str = "all",
        include_deleted_lost: bool = True,
    ) -> dict:
        snap = self._resolve_snapshot(ctx, snapshot_id)
        if snap is None:
            return {}
        df = _opps_to_df(self._opps_for(snap, scope=scope, include_deleted_lost=include_deleted_lost))
        if df.empty:
            return {"rows": []}

        grouped = (
            df.groupby("sub_region")
            .agg(count=("opportunity_id_18", "count"), acv=("forecast_acv_amount", "sum"))
            .reset_index()
            .sort_values("acv", ascending=False)
            .head(top_n)
        )
        return {"rows": grouped.to_dict(orient="records")}

    # ------------------------------------------------------------------ #
    # Top regions × BU
    # ------------------------------------------------------------------ #

    def get_top_regions_bu(
        self,
        ctx: UserContext,
        snapshot_id: str | None = None,
        top_n: int = 10,
        scope: str = "all",
        include_deleted_lost: bool = True,
    ) -> dict:
        snap = self._resolve_snapshot(ctx, snapshot_id)
        if snap is None:
            return {}

        from backend.utils.normalise import split_business_units
        opps = self._opps_for(snap, scope=scope, include_deleted_lost=include_deleted_lost)
        rows = []
        for o in opps:
            bus = split_business_units(o.business_unit_raw) or ["Unknown"]
            for bu in bus:
                rows.append({
                    "sub_region": o.sub_region or "Unknown",
                    "business_unit": bu,
                    "forecast_acv_amount": float(o.forecast_acv_amount or 0),
                })
        if not rows:
            return {"rows": []}

        df = pd.DataFrame(rows)
        # Get top N regions by total ACV
        top_regions = (
            df.groupby("sub_region")["forecast_acv_amount"]
            .sum()
            .sort_values(ascending=False)
            .head(top_n)
            .index.tolist()
        )
        df_filtered = df[df["sub_region"].isin(top_regions)]
        grouped = (
            df_filtered.groupby(["sub_region", "business_unit"])
            .agg(acv=("forecast_acv_amount", "sum"))
            .reset_index()
        )
        return {"rows": grouped.to_dict(orient="records"), "top_regions": top_regions}

    # ------------------------------------------------------------------ #
    # Forecast movement (for Sankey)
    # ------------------------------------------------------------------ #

    def get_forecast_movement(
        self, ctx: UserContext, snapshot_id: str | None = None, compare_to: str | None = None
    ) -> dict:
        snap = self._resolve_snapshot(ctx, snapshot_id)
        if snap is None:
            return {"links": []}

        comp_snap = None
        if compare_to:
            comp_snap = self.get_snapshot_by_id(ctx, compare_to)
        else:
            comp_snap = self._get_adjacent_snapshot(snap, days_back=1)

        if comp_snap is None:
            return {"links": []}

        movements = (
            self.db.query(ForecastMovementLog)
            .filter(
                ForecastMovementLog.snapshot_from_id == comp_snap.id,
                ForecastMovementLog.snapshot_to_id == snap.id,
            )
            .all()
        )
        return {
            "links": [
                {
                    "from": m.from_category,
                    "to": m.to_category,
                    "count": m.opportunity_count,
                    "acv": float(m.acv_total),
                }
                for m in movements
            ]
        }

    # ------------------------------------------------------------------ #
    # ACV changes summary
    # ------------------------------------------------------------------ #

    def get_acv_changes(
        self, ctx: UserContext, snapshot_id: str | None = None, compare_to: str | None = None
    ) -> dict:
        snap = self._resolve_snapshot(ctx, snapshot_id)
        if snap is None:
            return {"rows": []}

        comp_snap = None
        if compare_to:
            comp_snap = self.get_snapshot_by_id(ctx, compare_to)
        else:
            comp_snap = self._get_adjacent_snapshot(snap, days_back=1)

        if comp_snap is None:
            return {"rows": []}

        changes = (
            self.db.query(ChangeLog)
            .filter(
                ChangeLog.snapshot_from_id == comp_snap.id,
                ChangeLog.snapshot_to_id == snap.id,
                ChangeLog.change_type == "ACV Change",
            )
            .limit(200)
            .all()
        )
        return {
            "rows": [
                {
                    "opportunity_id_18": c.opportunity_id_18,
                    "opportunity_name": c.opportunity_name,
                    "old_value": c.old_value,
                    "new_value": c.new_value,
                    "change_type": c.change_type,
                }
                for c in changes
            ]
        }

    # ------------------------------------------------------------------ #
    # Expiry quarters
    # ------------------------------------------------------------------ #

    def get_expiry_quarters(
        self,
        ctx: UserContext,
        snapshot_id: str | None = None,
        scope: str = "all",
        include_deleted_lost: bool = True,
    ) -> dict:
        snap = self._resolve_snapshot(ctx, snapshot_id)
        if snap is None:
            return {"rows": [], "total_count": 0, "total_acv": 0.0, "by_quarter": {}}

        df = _opps_to_df(self._opps_for(snap, scope=scope, include_deleted_lost=include_deleted_lost))
        if df.empty:
            return {"rows": [], "total_count": 0, "total_acv": 0.0, "by_quarter": {}}

        # Apply Expiry Q3 Summary pivot scope
        df = filter_expiry_scope(df)

        grouped = (
            df.groupby(["service_expiry_period", "forecast_category"])
            .agg(acv=("forecast_acv_amount", "sum"), count=("opportunity_id_18", "count"))
            .reset_index()
        )
        quarter_grouped = (
            df.groupby("service_expiry_period")
            .agg(acv=("forecast_acv_amount", "sum"), count=("opportunity_id_18", "count"))
            .reset_index()
        )
        by_quarter = {
            r["service_expiry_period"]: {
                "acv": round(float(r["acv"]), 2),
                "count": int(r["count"]),
            }
            for _, r in quarter_grouped.iterrows()
        }
        return {
            "rows": grouped.to_dict(orient="records"),
            "total_count": int(len(df)),
            "total_acv": round(float(df["forecast_acv_amount"].sum()), 2),
            "by_quarter": by_quarter,
        }

    # ------------------------------------------------------------------ #
    # Closing year trend
    # ------------------------------------------------------------------ #

    def get_closing_year_trend(
        self,
        ctx: UserContext,
        snapshot_id: str | None = None,
        scope: str = "all",
        include_deleted_lost: bool = True,
    ) -> dict:
        snap = self._resolve_snapshot(ctx, snapshot_id)
        if snap is None:
            return {"rows": []}
        df = _opps_to_df(self._opps_for(snap, scope=scope, include_deleted_lost=include_deleted_lost))
        if df.empty:
            return {"rows": []}

        df = df[df["closing_year"].notna()]
        grouped = (
            df.groupby(["closing_year", "forecast_category"])
            .agg(acv=("forecast_acv_amount", "sum"), count=("opportunity_id_18", "count"))
            .reset_index()
        )
        return {"rows": grouped.to_dict(orient="records")}

    # ------------------------------------------------------------------ #
    # Trend sparklines (from daily_summary cache)
    # ------------------------------------------------------------------ #

    def get_trend_sparklines(
        self, ctx: UserContext, metric: str = "total_acv", days: int = 30
    ) -> dict:
        cutoff = date.today() - timedelta(days=days)
        rows = (
            self.db.query(DailySummary)
            .filter(
                DailySummary.metric == metric,
                DailySummary.dimension == "overall",
                DailySummary.snapshot_date >= cutoff,
            )
            .order_by(DailySummary.snapshot_date)
            .all()
        )
        return {
            "metric": metric,
            "points": [
                {"date": r.snapshot_date.isoformat(), "value": float(r.value), "count": r.count}
                for r in rows
            ],
        }

    # ------------------------------------------------------------------ #
    # Compare two dates
    # ------------------------------------------------------------------ #

    def get_comparison(
        self,
        ctx: UserContext,
        from_date: date,
        to_date: date,
        scope: str = "all",
        include_deleted_lost: bool = True,
    ) -> dict:
        from_snap = self.get_snapshot_by_date(ctx, from_date)
        to_snap = self.get_snapshot_by_date(ctx, to_date)
        if not from_snap or not to_snap:
            return {
                "error": f"One or both snapshots not found for dates {from_date} and {to_date}",
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "from_found": from_snap is not None,
                "to_found": to_snap is not None,
            }

        from_opps = self._opps_for(from_snap, scope=scope, include_deleted_lost=include_deleted_lost)
        to_opps = self._opps_for(to_snap, scope=scope, include_deleted_lost=include_deleted_lost)
        from_df = _opps_to_df(from_opps)
        to_df = _opps_to_df(to_opps)

        from_total_acv = float(from_df["forecast_acv_amount"].sum()) if not from_df.empty else 0.0
        to_total_acv = float(to_df["forecast_acv_amount"].sum()) if not to_df.empty else 0.0
        from_total_count = len(from_df)
        to_total_count = len(to_df)

        # 1. Forecast category comparison
        fc_list = []
        all_fc = list(dict.fromkeys(CANONICAL_FORECAST_CATEGORIES + 
            (list(from_df["forecast_category"].unique()) if not from_df.empty else []) +
            (list(to_df["forecast_category"].unique()) if not to_df.empty else [])))
        for fc in all_fc:
            f_sub = from_df[from_df["forecast_category"] == fc] if not from_df.empty else pd.DataFrame()
            t_sub = to_df[to_df["forecast_category"] == fc] if not to_df.empty else pd.DataFrame()
            f_cnt = len(f_sub)
            t_cnt = len(t_sub)
            f_acv = float(f_sub["forecast_acv_amount"].sum()) if not f_sub.empty else 0.0
            t_acv = float(t_sub["forecast_acv_amount"].sum()) if not t_sub.empty else 0.0
            fc_list.append({
                "category": fc,
                "from_count": f_cnt,
                "to_count": t_cnt,
                "count_diff": t_cnt - f_cnt,
                "from_acv": round(f_acv, 2),
                "to_acv": round(t_acv, 2),
                "acv_diff": round(t_acv - f_acv, 2),
            })

        # 2. Approval status comparison
        appr_list = []
        all_appr = list(dict.fromkeys(CANONICAL_APPROVAL_STATUSES +
            (list(from_df["approval_status"].unique()) if not from_df.empty else []) +
            (list(to_df["approval_status"].unique()) if not to_df.empty else [])))
        for st in all_appr:
            f_sub = from_df[from_df["approval_status"] == st] if not from_df.empty else pd.DataFrame()
            t_sub = to_df[to_df["approval_status"] == st] if not to_df.empty else pd.DataFrame()
            f_cnt = len(f_sub)
            t_cnt = len(t_sub)
            f_acv = float(f_sub["forecast_acv_amount"].sum()) if not f_sub.empty else 0.0
            t_acv = float(t_sub["forecast_acv_amount"].sum()) if not t_sub.empty else 0.0
            appr_list.append({
                "status": st,
                "from_count": f_cnt,
                "to_count": t_cnt,
                "count_diff": t_cnt - f_cnt,
                "from_acv": round(f_acv, 2),
                "to_acv": round(t_acv, 2),
                "acv_diff": round(t_acv - f_acv, 2),
            })

        # 3. Expiry pivot comparison (scoped to Expiry Q3 Summary)
        f_exp = filter_expiry_scope(from_df)
        t_exp = filter_expiry_scope(to_df)
        exp_list = []
        for p in EXPIRY_PIVOT_PERIODS:
            f_sub = f_exp[f_exp["service_expiry_period"] == p] if not f_exp.empty else pd.DataFrame()
            t_sub = t_exp[t_exp["service_expiry_period"] == p] if not t_exp.empty else pd.DataFrame()
            f_cnt = len(f_sub)
            t_cnt = len(t_sub)
            f_acv = float(f_sub["forecast_acv_amount"].sum()) if not f_sub.empty else 0.0
            t_acv = float(t_sub["forecast_acv_amount"].sum()) if not t_sub.empty else 0.0
            exp_list.append({
                "period": p,
                "from_count": f_cnt,
                "to_count": t_cnt,
                "count_diff": t_cnt - f_cnt,
                "from_acv": round(f_acv, 2),
                "to_acv": round(t_acv, 2),
                "acv_diff": round(t_acv - f_acv, 2),
            })

        expiry_cells = []
        for p in EXPIRY_PIVOT_PERIODS:
            for c in [cat for cat in CANONICAL_FORECAST_CATEGORIES if cat != "Blank"]:
                f_cell = f_exp[(f_exp["service_expiry_period"] == p) & (f_exp["forecast_category"] == c)] if not f_exp.empty else pd.DataFrame()
                t_cell = t_exp[(t_exp["service_expiry_period"] == p) & (t_exp["forecast_category"] == c)] if not t_exp.empty else pd.DataFrame()
                f_cnt = len(f_cell)
                t_cnt = len(t_cell)
                f_acv = float(f_cell["forecast_acv_amount"].sum()) if not f_cell.empty else 0.0
                t_acv = float(t_cell["forecast_acv_amount"].sum()) if not t_cell.empty else 0.0
                if f_cnt > 0 or t_cnt > 0:
                    expiry_cells.append({
                        "period": p,
                        "category": c,
                        "from_count": f_cnt,
                        "to_count": t_cnt,
                        "count_diff": t_cnt - f_cnt,
                        "from_acv": round(f_acv, 2),
                        "to_acv": round(t_acv, 2),
                        "acv_diff": round(t_acv - f_acv, 2),
                    })


        # 4. Region comparison
        all_regions = sorted(set(
            (from_df["sub_region"].dropna().tolist() if not from_df.empty else []) +
            (to_df["sub_region"].dropna().tolist() if not to_df.empty else [])
        ))
        region_list = []
        for reg in all_regions:
            f_sub = from_df[from_df["sub_region"] == reg] if not from_df.empty else pd.DataFrame()
            t_sub = to_df[to_df["sub_region"] == reg] if not to_df.empty else pd.DataFrame()
            f_cnt = len(f_sub)
            t_cnt = len(t_sub)
            f_acv = float(f_sub["forecast_acv_amount"].sum()) if not f_sub.empty else 0.0
            t_acv = float(t_sub["forecast_acv_amount"].sum()) if not t_sub.empty else 0.0
            region_list.append({
                "region": reg,
                "from_count": f_cnt,
                "to_count": t_cnt,
                "count_diff": t_cnt - f_cnt,
                "from_acv": round(f_acv, 2),
                "to_acv": round(t_acv, 2),
                "acv_diff": round(t_acv - f_acv, 2),
            })
        region_list.sort(key=lambda r: r["to_acv"], reverse=True)

        # 5. Business unit comparison (exploding multi-BU)
        from backend.utils.normalise import split_business_units
        def _get_bu_counts(opps):
            bu_map = defaultdict(lambda: {"count": 0, "acv": 0.0})
            for o in opps:
                bus = split_business_units(o.business_unit_raw) or ["Unknown"]
                amt = float(o.forecast_acv_amount or 0)
                for bu in bus:
                    bu_map[bu]["count"] += 1
                    bu_map[bu]["acv"] += amt
            return bu_map

        f_bu_map = _get_bu_counts(from_opps)
        t_bu_map = _get_bu_counts(to_opps)
        all_bus = sorted(set(f_bu_map.keys()) | set(t_bu_map.keys()))
        bu_list = []
        for bu in all_bus:
            f_item = f_bu_map.get(bu, {"count": 0, "acv": 0.0})
            t_item = t_bu_map.get(bu, {"count": 0, "acv": 0.0})
            bu_list.append({
                "business_unit": bu,
                "from_count": f_item["count"],
                "to_count": t_item["count"],
                "count_diff": t_item["count"] - f_item["count"],
                "from_acv": round(f_item["acv"], 2),
                "to_acv": round(t_item["acv"], 2),
                "acv_diff": round(t_item["acv"] - f_item["acv"], 2),
            })
        bu_list.sort(key=lambda b: b["to_acv"], reverse=True)

        # 6. Movement and ACV changes
        movements = (
            self.db.query(ForecastMovementLog)
            .filter(
                ForecastMovementLog.snapshot_from_id == from_snap.id,
                ForecastMovementLog.snapshot_to_id == to_snap.id,
            )
            .all()
        )
        movement_list = [
            {
                "from": m.from_category,
                "to": m.to_category,
                "count": m.opportunity_count,
                "acv": float(m.acv_total),
            }
            for m in movements
        ]
        # Fallback: if no stored movement log rows, infer from opp rows
        merged_common = pd.DataFrame()
        if not from_df.empty and not to_df.empty:
            merged_common = pd.merge(
                from_df,
                to_df,
                on="opportunity_id_18",
                suffixes=("_from", "_to"),
            )

        if not movement_list and not merged_common.empty:
            moved = merged_common[merged_common["forecast_category_from"] != merged_common["forecast_category_to"]]
            if not moved.empty:
                mov_grp = moved.groupby(["forecast_category_from", "forecast_category_to"]).agg(
                    count=("opportunity_id_18", "count"),
                    acv=("forecast_acv_amount_to", "sum"),
                ).reset_index()
                for _, r in mov_grp.iterrows():
                    movement_list.append({
                        "from": r["forecast_category_from"],
                        "to": r["forecast_category_to"],
                        "count": int(r["count"]),
                        "acv": round(float(r["acv"]), 2),
                    })

        # Attach opportunities and compute accurate ACV from merged_common for each movement link
        if not merged_common.empty:
            for m in movement_list:
                f_cat = m["from"]
                t_cat = m["to"]
                sub = merged_common[
                    (merged_common["forecast_category_from"] == f_cat) &
                    (merged_common["forecast_category_to"] == t_cat)
                ]
                if not sub.empty:
                    m["count"] = len(sub)
                    m["acv"] = round(float(sub["forecast_acv_amount_to"].sum()), 2)
                m["opportunities"] = [
                    {
                        "opportunity_id_18": r["opportunity_id_18"],
                        "opportunity_name": r["opportunity_name_to"],
                        "account_name": r["account_name_to"],
                        "acv": round(float(r["forecast_acv_amount_to"]), 2),
                        "old_category": f_cat,
                        "new_category": t_cat,
                    }
                    for _, r in sub.iterrows()
                ]
        else:
            for m in movement_list:
                m["opportunities"] = []

        changes = (
            self.db.query(ChangeLog)
            .filter(
                ChangeLog.snapshot_from_id == from_snap.id,
                ChangeLog.snapshot_to_id == to_snap.id,
                ChangeLog.change_type == "ACV Change",
            )
            .limit(200)
            .all()
        )
        acv_changes = [
            {
                "opportunity_id_18": c.opportunity_id_18,
                "opportunity_name": c.opportunity_name,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "change_type": c.change_type,
            }
            for c in changes
        ]

        # -------------------------------------------------------------- #
        # 7. Waterfall reconciliation
        # Formula: start_acv + new_acv + increases_acv - decreases_acv - removed_acv = end_acv
        # -------------------------------------------------------------- #
        from_ids = set(from_df["opportunity_id_18"]) if not from_df.empty else set()
        to_ids = set(to_df["opportunity_id_18"]) if not to_df.empty else set()
        new_ids = to_ids - from_ids
        removed_ids = from_ids - to_ids
        common_ids = to_ids & from_ids

        start_acv = round(from_total_acv, 2)
        end_acv = round(to_total_acv, 2)

        new_opps_df = to_df[to_df["opportunity_id_18"].isin(new_ids)] if new_ids else pd.DataFrame()
        new_acv = round(float(new_opps_df["forecast_acv_amount"].sum()), 2) if not new_opps_df.empty else 0.0
        new_opportunities = [
            {
                "opportunity_id_18": r["opportunity_id_18"],
                "opportunity_name": r["opportunity_name"],
                "account_name": r["account_name"],
                "acv": round(float(r["forecast_acv_amount"]), 2),
                "forecast_category": r["forecast_category"],
                "approval_status": r["approval_status"],
            }
            for _, r in new_opps_df.iterrows()
        ]

        rem_opps_df = from_df[from_df["opportunity_id_18"].isin(removed_ids)] if removed_ids else pd.DataFrame()
        removed_acv = round(float(rem_opps_df["forecast_acv_amount"].sum()), 2) if not rem_opps_df.empty else 0.0
        removed_opportunities = [
            {
                "opportunity_id_18": r["opportunity_id_18"],
                "opportunity_name": r["opportunity_name"],
                "account_name": r["account_name"],
                "acv": round(float(r["forecast_acv_amount"]), 2),
                "forecast_category": r["forecast_category"],
                "approval_status": r["approval_status"],
            }
            for _, r in rem_opps_df.iterrows()
        ]

        increases_acv = 0.0
        decreases_acv = 0.0
        increase_opportunities = []
        decrease_opportunities = []

        if not merged_common.empty:
            merged_common["diff"] = (
                merged_common["forecast_acv_amount_to"] - merged_common["forecast_acv_amount_from"]
            )
            inc_df = merged_common[merged_common["diff"] > 0.005]
            dec_df = merged_common[merged_common["diff"] < -0.005]

            increases_acv = round(float(inc_df["diff"].sum()), 2) if not inc_df.empty else 0.0
            decreases_acv = round(float(dec_df["diff"].abs().sum()), 2) if not dec_df.empty else 0.0

            increase_opportunities = [
                {
                    "opportunity_id_18": r["opportunity_id_18"],
                    "opportunity_name": r["opportunity_name_to"],
                    "account_name": r["account_name_to"],
                    "old_acv": round(float(r["forecast_acv_amount_from"]), 2),
                    "new_acv": round(float(r["forecast_acv_amount_to"]), 2),
                    "acv_diff": round(float(r["diff"]), 2),
                    "forecast_category": r["forecast_category_to"],
                    "approval_status": r["approval_status_to"],
                }
                for _, r in inc_df.iterrows()
            ]
            decrease_opportunities = [
                {
                    "opportunity_id_18": r["opportunity_id_18"],
                    "opportunity_name": r["opportunity_name_to"],
                    "account_name": r["account_name_to"],
                    "old_acv": round(float(r["forecast_acv_amount_from"]), 2),
                    "new_acv": round(float(r["forecast_acv_amount_to"]), 2),
                    "acv_diff": round(float(r["diff"]), 2),
                    "forecast_category": r["forecast_category_to"],
                    "approval_status": r["approval_status_to"],
                }
                for _, r in dec_df.iterrows()
            ]

        # Exact reconciliation arithmetic
        calc_reconciled = round(start_acv + new_acv + increases_acv - decreases_acv - removed_acv, 2)
        is_reconciled = abs(calc_reconciled - end_acv) < 0.05
        # Reconcile exact rounding if difference is within float cent noise
        reconciled_acv = end_acv if is_reconciled else calc_reconciled

        waterfall = {
            "start_acv": start_acv,
            "start_count": from_total_count,
            "new_acv": new_acv,
            "new_count": len(new_ids),
            "new_opportunities": new_opportunities,
            "increases_acv": increases_acv,
            "increases_count": len(increase_opportunities),
            "increase_opportunities": increase_opportunities,
            "decreases_acv": decreases_acv,
            "decreases_count": len(decrease_opportunities),
            "decrease_opportunities": decrease_opportunities,
            "removed_acv": removed_acv,
            "removed_count": len(removed_ids),
            "removed_opportunities": removed_opportunities,
            "end_acv": end_acv,
            "end_count": to_total_count,
            "reconciled_acv": reconciled_acv,
            "is_reconciled": is_reconciled,
        }

        # -------------------------------------------------------------- #
        # 8. Biggest movers (top 10 by abs diff)
        # -------------------------------------------------------------- #
        movers_candidates = []
        for o in new_opportunities:
            movers_candidates.append({
                "opportunity_id_18": o["opportunity_id_18"],
                "opportunity_name": o["opportunity_name"],
                "account_name": o["account_name"],
                "tag": "New",
                "old_acv": 0.0,
                "new_acv": o["acv"],
                "acv_diff": o["acv"],
                "abs_diff": abs(o["acv"]),
                "forecast_category": o["forecast_category"],
                "approval_status": o["approval_status"],
            })
        for o in increase_opportunities:
            movers_candidates.append({
                "opportunity_id_18": o["opportunity_id_18"],
                "opportunity_name": o["opportunity_name"],
                "account_name": o["account_name"],
                "tag": "Increase",
                "old_acv": o["old_acv"],
                "new_acv": o["new_acv"],
                "acv_diff": o["acv_diff"],
                "abs_diff": abs(o["acv_diff"]),
                "forecast_category": o["forecast_category"],
                "approval_status": o["approval_status"],
            })
        for o in decrease_opportunities:
            movers_candidates.append({
                "opportunity_id_18": o["opportunity_id_18"],
                "opportunity_name": o["opportunity_name"],
                "account_name": o["account_name"],
                "tag": "Decrease",
                "old_acv": o["old_acv"],
                "new_acv": o["new_acv"],
                "acv_diff": o["acv_diff"],
                "abs_diff": abs(o["acv_diff"]),
                "forecast_category": o["forecast_category"],
                "approval_status": o["approval_status"],
            })
        for o in removed_opportunities:
            movers_candidates.append({
                "opportunity_id_18": o["opportunity_id_18"],
                "opportunity_name": o["opportunity_name"],
                "account_name": o["account_name"],
                "tag": "Removed",
                "old_acv": o["acv"],
                "new_acv": 0.0,
                "acv_diff": -o["acv"],
                "abs_diff": abs(o["acv"]),
                "forecast_category": o["forecast_category"],
                "approval_status": o["approval_status"],
            })
        movers_candidates.sort(key=lambda x: x["abs_diff"], reverse=True)
        biggest_movers = movers_candidates[:10]

        # -------------------------------------------------------------- #
        # 9. Needs attention panel
        # Newly rejected, newly pending, category slipped, ACV dropped > 25%
        # -------------------------------------------------------------- #
        attention_list = []
        if not merged_common.empty:
            for _, r in merged_common.iterrows():
                f_app = r["approval_status_from"]
                t_app = r["approval_status_to"]
                f_cat = r["forecast_category_from"]
                t_cat = r["forecast_category_to"]
                f_acv = float(r["forecast_acv_amount_from"])
                t_acv = float(r["forecast_acv_amount_to"])
                opp_id = r["opportunity_id_18"]
                opp_name = r["opportunity_name_to"]
                acct = r["account_name_to"]

                # A. Newly rejected
                if f_app != "Rejected" and t_app == "Rejected":
                    attention_list.append({
                        "opportunity_id_18": opp_id,
                        "opportunity_name": opp_name,
                        "account_name": acct,
                        "attention_type": "newly_rejected",
                        "attention_label": "Newly Rejected",
                        "details": f"Approval status changed to Rejected (was {f_app})",
                        "old_value": f_app,
                        "new_value": t_app,
                        "acv": round(t_acv, 2),
                        "acv_diff": round(t_acv - f_acv, 2),
                        "forecast_category": t_cat,
                        "approval_status": t_app,
                    })

                # B. Newly pending approval
                is_old_pending = f_app in ["Pending Approval", "Pending-Approval"]
                is_new_pending = t_app in ["Pending Approval", "Pending-Approval"]
                if not is_old_pending and is_new_pending:
                    attention_list.append({
                        "opportunity_id_18": opp_id,
                        "opportunity_name": opp_name,
                        "account_name": acct,
                        "attention_type": "newly_pending",
                        "attention_label": "Newly Pending Approval",
                        "details": f"Submitted for approval (was {f_app})",
                        "old_value": f_app,
                        "new_value": t_app,
                        "acv": round(t_acv, 2),
                        "acv_diff": round(t_acv - f_acv, 2),
                        "forecast_category": t_cat,
                        "approval_status": t_app,
                    })

                # C. Dropped from forecast / slipped
                is_blank = t_cat in ["Blank", "", None]
                dropped_or_slipped = False
                if f_cat == "Pipeline" and is_blank:
                    dropped_or_slipped = True
                elif f_cat == "Best Case" and (is_blank or t_cat in ["Pipeline"]):
                    dropped_or_slipped = True
                elif f_cat == "Commit" and (is_blank or t_cat in ["Best Case", "Pipeline"]):
                    dropped_or_slipped = True

                if dropped_or_slipped:
                    attention_list.append({
                        "opportunity_id_18": opp_id,
                        "opportunity_name": opp_name,
                        "account_name": acct,
                        "attention_type": "dropped_from_forecast",
                        "attention_label": "Dropped from forecast / slipped",
                        "details": f"Forecast dropped from {f_cat} to {t_cat}",
                        "old_value": f_cat,
                        "new_value": t_cat,
                        "acv": round(t_acv, 2),
                        "acv_diff": round(t_acv - f_acv, 2),
                        "forecast_category": t_cat,
                        "approval_status": t_app,
                    })

                # D. ACV dropped > 25%
                if f_acv > 0 and (f_acv - t_acv) / f_acv > 0.25:
                    pct_drop = round(((f_acv - t_acv) / f_acv) * 100, 1)
                    attention_list.append({
                        "opportunity_id_18": opp_id,
                        "opportunity_name": opp_name,
                        "account_name": acct,
                        "attention_type": "acv_drop_25",
                        "attention_label": "ACV Dropped > 25%",
                        "details": f"ACV decreased by {pct_drop}% (-${round(f_acv - t_acv, 2):,})",
                        "old_value": f"${round(f_acv, 2):,}",
                        "new_value": f"${round(t_acv, 2):,}",
                        "acv": round(t_acv, 2),
                        "acv_diff": round(t_acv - f_acv, 2),
                        "forecast_category": t_cat,
                        "approval_status": t_app,
                    })

        # Calculate unique deals and category breakdowns for Needs Attention
        unique_attention_ids = {item["opportunity_id_18"] for item in attention_list}
        attention_summary = {
            "total_unique": len(unique_attention_ids),
            "total_exceptions": len(attention_list),
            "overlap_count": len(attention_list) - len(unique_attention_ids),
            "counts_by_type": {
                "newly_rejected": len([i for i in attention_list if i["attention_type"] == "newly_rejected"]),
                "newly_pending": len([i for i in attention_list if i["attention_type"] == "newly_pending"]),
                "dropped_from_forecast": len([i for i in attention_list if i["attention_type"] == "dropped_from_forecast"]),
                "acv_drop_25": len([i for i in attention_list if i["attention_type"] == "acv_drop_25"]),
            },
            "items": attention_list,
        }

        # -------------------------------------------------------------- #
        # 10. Dynamic Headline & Insight Chips
        # -------------------------------------------------------------- #
        net_acv_diff = round(to_total_acv - from_total_acv, 2)
        net_cnt_diff = to_total_count - from_total_count
        direction = "up" if net_acv_diff >= 0 else "down"
        abs_acv_m = abs(net_acv_diff) / 1_000_000

        # Specific Commit -> Closed flow
        c_to_cl_flows = [m for m in movement_list if m["from"] == "Commit" and m["to"] == "Closed"]
        c_to_cl_flow = c_to_cl_flows[0] if c_to_cl_flows else None
        c_to_cl_acv = c_to_cl_flow["acv"] if c_to_cl_flow else 0.0
        c_to_cl_count = c_to_cl_flow["count"] if c_to_cl_flow else 0

        # Net Commit category change
        to_commit_val = float(to_df[to_df["forecast_category"] == "Commit"]["forecast_acv_amount"].sum()) if not to_df.empty else 0.0
        from_commit_val = float(from_df[from_df["forecast_category"] == "Commit"]["forecast_acv_amount"].sum()) if not from_df.empty else 0.0
        net_commit_diff = to_commit_val - from_commit_val
        net_commit_str = f"+${net_commit_diff/1_000_000:.2f}M" if net_commit_diff >= 0 else f"-${abs(net_commit_diff)/1_000_000:.2f}M"

        flow_str = ""
        if c_to_cl_count > 0:
            flow_str = f" Commit moved {net_commit_str}, mostly into Closed ({c_to_cl_count} deals)."
        else:
            cat_deltas = sorted(fc_list, key=lambda c: abs(c["acv_diff"]), reverse=True)
            if cat_deltas and abs(cat_deltas[0]["acv_diff"]) > 1000:
                c_diff = cat_deltas[0]
                diff_m = c_diff["acv_diff"] / 1_000_000
                flow_str = f" {c_diff['category']} shifted {'+$' if diff_m >= 0 else '-$'}{abs(diff_m):.2f}M."

        compare_label_str = from_snap.label.lower() if from_snap.label else "previous snapshot"
        headline_text = f"ACV is {direction} ${abs_acv_m:.2f}M and {abs(net_cnt_diff)} opportunities since {compare_label_str}.{flow_str}"

        insight_chips = []
        if c_to_cl_flow and c_to_cl_count > 0:
            # Point 1: Must show the ACV of the deals that moved (about $6.58M), not the net category change (-$5.65M)
            flow_m = c_to_cl_acv / 1_000_000
            insight_chips.append({
                "label": "Commit → Closed",
                "value": f"+${flow_m:.2f}M ({c_to_cl_count} deals)",
                "type": "positive",
            })
        if len(new_ids) > 0:
            insight_chips.append({
                "label": "New Opportunities",
                "value": f"+{len(new_ids)} deals (+${new_acv/1_000_000:.2f}M)",
                "type": "positive",
            })
        if attention_summary["total_unique"] > 0:
            insight_chips.append({
                "label": "Needs Attention",
                "value": f"{attention_summary['total_unique']} unique deals flagged",
                "type": "warning",
            })
        else:
            insight_chips.append({
                "label": "Pipeline Stability",
                "value": "Zero deal downgrades",
                "type": "positive",
            })

        # -------------------------------------------------------------- #
        # 11. KPI Strip (6 KPIs) with compare delta, last week delta, sparklines
        # -------------------------------------------------------------- #
        lw_snap = (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.snapshot_date <= to_snap.snapshot_date - timedelta(days=6))
            .order_by(UploadSnapshot.snapshot_date.desc())
            .first()
        )
        lw_df = _opps_to_df(self._opps_for(lw_snap, scope=scope, include_deleted_lost=include_deleted_lost)) if lw_snap else pd.DataFrame()
        lw_total_acv = float(lw_df["forecast_acv_amount"].sum()) if not lw_df.empty else None
        lw_total_count = len(lw_df) if not lw_df.empty else None

        def _cat_sum(d, cat):
            if d.empty: return 0.0
            sub = d[d["forecast_category"] == cat]
            return float(sub["forecast_acv_amount"].sum()) if not sub.empty else 0.0

        def _cat_count(d, cat):
            if d.empty: return 0
            sub = d[d["forecast_category"] == cat]
            return len(sub)

        all_snaps = (
            self.db.query(UploadSnapshot)
            .order_by(UploadSnapshot.snapshot_date.asc())
            .all()
        )
        snap_points_map = defaultdict(list)
        for s in all_snaps:
            s_df = _opps_to_df(self._opps_for(s, scope=scope, include_deleted_lost=include_deleted_lost))
            dt = s.snapshot_date.isoformat()
            if not s_df.empty:
                s_tot_acv = float(s_df["forecast_acv_amount"].sum())
                s_tot_cnt = len(s_df)
                s_closed = _cat_sum(s_df, "Closed")
                s_commit = _cat_sum(s_df, "Commit")
                s_best = _cat_sum(s_df, "Best Case")
                s_pipe = _cat_sum(s_df, "Pipeline")
            else:
                s_tot_acv = s_tot_cnt = s_closed = s_commit = s_best = s_pipe = 0

            snap_points_map["total_acv"].append({"date": dt, "value": round(s_tot_acv, 2)})
            snap_points_map["total_count"].append({"date": dt, "value": s_tot_cnt})
            snap_points_map["closed_acv"].append({"date": dt, "value": round(s_closed, 2)})
            snap_points_map["commit_acv"].append({"date": dt, "value": round(s_commit, 2)})
            snap_points_map["best_case_acv"].append({"date": dt, "value": round(s_best, 2)})
            snap_points_map["pipeline_acv"].append({"date": dt, "value": round(s_pipe, 2)})

        to_closed_acv = _cat_sum(to_df, "Closed")
        from_closed_acv = _cat_sum(from_df, "Closed")
        lw_closed_acv = _cat_sum(lw_df, "Closed") if not lw_df.empty else None

        to_commit_acv = _cat_sum(to_df, "Commit")
        from_commit_acv = _cat_sum(from_df, "Commit")
        lw_commit_acv = _cat_sum(lw_df, "Commit") if not lw_df.empty else None

        to_best_acv = _cat_sum(to_df, "Best Case")
        from_best_acv = _cat_sum(from_df, "Best Case")
        lw_best_acv = _cat_sum(lw_df, "Best Case") if not lw_df.empty else None

        to_pipe_acv = _cat_sum(to_df, "Pipeline")
        from_pipe_acv = _cat_sum(from_df, "Pipeline")
        lw_pipe_acv = _cat_sum(lw_df, "Pipeline") if not lw_df.empty else None

        # Point 2: Category-specific vs last week deltas
        kpi_strip = [
            {
                "key": "total_acv",
                "label": "Total ACV",
                "value": round(to_total_acv, 2),
                "format": "acv",
                "delta_compare": round(to_total_acv - from_total_acv, 2),
                "delta_compare_count": to_total_count - from_total_count,
                "delta_compare_label": f"vs {from_snap.label.lower()}",
                "delta_last_week": round(to_total_acv - lw_total_acv, 2) if lw_total_acv is not None else None,
                "delta_last_week_count": to_total_count - lw_total_count if lw_total_count is not None else None,
                "delta_last_week_label": "vs last week",
                "points": snap_points_map["total_acv"],
                "accent": "#00A3AD",
            },
            {
                "key": "total_count",
                "label": "Opportunities",
                "value": to_total_count,
                "format": "count",
                "delta_compare": to_total_count - from_total_count,
                "delta_compare_count": to_total_count - from_total_count,
                "delta_compare_label": f"vs {from_snap.label.lower()}",
                "delta_last_week": to_total_count - lw_total_count if lw_total_count is not None else None,
                "delta_last_week_count": to_total_count - lw_total_count if lw_total_count is not None else None,
                "delta_last_week_label": "vs last week",
                "points": snap_points_map["total_count"],
                "accent": "#8080FF",
            },
            {
                "key": "closed_acv",
                "label": "Closed",
                "value": round(to_closed_acv, 2),
                "format": "acv",
                "delta_compare": round(to_closed_acv - from_closed_acv, 2),
                "delta_compare_count": _cat_count(to_df, "Closed") - _cat_count(from_df, "Closed"),
                "delta_compare_label": f"vs {from_snap.label.lower()}",
                "delta_last_week": round(to_closed_acv - lw_closed_acv, 2) if lw_closed_acv is not None else None,
                "delta_last_week_count": _cat_count(to_df, "Closed") - _cat_count(lw_df, "Closed") if not lw_df.empty else None,
                "delta_last_week_label": "vs last week",
                "points": snap_points_map["closed_acv"],
                "accent": "#10B981",
            },
            {
                "key": "commit_acv",
                "label": "Commit",
                "value": round(to_commit_acv, 2),
                "format": "acv",
                "delta_compare": round(to_commit_acv - from_commit_acv, 2),
                "delta_compare_count": _cat_count(to_df, "Commit") - _cat_count(from_df, "Commit"),
                "delta_compare_label": f"vs {from_snap.label.lower()}",
                "delta_last_week": round(to_commit_acv - lw_commit_acv, 2) if lw_commit_acv is not None else None,
                "delta_last_week_count": _cat_count(to_df, "Commit") - _cat_count(lw_df, "Commit") if not lw_df.empty else None,
                "delta_last_week_label": "vs last week",
                "points": snap_points_map["commit_acv"],
                "accent": "#F59E0B",
            },
            {
                "key": "best_case_acv",
                "label": "Best Case",
                "value": round(to_best_acv, 2),
                "format": "acv",
                "delta_compare": round(to_best_acv - from_best_acv, 2),
                "delta_compare_count": _cat_count(to_df, "Best Case") - _cat_count(from_df, "Best Case"),
                "delta_compare_label": f"vs {from_snap.label.lower()}",
                "delta_last_week": round(to_best_acv - lw_best_acv, 2) if lw_best_acv is not None else None,
                "delta_last_week_count": _cat_count(to_df, "Best Case") - _cat_count(lw_df, "Best Case") if not lw_df.empty else None,
                "delta_last_week_label": "vs last week",
                "points": snap_points_map["best_case_acv"],
                "accent": "#00A3AD",
            },
            {
                "key": "pipeline_acv",
                "label": "Pipeline",
                "value": round(to_pipe_acv, 2),
                "format": "acv",
                "delta_compare": round(to_pipe_acv - from_pipe_acv, 2),
                "delta_compare_count": _cat_count(to_df, "Pipeline") - _cat_count(from_df, "Pipeline"),
                "delta_compare_label": f"vs {from_snap.label.lower()}",
                "delta_last_week": round(to_pipe_acv - lw_pipe_acv, 2) if lw_pipe_acv is not None else None,
                "delta_last_week_count": _cat_count(to_df, "Pipeline") - _cat_count(lw_df, "Pipeline") if not lw_df.empty else None,
                "delta_last_week_label": "vs last week",
                "points": snap_points_map["pipeline_acv"],
                "accent": "#6366F1",
            },
        ]

        return {
            "from_snapshot": {
                "id": from_snap.id,
                "date": from_snap.snapshot_date.isoformat(),
                "label": from_snap.label,
                "total_acv": round(from_total_acv, 2),
                "total_count": from_total_count,
            },
            "to_snapshot": {
                "id": to_snap.id,
                "date": to_snap.snapshot_date.isoformat(),
                "label": to_snap.label,
                "total_acv": round(to_total_acv, 2),
                "total_count": to_total_count,
            },
            "diff": {
                "acv": round(to_total_acv - from_total_acv, 2),
                "count": to_total_count - from_total_count,
            },
            "headline": {
                "text": headline_text,
                "chips": insight_chips,
            },
            "kpi_strip": kpi_strip,
            "waterfall": waterfall,
            "biggest_movers": biggest_movers,
            "needs_attention": attention_list,
            "needs_attention_summary": attention_summary,
            "forecast_category": fc_list,
            "approval_status": appr_list,
            "expiry_pivot": exp_list,
            "expiry_cells": expiry_cells,
            "region": region_list,
            "business_unit": bu_list,
            "movement": movement_list,
            "acv_changes": acv_changes,
        }

    def get_sub_regions_overview(
        self,
        ctx: UserContext,
        snapshot_id: str | None = None,
        compare_to: str | None = None,
        mode: str = "as_in_excel",
        scope: str = "all",
        include_deleted_lost: bool = True,
    ) -> dict:
        snap = self._resolve_snapshot(ctx, snapshot_id)
        if snap is None:
            return {"regions": [], "total_acv": 0.0, "total_count": 0, "mode": mode}

        compare_snap = None
        if compare_to:
            compare_snap = self.get_snapshot_by_id(ctx, compare_to)
        if compare_snap is None:
            compare_snap = self._get_adjacent_snapshot(snap, days_back=1)

        df_curr = _opps_to_df(self._opps_for(snap, scope=scope, include_deleted_lost=include_deleted_lost))
        df_prev = _opps_to_df(self._opps_for(compare_snap, scope=scope, include_deleted_lost=include_deleted_lost)) if compare_snap else pd.DataFrame()

        all_snaps = (
            self.db.query(UploadSnapshot)
            .order_by(UploadSnapshot.snapshot_date.asc())
            .all()
        )
        snap_dfs = {s.id: _opps_to_df(self._opps_for(s, scope=scope, include_deleted_lost=include_deleted_lost)) for s in all_snaps}

        if df_curr.empty:
            return {"regions": [], "total_acv": 0.0, "total_count": 0, "mode": mode}

        curr_grouped = (
            df_curr.groupby("sub_region", dropna=False)
            .agg(count=("opportunity_id_18", "count"), acv=("forecast_acv_amount", "sum"))
            .reset_index()
        )

        prev_grouped = (
            df_prev.groupby("sub_region", dropna=False)
            .agg(prev_count=("opportunity_id_18", "count"), prev_acv=("forecast_acv_amount", "sum"))
            .reset_index()
            if not df_prev.empty
            else pd.DataFrame(columns=["sub_region", "prev_count", "prev_acv"])
        )

        merged = pd.merge(curr_grouped, prev_grouped, on="sub_region", how="outer")
        merged["sub_region"] = merged["sub_region"].fillna("(blank)")
        merged["count"] = merged["count"].fillna(0).astype(int)
        merged["acv"] = merged["acv"].fillna(0.0)
        merged["prev_count"] = merged["prev_count"].fillna(0).astype(int)
        merged["prev_acv"] = merged["prev_acv"].fillna(0.0)
        merged["delta_count"] = merged["count"] - merged["prev_count"]
        merged["delta_acv"] = merged["acv"] - merged["prev_acv"]

        # Sort by acv descending
        merged = merged.sort_values("acv", ascending=False)

        region_list = []
        for _, row in merged.iterrows():
            reg_name = row["sub_region"]
            reg_df = (
                df_curr[df_curr["sub_region"] == reg_name].sort_values("forecast_acv_amount", ascending=False)
                if not df_curr.empty
                else pd.DataFrame()
            )

            top_10 = []
            for _, opp in reg_df.head(10).iterrows():
                bu_val = opp["business_unit_raw"] if mode == "as_in_excel" else opp["business_unit_primary"]
                top_10.append({
                    "id": opp["opportunity_id_18"],
                    "opportunity_id_18": opp["opportunity_id_18"],
                    "opportunity_name": opp["opportunity_name"],
                    "account_name": opp["account_name"],
                    "business_unit": bu_val or "Unknown",
                    "business_unit_raw": opp["business_unit_raw"] or "Unknown",
                    "business_unit_primary": opp["business_unit_primary"] or "Unknown",
                    "forecast_category": opp["forecast_category"],
                    "approval_status": opp["approval_status"],
                    "acv": round(float(opp["forecast_acv_amount"]), 2),
                })

            if mode == "as_in_excel":
                leading_bu = top_10[0]["business_unit_raw"] if top_10 and top_10[0]["business_unit_raw"] else "N/A"
                leading_bu_df = (
                    reg_df[reg_df["business_unit_raw"] == leading_bu].sort_values("forecast_acv_amount", ascending=False)
                    if not reg_df.empty and leading_bu != "N/A"
                    else pd.DataFrame()
                )
            else:
                leading_bu = top_10[0]["business_unit_primary"] if top_10 and top_10[0]["business_unit_primary"] else "N/A"
                leading_bu_df = (
                    reg_df[reg_df["business_unit_primary"] == leading_bu].sort_values("forecast_acv_amount", ascending=False)
                    if not reg_df.empty and leading_bu != "N/A"
                    else pd.DataFrame()
                )

            leading_bu_top_10 = []
            for _, opp in leading_bu_df.head(10).iterrows():
                bu_val = opp["business_unit_raw"] if mode == "as_in_excel" else opp["business_unit_primary"]
                leading_bu_top_10.append({
                    "id": opp["opportunity_id_18"],
                    "opportunity_id_18": opp["opportunity_id_18"],
                    "opportunity_name": opp["opportunity_name"],
                    "account_name": opp["account_name"],
                    "business_unit": bu_val or "Unknown",
                    "business_unit_raw": opp["business_unit_raw"] or "Unknown",
                    "business_unit_primary": opp["business_unit_primary"] or "Unknown",
                    "forecast_category": opp["forecast_category"],
                    "approval_status": opp["approval_status"],
                    "acv": round(float(opp["forecast_acv_amount"]), 2),
                })

            sparkline = []
            for s in all_snaps:
                sdf = snap_dfs.get(s.id)
                if sdf is not None and not sdf.empty:
                    s_acv = float(sdf[sdf["sub_region"] == reg_name]["forecast_acv_amount"].sum())
                    sparkline.append(round(s_acv, 2))
                else:
                    sparkline.append(0.0)

            cat_mix = []
            for cat in ["Closed", "Commit", "Best Case", "Pipeline", "Blank"]:
                c_df = reg_df[reg_df["forecast_category"] == cat]
                cat_mix.append({
                    "category": cat,
                    "count": len(c_df),
                    "acv": round(float(c_df["forecast_acv_amount"].sum()), 2),
                })

            app_mix = []
            for st in ["Approved", "Approved - 2nd", "Pending-Approval", "Blank", "Rejected"]:
                if st == "Pending-Approval":
                    a_df = reg_df[reg_df["approval_status"].isin(["Pending Approval", "Pending-Approval"])]
                else:
                    a_df = reg_df[reg_df["approval_status"] == st]
                app_mix.append({
                    "status": st,
                    "count": len(a_df),
                    "acv": round(float(a_df["forecast_acv_amount"].sum()), 2),
                })

            region_list.append({
                "sub_region": reg_name,
                "acv": round(float(row["acv"]), 2),
                "count": int(row["count"]),
                "delta_acv": round(float(row["delta_acv"]), 2),
                "delta_count": int(row["delta_count"]),
                "prev_acv": round(float(row["prev_acv"]), 2),
                "prev_count": int(row["prev_count"]),
                "sparkline": sparkline,
                "top_10_opportunities": top_10,
                "leading_bu": leading_bu,
                "leading_bu_top_10": leading_bu_top_10,
                "forecast_category_mix": cat_mix,
                "approval_status_mix": app_mix,
            })

        total_acv = round(sum(r["acv"] for r in region_list), 2)
        total_count = sum(r["count"] for r in region_list)

        return {
            "snapshot_id": snap.id,
            "snapshot_date": snap.snapshot_date.isoformat(),
            "compare_snapshot_id": compare_snap.id if compare_snap else None,
            "compare_snapshot_date": compare_snap.snapshot_date.isoformat() if compare_snap else None,
            "total_acv": total_acv,
            "total_count": total_count,
            "regions": region_list,
        }

    def compute_anomaly_zscore(
        self,
        ctx: UserContext,
        scope: str = "renewals",
        include_deleted_lost: bool = False,
    ) -> dict:
        """
        Compute anomaly detection z-score for daily changes normalized by days_between.
        Friday-to-Monday change is divided by 3 days.
        Activates when >= 7 snapshots are collected.
        """
        snapshots = (
            self.db.query(UploadSnapshot)
            .order_by(UploadSnapshot.snapshot_date.asc())
            .all()
        )
        if len(snapshots) < 7:
            return {
                "has_sufficient_history": False,
                "snapshot_count": len(snapshots),
                "required_snapshots": 7,
                "message": f"Collecting history — {len(snapshots)} of 7 snapshots available",
                "z_score": None,
                "is_anomaly": False,
            }

        daily_rates = []
        prev_val = None
        prev_date = None
        for s in snapshots:
            if not self.is_scope_available(s.id, scope):
                continue
            opps = self._opps_for(s, scope=scope, include_deleted_lost=include_deleted_lost)
            tot_acv = sum(float(o.forecast_acv_amount or 0) for o in opps)
            if prev_val is not None and prev_date is not None:
                days_diff = max(1, (s.snapshot_date - prev_date).days)
                daily_rate = (tot_acv - prev_val) / days_diff
                daily_rates.append(daily_rate)
            prev_val = tot_acv
            prev_date = s.snapshot_date

        if len(daily_rates) < 6:
            return {
                "has_sufficient_history": False,
                "snapshot_count": len(snapshots),
                "required_snapshots": 7,
                "z_score": None,
                "is_anomaly": False,
            }

        import numpy as np
        mean_rate = float(np.mean(daily_rates[:-1]))
        std_rate = float(np.std(daily_rates[:-1]))
        latest_rate = daily_rates[-1]
        z_score = (latest_rate - mean_rate) / std_rate if std_rate > 0 else 0.0

        return {
            "has_sufficient_history": True,
            "snapshot_count": len(snapshots),
            "required_snapshots": 7,
            "latest_daily_rate": round(latest_rate, 2),
            "mean_daily_rate": round(mean_rate, 2),
            "std_daily_rate": round(std_rate, 2),
            "z_score": round(z_score, 2),
            "is_anomaly": abs(z_score) > 2.0,
        }

    def get_history_overview(
        self,
        ctx: UserContext,
        scope: str = "all",
        include_deleted_lost: bool = True,
    ) -> dict:
        snapshots = (
            self.db.query(UploadSnapshot)
            .order_by(UploadSnapshot.snapshot_date.asc())
            .all()
        )
        snap_items = []
        dates = []
        labels = []
        total_acv_series = []
        count_series = []
        category_series = {cat: [] for cat in ["Closed", "Commit", "Best Case", "Pipeline", "Blank"]}
        approval_series = {st: [] for st in ["Approved", "Approved - 2nd", "Pending-Approval", "Blank", "Rejected"]}

        prev_tot_acv = None
        prev_tot_cnt = None

        for idx, s in enumerate(snapshots):
            d_str = s.snapshot_date.isoformat()
            dates.append(d_str)
            labels.append(s.label)

            scope_avail = self.is_scope_available(s.id, scope)
            if not scope_avail:
                total_acv_series.append({"date": d_str, "label": s.label, "value": None})
                count_series.append({"date": d_str, "label": s.label, "value": None})
                for cat in category_series.keys():
                    category_series[cat].append({"date": d_str, "label": s.label, "value": None})
                for st in approval_series.keys():
                    approval_series[st].append({"date": d_str, "label": s.label, "value": None})

                snap_items.append({
                    "id": s.id,
                    "label": s.label,
                    "snapshot_date": d_str,
                    "yesterday_date": s.yesterday_date.isoformat() if s.yesterday_date else None,
                    "row_count": None,
                    "total_acv": None,
                    "scope_available": False,
                    "source_file_summary": s.source_file_summary,
                    "source_file_comparison": s.source_file_comparison,
                    "last_week_source": s.last_week_source or "real_snapshot",
                    "last_week_is_partial": s.last_week_is_partial,
                    "uploaded_at": s.uploaded_at.isoformat() if s.uploaded_at else None,
                    "is_active_today": s.is_active_today,
                    "what_changed": "Scope unavailable for this snapshot",
                })
                prev_tot_acv = None
                prev_tot_cnt = None
                continue

            opps = self._opps_for(s, scope=scope, include_deleted_lost=include_deleted_lost)
            df = _opps_to_df(opps)
            tot_acv = round(float(df["forecast_acv_amount"].sum()), 2) if not df.empty else 0.0
            tot_cnt = len(df)
            total_acv_series.append({"date": d_str, "label": s.label, "value": tot_acv})
            count_series.append({"date": d_str, "label": s.label, "value": tot_cnt})

            for cat in category_series.keys():
                c_val = round(float(df[df["forecast_category"] == cat]["forecast_acv_amount"].sum()), 2) if not df.empty else 0.0
                category_series[cat].append({"date": d_str, "label": s.label, "value": c_val})

            for st in approval_series.keys():
                if st == "Pending-Approval":
                    st_cnt = len(df[df["approval_status"].isin(["Pending Approval", "Pending-Approval"])]) if not df.empty else 0
                else:
                    st_cnt = len(df[df["approval_status"] == st]) if not df.empty else 0
                approval_series[st].append({"date": d_str, "label": s.label, "value": st_cnt})

            what_changed = []
            if idx > 0 and prev_tot_acv is not None and prev_tot_cnt is not None:
                prev_s = snapshots[idx - 1]
                days_between = max(1, (s.snapshot_date - prev_s.snapshot_date).days)
                acv_diff = round(tot_acv - prev_tot_acv, 2)
                cnt_diff = tot_cnt - prev_tot_cnt
                daily_acv_rate = round(acv_diff / days_between, 2)
                what_changed.append(f"ACV {'+' if acv_diff >= 0 else ''}${acv_diff:,.2f} ({'+' if daily_acv_rate >= 0 else ''}${daily_acv_rate:,.2f}/d over {days_between}d)")
                what_changed.append(f"Deals {'+' if cnt_diff >= 0 else ''}{cnt_diff}")
            elif idx > 0:
                what_changed.append("Previous snapshot scope unavailable")
            else:
                what_changed.append("Initial baseline snapshot")

            prev_tot_acv = tot_acv
            prev_tot_cnt = tot_cnt

            snap_items.append({
                "id": s.id,
                "label": s.label,
                "snapshot_date": d_str,
                "yesterday_date": s.yesterday_date.isoformat() if s.yesterday_date else None,
                "row_count": tot_cnt,
                "total_acv": tot_acv,
                "scope_available": True,
                "source_file_summary": s.source_file_summary,
                "source_file_comparison": s.source_file_comparison,
                "last_week_source": s.last_week_source or "real_snapshot",
                "last_week_is_partial": s.last_week_is_partial,
                "uploaded_at": s.uploaded_at.isoformat() if s.uploaded_at else None,
                "is_active_today": s.is_active_today,
                "what_changed": " · ".join(what_changed),
            })

        timeline_items = list(reversed(snap_items))
        anomaly_info = self.compute_anomaly_zscore(ctx, scope=scope, include_deleted_lost=include_deleted_lost)

        return {
            "snapshots": timeline_items,
            "dates": dates,
            "labels": labels,
            "total_count": len(snapshots),
            "has_sufficient_history": len(snapshots) >= 7,
            "history_note": f"Collecting history — {len(snapshots)} of 7 snapshots available" if len(snapshots) < 7 else None,
            "trends": {
                "total_acv": total_acv_series,
                "count": count_series,
                "category_acv": category_series,
                "approval_counts": approval_series,
            },
            "anomaly_status": anomaly_info,
        }


