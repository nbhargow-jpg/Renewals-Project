from __future__ import annotations
import logging
import re
from datetime import date
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

class V2ExpiryService:
    def __init__(self, db: Session):
        self.db = db

    def _get_snapshot(self, ctx: UserContext, target_date: Optional[str] = None) -> Optional[UploadSnapshot]:
        q = self.db.query(UploadSnapshot)
        if target_date:
            if target_date == "yesterday":
                latest = q.order_by(UploadSnapshot.snapshot_date.desc()).first()
                if not latest: return None
                return q.filter(UploadSnapshot.snapshot_date < latest.snapshot_date).order_by(UploadSnapshot.snapshot_date.desc()).first()
            elif target_date == "last_week":
                latest = q.order_by(UploadSnapshot.snapshot_date.desc()).first()
                if not latest: return None
                target = latest.snapshot_date - pd.Timedelta(days=7)
                return q.filter(UploadSnapshot.snapshot_date <= target).order_by(UploadSnapshot.snapshot_date.desc()).first()
            else:
                try:
                    d = date.fromisoformat(target_date)
                    return q.filter(UploadSnapshot.snapshot_date <= d).order_by(UploadSnapshot.snapshot_date.desc()).first()
                except ValueError:
                    return None
        return q.order_by(UploadSnapshot.snapshot_date.desc()).first()

    def _window_opps(self, snap: UploadSnapshot, filter_spec: Optional[ScopeService.FilterSpec] = None, exclude_deleted_lost: bool = False) -> tuple[pd.DataFrame, list[str]]:
        from backend.services.scopes import FilterSpec
        fs = filter_spec.model_copy() if filter_spec else FilterSpec()
        if exclude_deleted_lost:
            fs.include_deleted_lost = False
            
        # We want to apply all FilterSpec conditions EXCEPT period (since expiry organizes by service expiry year)
        # We can construct conditions using FilterSpec with period="all_periods"
        fs_for_expiry = fs.model_copy()
        fs_for_expiry.period = "all_periods"
        res = ScopeService.resolve(fs_for_expiry, snapshot=snap, as_of_date=snap.snapshot_date)
        
        q = self.db.query(Opportunity).filter(
            Opportunity.snapshot_id == snap.id,
            *res.conditions
        )
        
        opps = q.all()
        if not opps:
            return pd.DataFrame(), []
            
        data = []
        years_found = set()
        for o in opps:
            fc = o.forecast_category if o.forecast_category in ALL_FC else "Blank"
            if not o.forecast_category or str(o.forecast_category).strip() == "":
                fc = "Blank"
            elif o.forecast_category not in ["Closed", "Commit", "Best Case", "Pipeline"]:
                fc = "Blank"
                
            sep = o.service_expiry_period or "Blank"
            if sep and "-" in sep:
                try:
                    parts = sep.split("-")
                    if len(parts) == 2 and parts[1].isdigit():
                        years_found.add(parts[1])
                except:
                    pass
                    
            data.append({
                "id": o.id,
                "opportunity_id_18": o.opportunity_id_18,
                "forecast_category": fc,
                "forecast_acv_amount": float(o.forecast_acv_amount or 0),
                "service_expiry_period": sep,
                "close_date": o.close_date
            })
        
        df = pd.DataFrame(data)
        df = df.drop_duplicates(subset=["opportunity_id_18"], keep="last")
        sorted_years = sorted(list(years_found))
        return df, sorted_years

    def get_summary(
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
            
        df, years_found = self._window_opps(snap, filter_spec=filter_spec, exclude_deleted_lost=exclude_deleted_lost)
        
        eff_date = snap.snapshot_date
        if eff_as_of:
            try:
                eff_date = date.fromisoformat(eff_as_of)
            except ValueError:
                pass
        target_quarter = ScopeService.current_quarter(eff_date)
        _, current_y_str = target_quarter.split("-") if (target_quarter and "-" in target_quarter) else ("", "2026")
        next_y_str = str(int(current_y_str) + 1)
        default_years = [current_y_str, next_y_str]
        
        fs_period = (filter_spec.period if filter_spec and filter_spec.period else "current_quarter").strip()
        if fs_period == "all_periods" or fs_period == "all":
            years_to_use = sorted(years_found) if years_found else default_years
        elif fs_period.upper().startswith("FY"):
            years_to_use = [fs_period[2:]]
        elif re.match(r"^Q[1-4]-\d{4}$", fs_period, re.IGNORECASE):
            years_to_use = [fs_period.split("-")[1]]
        else:
            # Default Expiry window: current FY + next FY
            years_to_use = default_years
            
        comp_snap = None
        if eff_compare:
            comp_snap = self._get_snapshot(ctx, eff_compare)
        comp_df = pd.DataFrame()
        if comp_snap:
            comp_df, _ = self._window_opps(comp_snap, filter_spec=filter_spec, exclude_deleted_lost=exclude_deleted_lost)
            
        snap_yest = self._get_snapshot(ctx, "yesterday")
        df_yest, _ = self._window_opps(snap_yest, filter_spec=filter_spec, exclude_deleted_lost=exclude_deleted_lost) if snap_yest else (pd.DataFrame(), [])
        
        snap_lw = self._get_snapshot(ctx, "last_week")
        df_lw, _ = self._window_opps(snap_lw, filter_spec=filter_spec, exclude_deleted_lost=exclude_deleted_lost) if snap_lw else (pd.DataFrame(), [])
        
        quarters = []
        for y_str in years_to_use:
            for q in range(1, 5):
                key = f"Q{q}-{y_str}"
                label = ScopeService.quarter_label(key)
                quarters.append({"key": key, "label": label, "fy": y_str})
                
        def build_grid(target_df: pd.DataFrame, y_label: str):
            rows = []
            fy_qs = [q for q in quarters if q["fy"] == y_label]
            grid_count = 0
            grid_acv = 0.0
            cat_totals = {fc: {"count": 0, "acv": 0.0} for fc in ALL_FC}
            
            for q in fy_qs:
                cells = {}
                row_count = 0
                row_acv = 0.0
                q_df = target_df[target_df["service_expiry_period"] == q["key"]] if not target_df.empty else pd.DataFrame()
                
                for fc in ALL_FC:
                    fc_df = q_df[q_df["forecast_category"] == fc] if not q_df.empty else pd.DataFrame()
                    c = len(fc_df)
                    a = round(_sum(fc_df, "forecast_acv_amount"), 2)
                    cells[fc] = {"count": c, "acv": a}
                    row_count += c
                    row_acv += a
                    
                    cat_totals[fc]["count"] += c
                    cat_totals[fc]["acv"] += a
                    
                rows.append({
                    "quarter": q["key"],
                    "label": q["label"],
                    "cells": cells,
                    "total": {"count": row_count, "acv": round(row_acv, 2)}
                })
                grid_count += row_count
                grid_acv += row_acv
                
            return {
                "rows": rows,
                "totals": {
                    "category": cat_totals,
                    "grand": {"count": grid_count, "acv": round(grid_acv, 2)}
                }
            }
            
        grids = {}
        cgrids = {}
        yest_grids = {}
        lw_grids = {}
        deltas = {}
        acv_by_year = {}
        grand_total_count = 0
        grand_total_acv = 0.0

        def compute_deltas(grid, cgrid):
            deltas = {
                "grand": {
                    "count": grid["totals"]["grand"]["count"] - cgrid["totals"]["grand"]["count"], 
                    "acv": round(grid["totals"]["grand"]["acv"] - cgrid["totals"]["grand"]["acv"], 2)
                },
                "category": {},
                "quarters": {}
            }
            for fc in ALL_FC:
                deltas["category"][fc] = {
                    "count": grid["totals"]["category"][fc]["count"] - cgrid["totals"]["category"][fc]["count"],
                    "acv": round(grid["totals"]["category"][fc]["acv"] - cgrid["totals"]["category"][fc]["acv"], 2)
                }
            for i, r in enumerate(grid["rows"]):
                cr = cgrid["rows"][i]
                deltas["quarters"][r["quarter"]] = {
                    "count": r["total"]["count"] - cr["total"]["count"],
                    "acv": round(r["total"]["acv"] - cr["total"]["acv"], 2)
                }
            return deltas

        for y_label in years_to_use:
            g = build_grid(df, y_label)
            grids[y_label] = g
            acv_by_year[y_label] = g["totals"]["grand"]
            grand_total_count += g["totals"]["grand"]["count"]
            grand_total_acv += g["totals"]["grand"]["acv"]
            
            cg = build_grid(comp_df, y_label) if not comp_df.empty else build_grid(pd.DataFrame(), y_label)
            yg = build_grid(df_yest, y_label) if not df_yest.empty else build_grid(pd.DataFrame(), y_label)
            lg = build_grid(df_lw, y_label) if not df_lw.empty else build_grid(pd.DataFrame(), y_label)
            
            y_deltas = {
                "yesterday": compute_deltas(g, yg),
                "lastweek": compute_deltas(g, lg)
            }
            if eff_compare:
                y_deltas["custom"] = compute_deltas(g, cg)
            deltas[y_label] = y_deltas
            
        _, fy_end_date = ScopeService.quarter_bounds(f"Q4-{current_y_str}")
        grid_quarters = [q["key"] for q in quarters]
        grid_df = df[df["service_expiry_period"].isin(grid_quarters)] if not df.empty else pd.DataFrame()
        slip_df = grid_df[grid_df["close_date"] > fy_end_date] if not grid_df.empty else pd.DataFrame()
        slip_count = len(slip_df)
        slip_acv = _sum(slip_df, "forecast_acv_amount")
        
        slip_by_quarter = []
        if not slip_df.empty:
            for q in quarters:
                q_slip = slip_df[slip_df["service_expiry_period"] == q["key"]]
                if not q_slip.empty:
                    slip_by_quarter.append({
                        "quarter": q["key"],
                        "count": len(q_slip),
                        "acv": round(_sum(q_slip, "forecast_acv_amount"), 2)
                    })
        
        from backend.services.scopes import FilterSpec
        fs = filter_spec.model_copy() if filter_spec else FilterSpec()
        res = ScopeService.resolve(fs, snapshot=snap, as_of_date=eff_date)

        return {
            "snapshot_date": snap.snapshot_date.isoformat(),
            "requested_as_of": eff_as_of or snap.snapshot_date.isoformat(),
            "compare_date": comp_snap.snapshot_date.isoformat() if comp_snap else None,
            "data_slice": res.label,
            "data_slice_key": target_quarter,
            "filters_applied": res.filters_applied,
            "fiscal_years": [
                {"label": y_label, "quarters": [{"key": q["key"], "label": q["label"]} for q in quarters if q["fy"] == y_label]}
                for y_label in years_to_use
            ],
            "categories": ALL_FC,
            "grids": grids,
            "acv_by_year": acv_by_year,
            "grand_total": {
                "count": grand_total_count,
                "acv": round(grand_total_acv, 2)
            },
            "slippage": {
                "count": slip_count,
                "acv": round(slip_acv, 2),
                "by_quarter": slip_by_quarter
            },
            "deltas": deltas
        }
        
    def get_deals(
        self,
        ctx: UserContext,
        quarter: Optional[str] = None,
        category: Optional[str] = None,
        as_of: Optional[str] = None,
        exclude_deleted_lost: bool = False,
        slippage: bool = False,
        filter_spec: Optional[ScopeService.FilterSpec] = None
    ) -> list[dict]:
        eff_as_of = as_of or (filter_spec.as_of if filter_spec else None)
        snap = self._get_snapshot(ctx, eff_as_of)
        if not snap:
            return []
            
        from backend.services.scopes import FilterSpec
        fs = filter_spec.model_copy() if filter_spec else FilterSpec()
        if exclude_deleted_lost:
            fs.include_deleted_lost = False
        fs_for_expiry = fs.model_copy()
        fs_for_expiry.period = "all_periods"
        res = ScopeService.resolve(fs_for_expiry, snapshot=snap, as_of_date=snap.snapshot_date)
        
        q = self.db.query(Opportunity).filter(
            Opportunity.snapshot_id == snap.id,
            *res.conditions
        )
            
        target_quarter = ScopeService.current_quarter(snap.snapshot_date)
        _, current_y_str = target_quarter.split("-") if (target_quarter and "-" in target_quarter) else ("", "2026")
        next_y_str = str(int(current_y_str) + 1)
        default_grid_quarters = [f"Q{q}-{y}" for y in [current_y_str, next_y_str] for q in range(1, 5)]

        if slippage:
            _, fy_end_date = ScopeService.quarter_bounds(f"Q4-{current_y_str}")
            q = q.filter(Opportunity.close_date > fy_end_date, Opportunity.service_expiry_period.in_(default_grid_quarters))

        if quarter:
            q = q.filter(Opportunity.service_expiry_period == quarter)
        elif not slippage:
            # Default Expiry window: current FY + next FY
            q = q.filter(Opportunity.service_expiry_period.in_(default_grid_quarters))
        if category:
            if category == "Blank":
                q = q.filter(or_(Opportunity.forecast_category == None, Opportunity.forecast_category == "", ~Opportunity.forecast_category.in_(["Closed", "Commit", "Best Case", "Pipeline"])))
            else:
                q = q.filter(Opportunity.forecast_category == category)
                
        opps = q.all()
        seen = set()
        deduped = []
        for o in reversed(opps): 
            if o.opportunity_id_18 not in seen:
                seen.add(o.opportunity_id_18)
                deduped.append(o)
        
        def to_dict(o):
            return {
                "id": o.id,
                "opportunity_id_18": o.opportunity_id_18,
                "opportunity_name": o.opportunity_name,
                "account_name": o.account_name,
                "forecast_category": o.forecast_category,
                "forecast_acv_amount": float(o.forecast_acv_amount or 0),
                "approval_status": o.approval_status,
                "sub_region": o.sub_region,
                "business_unit_primary": o.business_unit_primary,
                "service_expiry_period": o.service_expiry_period,
                "close_date": o.close_date.isoformat() if o.close_date else None
            }
        return [to_dict(o) for o in reversed(deduped)]