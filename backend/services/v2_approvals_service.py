from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Optional
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot
from backend.services.context import UserContext
from backend.services.scopes import ScopeService

def _sum(df: pd.DataFrame, col: str) -> float:
    if df.empty or col not in df.columns:
        return 0.0
    return float(df[col].sum())

log = logging.getLogger(__name__)

ALL_FC = ["Closed", "Commit", "Best Case", "Pipeline", "Blank"]
FUNNEL_STAGES = ["Approved", "Pending Approval", "Blank"]

def _norm_approval(s: str | None) -> str:
    if not s or str(s).strip() in ("", "nan", "None", "Blank"):
        return "Blank"
    s = s.strip()
    if s in ("Approved", "Approved - 2nd"):
        return "Approved"
    if s in ("Pending Approval", "Pending-Approval"):
        return "Pending Approval"
    return s

def _norm_fc(s: str | None) -> str:
    if not s or str(s).strip() in ("", "nan", "None"):
        return "Blank"
    s = s.strip()
    if s not in ["Closed", "Commit", "Best Case", "Pipeline"]:
        return "Blank"
    return s

class V2ApprovalsService:
    def __init__(self, db: Session):
        self.db = db

    def _get_snapshot(self, ctx: UserContext, target_date: Optional[str] = None, base_snap: Optional[UploadSnapshot] = None) -> Optional[UploadSnapshot]:
        q = self.db.query(UploadSnapshot)
        if target_date:
            if target_date == "yesterday":
                if base_snap:
                    # Look for date < base_snap.snapshot_date
                    return q.filter(UploadSnapshot.snapshot_date < base_snap.snapshot_date).order_by(UploadSnapshot.snapshot_date.desc()).first()
                else:
                    latest = q.order_by(UploadSnapshot.snapshot_date.desc()).first()
                    if not latest: return None
                    return q.filter(UploadSnapshot.snapshot_date < latest.snapshot_date).order_by(UploadSnapshot.snapshot_date.desc()).first()
            elif target_date == "last_week":
                if base_snap:
                    target = base_snap.snapshot_date - timedelta(days=7)
                else:
                    latest = q.order_by(UploadSnapshot.snapshot_date.desc()).first()
                    if not latest: return None
                    target = latest.snapshot_date - timedelta(days=7)
                return q.filter(UploadSnapshot.snapshot_date <= target).order_by(UploadSnapshot.snapshot_date.desc()).first()
            else:
                try:
                    d = date.fromisoformat(target_date)
                    return q.filter(UploadSnapshot.snapshot_date <= d).order_by(UploadSnapshot.snapshot_date.desc()).first()
                except ValueError:
                    return None
        return q.order_by(UploadSnapshot.snapshot_date.desc()).first()

    def _scoped_opps(self, snap: UploadSnapshot, filter_spec: Optional[ScopeService.FilterSpec] = None, exclude_deleted_lost: bool = False, target_date = None) -> tuple[pd.DataFrame, Any]:
        from backend.services.scopes import FilterSpec
        if not snap:
            return pd.DataFrame(), None
        eff_date = target_date
        if not eff_date and filter_spec and filter_spec.as_of:
            try:
                eff_date = date.fromisoformat(filter_spec.as_of)
            except ValueError:
                pass
        if not eff_date:
            eff_date = snap.snapshot_date
        fs = filter_spec.model_copy() if filter_spec else FilterSpec()
        if exclude_deleted_lost:
            fs.include_deleted_lost = False
        res = ScopeService.resolve(fs, snapshot=snap, as_of_date=eff_date)
        q = (
            self.db.query(Opportunity)
            .filter(
                Opportunity.snapshot_id == snap.id,
                *res.conditions
            )
        )
        opps = q.all()
        if not opps:
            return pd.DataFrame(), res
            
        data = []
        for o in opps:
            fc = _norm_fc(o.forecast_category)
            status = _norm_approval(o.approval_status)
                
            data.append({
                "id": o.id,
                "opportunity_id_18": o.opportunity_id_18,
                "opportunity_name": o.opportunity_name,
                "account_name": o.account_name,
                "forecast_category": fc,
                "forecast_acv_amount": float(o.forecast_acv_amount or 0),
                "approval_status": status,
                "reason_for_approval": o.extra_attributes.get("Reason for approval") if o.extra_attributes else None,
                "close_date": o.close_date,
                "sub_region": o.sub_region,
                "business_unit_primary": o.business_unit_primary
            })
        
        df = pd.DataFrame(data)
        df = df.drop_duplicates(subset=["opportunity_id_18"], keep="last")
        return df, res

    def _get_opps_df(self, snap: UploadSnapshot, filter_spec: Optional[ScopeService.FilterSpec] = None, exclude_deleted_lost: bool = False, target_date = None) -> tuple[pd.DataFrame, Any]:
        return self._scoped_opps(snap, filter_spec=filter_spec, exclude_deleted_lost=exclude_deleted_lost, target_date=target_date)


    def get_distribution(
        self,
        ctx: UserContext,
        as_of: Optional[str] = None,
        compare: Optional[str] = None,
        exclude_deleted_lost: bool = False,
        filter_spec: Optional[ScopeService.FilterSpec] = None
    ) -> dict:
        eff_as_of = as_of or (filter_spec.as_of if filter_spec else None)
        eff_compare = compare or (filter_spec.compare if filter_spec else None)
        snap = self._get_snapshot(ctx, eff_as_of)
        if not snap:
            return {"error": "No snapshot found"}

        eff_target_date = None
        if eff_as_of:
            try:
                eff_target_date = date.fromisoformat(eff_as_of)
            except ValueError:
                pass
        if not eff_target_date:
            eff_target_date = snap.snapshot_date
            
        df, res = self._get_opps_df(snap, filter_spec=filter_spec, exclude_deleted_lost=exclude_deleted_lost, target_date=eff_target_date)
        
        comp_snap = None
        if eff_compare:
            comp_snap = self._get_snapshot(ctx, eff_compare, base_snap=snap)
        comp_df, _ = self._get_opps_df(comp_snap, filter_spec=filter_spec, exclude_deleted_lost=exclude_deleted_lost, target_date=eff_target_date) if comp_snap else (pd.DataFrame(), None)
            
        snap_yest = self._get_snapshot(ctx, "yesterday", base_snap=snap)
        df_yest, _ = self._get_opps_df(snap_yest, filter_spec=filter_spec, exclude_deleted_lost=exclude_deleted_lost, target_date=eff_target_date) if snap_yest else (pd.DataFrame(), None)
        
        snap_lw = self._get_snapshot(ctx, "last_week", base_snap=snap)
        df_lw, _ = self._get_opps_df(snap_lw, filter_spec=filter_spec, exclude_deleted_lost=exclude_deleted_lost, target_date=eff_target_date) if snap_lw else (pd.DataFrame(), None)
        
        total_count = len(df)
        total_acv = _sum(df, "forecast_acv_amount") if not df.empty else 0.0
        
        all_statuses = set()
        if not df.empty:
            all_statuses.update(df["approval_status"].unique())
        all_statuses.update(FUNNEL_STAGES)
        
        statuses_list = []
        matrix = {}
        for st in all_statuses:
            st_df = df[df["approval_status"] == st] if not df.empty else pd.DataFrame()
            c = len(st_df)
            a = _sum(st_df, "forecast_acv_amount")
            if c == 0 and st not in FUNNEL_STAGES:
                continue
                
            pct_c = round((c / total_count * 100) if total_count else 0, 1)
            pct_a = round((a / total_acv * 100) if total_acv else 0, 1)
            
            def get_delta(prev_df):
                if prev_df.empty:
                    return {"count": 0, "acv": 0.0} # Fixed!
                prev_st_df = prev_df[prev_df["approval_status"] == st]
                prev_c = len(prev_st_df)
                prev_a = _sum(prev_st_df, "forecast_acv_amount")
                return {"count": c - prev_c, "acv": round(a - prev_a, 2)}
                
            delta_yest = get_delta(df_yest)
            delta_lw = get_delta(df_lw)
            delta_comp = get_delta(comp_df) if comp_snap else None
            
            statuses_list.append({
                "status": st,
                "count": c,
                "acv": round(a, 2),
                "pct_count": pct_c,
                "pct_acv": pct_a,
                "delta_yesterday": delta_yest,
                "delta_lastweek": delta_lw,
                "delta_custom": delta_comp
            })
            
            row_matrix = {}
            for fc in ALL_FC:
                fc_df = st_df[st_df["forecast_category"] == fc] if not st_df.empty else pd.DataFrame()
                row_matrix[fc] = {
                    "count": len(fc_df),
                    "acv": round(_sum(fc_df, "forecast_acv_amount"), 2)
                }
            matrix[st] = row_matrix
            
        funnel = [{"stage": "Total slice", "count": total_count, "acv": round(total_acv, 2)}]
        for st in FUNNEL_STAGES:
            st_df = df[df["approval_status"] == st] if not df.empty else pd.DataFrame()
            funnel.append({
                "stage": st,
                "count": len(st_df),
                "acv": round(_sum(st_df, "forecast_acv_amount"), 2)
            })
            
        movements = []
        def get_movements(prev_df):
            moves = []
            if not df.empty and not prev_df.empty:
                merged = pd.merge(
                    prev_df[["opportunity_id_18", "approval_status"]],
                    df[["opportunity_id_18", "approval_status", "forecast_acv_amount"]],
                    on="opportunity_id_18",
                    how="right",
                    suffixes=("_prev", "_curr")
                )
                changed = merged[merged["approval_status_prev"] != merged["approval_status_curr"]].copy()
                changed["approval_status_prev"] = changed["approval_status_prev"].fillna("New to slice")
                changed["approval_status_curr"] = changed["approval_status_curr"].fillna("Blank")
                
                grouped = changed.groupby(["approval_status_prev", "approval_status_curr"], dropna=False).agg(
                    count=("opportunity_id_18", "count"),
                    acv=("forecast_acv_amount", "sum")
                ).reset_index()
                for _, row in grouped.iterrows():
                    moves.append({
                        "from_status": row["approval_status_prev"],
                        "to_status": row["approval_status_curr"],
                        "count": int(row["count"]),
                        "acv": round(float(row["acv"]), 2)
                    })
            return moves
            
        movements_yesterday = get_movements(df_yest)
        movements_lastweek = get_movements(df_lw)
        movements_custom = get_movements(comp_df) if comp_snap else []
                
        pending_reasons = []
        pending_df = df[df["approval_status"] == "Pending Approval"] if not df.empty else pd.DataFrame()
        if not pending_df.empty and "reason_for_approval" in pending_df.columns:
            reasons = pending_df["reason_for_approval"].value_counts().reset_index()
            reasons.columns = ["reason", "count"]
            for _, r in reasons.iterrows():
                reason_val = r["reason"]
                if pd.isna(reason_val) or str(reason_val).strip() == "":
                    continue
                reason_acv = _sum(pending_df[pending_df["reason_for_approval"] == reason_val], "forecast_acv_amount")
                pending_reasons.append({
                    "reason": reason_val,
                    "count": int(r["count"]),
                    "acv": round(reason_acv, 2)
                })
                
        # Handle total deltas
        def get_total_delta(prev_df):
            if prev_df.empty:
                return {"count": 0, "acv": 0.0}
            return {"count": total_count - len(prev_df), "acv": round(total_acv - _sum(prev_df, "forecast_acv_amount"), 2)}
            
        return {
            "snapshot_date": snap.snapshot_date.isoformat(),
            "requested_as_of": eff_as_of or snap.snapshot_date.isoformat(),
            "compare_date": comp_snap.snapshot_date.isoformat() if comp_snap else None,
            "yesterday_date": snap_yest.snapshot_date.isoformat() if snap_yest else None,
            "lastweek_date": snap_lw.snapshot_date.isoformat() if snap_lw else None,
            "data_slice": res.label if res else ScopeService.quarter_label(ScopeService.current_quarter(snap.snapshot_date)),
            "data_slice_key": res.period if res else ScopeService.current_quarter(snap.snapshot_date),
            "filters_applied": res.filters_applied if res else {},
            "total": {
                "count": total_count,
                "acv": round(total_acv, 2),
                "delta_yesterday": get_total_delta(df_yest),
                "delta_lastweek": get_total_delta(df_lw),
                "delta_custom": get_total_delta(comp_df) if comp_snap else None
            },
            "statuses": statuses_list,
            "matrix": matrix,
            "categories": ALL_FC,
            "funnel": funnel,
            "movements_yesterday": movements_yesterday,
            "movements_lastweek": movements_lastweek,
            "movements_custom": movements_custom,
            "pending_deals": [{
                "opportunity_name": r["opportunity_name"],
                "account_name": r["account_name"],
                "forecast_acv_amount": float(r["forecast_acv_amount"] or 0),
                "close_date": r["close_date"].isoformat() if r["close_date"] else None,
                "reason_for_approval": r["reason_for_approval"] if "reason_for_approval" in r and pd.notna(r["reason_for_approval"]) else None
            } for _, r in pending_df.sort_values("forecast_acv_amount", ascending=False).iterrows()] if not pending_df.empty else []
        }

    def get_deals(
        self,
        ctx: UserContext,
        status: Optional[str] = None,
        category: Optional[str] = None,
        as_of: Optional[str] = None,
        exclude_deleted_lost: bool = False,
        region: Optional[str] = None,
        business_unit: Optional[str] = None,
        filter_spec: Optional[ScopeService.FilterSpec] = None
    ) -> dict:
        eff_as_of = as_of or (filter_spec.as_of if filter_spec else None)
        snap = self._get_snapshot(ctx, eff_as_of)
        if not snap:
            return {"count": 0, "acv": 0.0, "filters_applied": {}, "deals": []}
            
        df, res = self._get_opps_df(snap, filter_spec=filter_spec, exclude_deleted_lost=exclude_deleted_lost, target_date=snap.snapshot_date)
        if df.empty:
            return {"count": 0, "acv": 0.0, "filters_applied": res.filters_applied if res else {}, "deals": []}
            
        filters_applied = dict(res.filters_applied) if res else {}
        if status:
            df = df[df["approval_status"] == status]
            filters_applied["status"] = status
        if category:
            df = df[df["forecast_category"] == category]
            filters_applied["category"] = category
        if region:
            df = df[df["sub_region"] == region]
            filters_applied["region"] = region
        if business_unit:
            df = df[df["business_unit_primary"] == business_unit]
            filters_applied["business_unit"] = business_unit
            
        count = len(df)
        acv = round(_sum(df, "forecast_acv_amount"), 2)
        
        deals = []
        for _, r in df.iterrows():
            def _clean(val):
                return None if pd.isna(val) else val
            deals.append({
                "id": _clean(r["id"]),
                "opportunity_id_18": _clean(r["opportunity_id_18"]),
                "opportunity_name": _clean(r["opportunity_name"]),
                "account_name": _clean(r["account_name"]),
                "forecast_category": _clean(r["forecast_category"]),
                "forecast_acv_amount": float(_clean(r["forecast_acv_amount"]) or 0),
                "approval_status": _clean(r["approval_status"]),
                "reason_for_approval": _clean(r["reason_for_approval"]),
                "sub_region": _clean(r["sub_region"]),
                "business_unit_primary": _clean(r["business_unit_primary"]),
                "close_date": r["close_date"].isoformat() if _clean(r["close_date"]) else None
            })
            
        return {
            "count": count,
            "acv": acv,
            "filters_applied": filters_applied,
            "deals": deals
        }
