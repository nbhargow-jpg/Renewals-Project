from __future__ import annotations
import logging
import pandas as pd
from datetime import date, timedelta
from typing import Optional, Any
from sqlalchemy.orm import Session

from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot
from backend.services.context import UserContext
from backend.services.scopes import ScopeService

log = logging.getLogger(__name__)

ALL_FC = ["Closed", "Commit", "Best Case", "Pipeline", "Blank"]
FUNNEL_STAGES = ["Approved", "Pending Approval", "Blank"]
REGION_ORDER = ["North America", "LATAM", "Middle East and North Africa", "APAC", "Europe", "Africa"]

def _sum(df: pd.DataFrame, col: str) -> float:
    if df.empty or col not in df.columns:
        return 0.0
    return float(df[col].sum())

def _norm_fc(s: str | None) -> str:
    if not s or str(s).strip() in ("", "nan", "None"):
        return "Blank"
    s = str(s).strip()
    if s not in ["Closed", "Commit", "Best Case", "Pipeline"]:
        return "Blank"
    return s

def _norm_approval(s: str | None) -> str:
    if not s or str(s).strip() in ("", "nan", "None", "Blank"):
        return "Blank"
    s = str(s).strip()
    if s in ("Approved", "Approved - 2nd"):
        return "Approved"
    if s in ("Pending Approval", "Pending-Approval"):
        return "Pending Approval"
    return s

def _map_region(s: str | None) -> str:
    if not s or str(s).strip() in ("", "nan", "None"):
        return "Other"
    s = str(s).strip()
    if s == "Europe": return "Europe"
    if s == "APAC": return "APAC"
    if s == "AFRICA": return "Africa"
    if s == "MENA": return "Middle East and North Africa"
    if s == "NAMR": return "North America"
    if s == "South America": return "LATAM"
    return "Other"

def _opps_to_df(opps: list[Opportunity]) -> pd.DataFrame:
    if not opps:
        return pd.DataFrame()
    records = []
    for o in opps:
        records.append({
            "opportunity_id_18": o.opportunity_id_18,
            "opportunity_name": o.opportunity_name,
            "account_name": o.account_name,
            "forecast_acv_amount": float(o.forecast_acv_amount or 0.0),
            "forecast_category": _norm_fc(o.forecast_category),
            "business_unit": (o.business_unit_primary or "").strip() or "Unassigned",
            "is_deleted_or_lost": bool(o.is_deleted_or_lost),
            "fiscal_period": o.fiscal_period or "",
            "close_date": o.close_date,
            "approval_status": _norm_approval(o.approval_status),
            "region": _map_region(o.revised_sub_region),
            "raw_sub_region": o.revised_sub_region or "",
        })
    df = pd.DataFrame(records)
    df = df.drop_duplicates(subset=["opportunity_id_18"], keep="last")
    return df

class V2RegionsService:
    def __init__(self, db: Session):
        self.db = db

    def _active_snap(self, as_of: str | None = None) -> UploadSnapshot | None:
        q = self.db.query(UploadSnapshot)
        if as_of:
            try:
                d = date.fromisoformat(as_of)
                return q.filter(UploadSnapshot.snapshot_date <= d).order_by(UploadSnapshot.snapshot_date.desc()).first()
            except ValueError:
                pass
        return (
            q.filter(UploadSnapshot.is_active_today == True)
            .order_by(UploadSnapshot.snapshot_date.desc())
            .first()
        )

    def _snap_by_date(self, d: date) -> UploadSnapshot | None:
        return self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == d).first()

    def _scoped_opps(self, snap: UploadSnapshot, filter_spec: Optional[ScopeService.FilterSpec] = None, exclude_deleted: bool = False, target_date = None) -> tuple[list[Opportunity], Any]:
        from backend.services.scopes import FilterSpec
        eff_date = target_date
        if not eff_date and filter_spec and filter_spec.as_of:
            try:
                eff_date = date.fromisoformat(filter_spec.as_of)
            except ValueError:
                pass
        if not eff_date:
            eff_date = snap.snapshot_date
        fs = filter_spec.model_copy() if filter_spec else FilterSpec()
        if exclude_deleted:
            fs.include_deleted_lost = False
        res = ScopeService.resolve(fs, snapshot=snap, as_of_date=eff_date)
        q = (
            self.db.query(Opportunity)
            .filter(
                Opportunity.snapshot_id == snap.id,
                *res.conditions
            )
        )
        return q.all(), res

    def _q4_opps(self, snap: UploadSnapshot, exclude_deleted: bool = False, target_date = None) -> list[Opportunity]:
        opps, _ = self._scoped_opps(snap, exclude_deleted=exclude_deleted, target_date=target_date)
        return opps


    def _yesterday_snap(self, snap: UploadSnapshot) -> UploadSnapshot | None:
        return (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.snapshot_date < snap.snapshot_date)
            .order_by(UploadSnapshot.snapshot_date.desc())
            .first()
        )

    def _lastweek_snap(self, snap: UploadSnapshot) -> UploadSnapshot | None:
        target = snap.snapshot_date - timedelta(days=7)
        return (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.snapshot_date <= target)
            .order_by(UploadSnapshot.snapshot_date.desc())
            .first()
        )

    def get_summary(self, ctx: UserContext, as_of: Optional[str] = None, compare: Optional[str] = None, exclude_deleted_lost: bool = False, filter_spec: Optional[ScopeService.FilterSpec] = None) -> dict:
        from backend.services.scopes import FilterSpec
        fs = filter_spec.model_copy() if filter_spec else FilterSpec()
        if as_of:
            fs.as_of = as_of
        if compare:
            fs.compare = compare
        if exclude_deleted_lost:
            fs.include_deleted_lost = False

        snap = self._active_snap(fs.as_of)
        if not snap:
            return {"error": "no_snapshot"}

        eff_as_of_date = None
        if fs.as_of:
            try:
                eff_as_of_date = date.fromisoformat(fs.as_of)
            except ValueError:
                pass
        if not eff_as_of_date:
            eff_as_of_date = snap.snapshot_date

        opps, res = self._scoped_opps(snap, filter_spec=fs, target_date=eff_as_of_date)
        df = _opps_to_df(opps)

        y_snap = self._yesterday_snap(snap)
        lw_snap = self._lastweek_snap(snap)

        y_opps, _ = self._scoped_opps(y_snap, filter_spec=fs, target_date=eff_as_of_date) if y_snap else ([], None)
        lw_opps, _ = self._scoped_opps(lw_snap, filter_spec=fs, target_date=eff_as_of_date) if lw_snap else ([], None)
        y_df = _opps_to_df(y_opps)
        lw_df = _opps_to_df(lw_opps)

        grand_count = len(df)
        grand_acv = float(df["forecast_acv_amount"].sum()) if not df.empty else 0.0

        def _get_region_data(df_in: pd.DataFrame) -> dict:
            res = {}
            if df_in.empty: return res
            for r, grp in df_in.groupby("region"):
                res[r] = {
                    "count": len(grp),
                    "acv": float(grp["forecast_acv_amount"].sum()),
                    "cells": {fc: {"count": len(grp[grp["forecast_category"] == fc]), "acv": float(grp[grp["forecast_category"] == fc]["forecast_acv_amount"].sum())} for fc in ALL_FC},
                    "approval": {st: {"count": len(grp[grp["approval_status"] == st]), "acv": float(grp[grp["approval_status"] == st]["forecast_acv_amount"].sum())} for st in FUNNEL_STAGES}
                }
            return res

        today_reg = _get_region_data(df)
        y_reg = _get_region_data(y_df)
        lw_reg = _get_region_data(lw_df)

        regions_out = []
        for reg_name in REGION_ORDER + ["Other"]:
            if reg_name == "Other" and (reg_name not in today_reg or today_reg[reg_name]["count"] == 0):
                continue
            if reg_name not in today_reg and reg_name != "Other":
                today_reg[reg_name] = {"count": 0, "acv": 0.0, "cells": {fc: {"count": 0, "acv": 0.0} for fc in ALL_FC}, "approval": {st: {"count": 0, "acv": 0.0} for st in FUNNEL_STAGES}}

            d_today = today_reg.get(reg_name, {"count": 0, "acv": 0.0, "cells": {fc: {"count": 0, "acv": 0.0} for fc in ALL_FC}, "approval": {st: {"count": 0, "acv": 0.0} for st in FUNNEL_STAGES}})
            d_y = y_reg.get(reg_name, {"count": 0, "acv": 0.0, "cells": {fc: {"count": 0, "acv": 0.0} for fc in ALL_FC}})
            d_lw = lw_reg.get(reg_name, {"count": 0, "acv": 0.0, "cells": {fc: {"count": 0, "acv": 0.0} for fc in ALL_FC}})

            pct_acv = round((d_today["acv"] / grand_acv * 100) if grand_acv else 0, 1)
            commit_acv = d_today["cells"]["Commit"]["acv"] + d_today["cells"]["Closed"]["acv"]
            commit_pct = round((commit_acv / d_today["acv"] * 100) if d_today["acv"] else 0, 1)

            regions_out.append({
                "region": reg_name,
                "count": d_today["count"],
                "acv": round(d_today["acv"], 2),
                "pct_acv": pct_acv,
                "commit_pct": commit_pct,
                "cells": {k: {"count": v["count"], "acv": round(v["acv"], 2)} for k, v in d_today["cells"].items()},
                "approval": {k: {"count": v["count"], "acv": round(v["acv"], 2)} for k, v in d_today["approval"].items()},
                "delta_yesterday": {"count": d_today["count"] - d_y["count"], "acv": round(d_today["acv"] - d_y["acv"], 2)},
                "delta_lastweek": {"count": d_today["count"] - d_lw["count"], "acv": round(d_today["acv"] - d_lw["acv"], 2)}
            })

        fc_totals = {}
        for fc in ALL_FC:
            fc_df = df[df["forecast_category"] == fc] if not df.empty else pd.DataFrame()
            fc_y = y_df[y_df["forecast_category"] == fc] if not y_df.empty else pd.DataFrame()
            fc_lw = lw_df[lw_df["forecast_category"] == fc] if not lw_df.empty else pd.DataFrame()
            fc_totals[fc] = {
                "count": len(fc_df),
                "acv": round(float(fc_df["forecast_acv_amount"].sum()) if not fc_df.empty else 0.0, 2),
                "delta_yesterday": {"count": len(fc_df) - len(fc_y), "acv": round(float(fc_df["forecast_acv_amount"].sum() if not fc_df.empty else 0.0) - float(fc_y["forecast_acv_amount"].sum() if not fc_y.empty else 0.0), 2)},
                "delta_lastweek": {"count": len(fc_df) - len(fc_lw), "acv": round(float(fc_df["forecast_acv_amount"].sum() if not fc_df.empty else 0.0) - float(fc_lw["forecast_acv_amount"].sum() if not fc_lw.empty else 0.0), 2)},
            }

        app_totals = {}
        for st in FUNNEL_STAGES:
            st_df = df[df["approval_status"] == st] if not df.empty else pd.DataFrame()
            st_y = y_df[y_df["approval_status"] == st] if not y_df.empty else pd.DataFrame()
            st_lw = lw_df[lw_df["approval_status"] == st] if not lw_df.empty else pd.DataFrame()
            app_totals[st] = {
                "count": len(st_df),
                "acv": round(float(st_df["forecast_acv_amount"].sum()) if not st_df.empty else 0.0, 2),
                "delta_yesterday": {"count": len(st_df) - len(st_y), "acv": round(float(st_df["forecast_acv_amount"].sum() if not st_df.empty else 0.0) - float(st_y["forecast_acv_amount"].sum() if not st_y.empty else 0.0), 2)},
                "delta_lastweek": {"count": len(st_df) - len(st_lw), "acv": round(float(st_df["forecast_acv_amount"].sum() if not st_df.empty else 0.0) - float(st_lw["forecast_acv_amount"].sum() if not st_lw.empty else 0.0), 2)},
            }

        unmapped = {"count": 0, "acv": 0.0, "values": []}
        if not df.empty:
            other_df = df[df["region"] == "Other"]
            unmapped["count"] = len(other_df)
            unmapped["acv"] = round(float(other_df["forecast_acv_amount"].sum()), 2)
            unmapped["values"] = sorted(list(set([str(x) for x in other_df["raw_sub_region"].unique() if pd.notna(x) and x != ""])))

        return {
            "snapshot_date": snap.snapshot_date.isoformat(),
            "requested_as_of": fs.as_of or snap.snapshot_date.isoformat(),
            "yesterday_date": y_snap.snapshot_date.isoformat() if y_snap else None,
            "lastweek_date": lw_snap.snapshot_date.isoformat() if lw_snap else None,
            "data_slice": res.data_slice,
            "data_slice_key": res.resolved_quarter,
            "filters_applied": res.filters_applied,
            "total": {
                "count": grand_count,
                "acv": round(grand_acv, 2),
                "delta_yesterday": {"count": grand_count - len(y_df), "acv": round(grand_acv - float(y_df["forecast_acv_amount"].sum() if not y_df.empty else 0.0), 2)},
                "delta_lastweek": {"count": grand_count - len(lw_df), "acv": round(grand_acv - float(lw_df["forecast_acv_amount"].sum() if not lw_df.empty else 0.0), 2)},
            },
            "regions": regions_out,
            "totals": {
                "categories": fc_totals,
                "approval": app_totals,
            },
            "unmapped": unmapped
        }

    def get_region_summary(self, ctx: UserContext, region: str, as_of: Optional[str] = None, exclude_deleted_lost: bool = False) -> dict:
        base = self.get_summary(ctx, as_of=as_of, exclude_deleted_lost=exclude_deleted_lost)
        if "error" in base:
            return base

        reg_data = next((r for r in base["regions"] if r["region"] == region), None)
        if not reg_data:
            return {"error": "not_found"}

        snap = self._active_snap(as_of)
        eff_date = snap.snapshot_date
        if as_of:
            try: eff_date = date.fromisoformat(as_of)
            except ValueError: pass
        
        opps = self._q4_opps(snap, exclude_deleted=exclude_deleted_lost, target_date=eff_date)
        df = _opps_to_df(opps)
        
        reg_df = df[df["region"] == region] if not df.empty else pd.DataFrame()
        bus = []
        if not reg_df.empty:
            for bu, grp in reg_df.groupby("business_unit"):
                bus.append({
                    "bu": bu,
                    "count": len(grp),
                    "acv": round(float(grp["forecast_acv_amount"].sum()), 2)
                })
        bus.sort(key=lambda x: x["acv"], reverse=True)

        reg_data["business_units"] = bus
        return reg_data

    def get_movements(self, ctx: UserContext, region: str, compare: str = "yesterday", exclude_deleted_lost: bool = False) -> dict:
        snap = self._active_snap()
        if not snap: return {"error": "no_snapshot"}

        comp_snap = self._yesterday_snap(snap) if compare == "yesterday" else self._lastweek_snap(snap)
        if not comp_snap:
            return {"category_moves": [], "approval_moves": [], "new_to_slice": [], "slipped_out": []}

        target_fp = ScopeService.current_quarter(snap.snapshot_date)
        
        t_opps = self._q4_opps(snap, exclude_deleted=exclude_deleted_lost, target_date=snap.snapshot_date)
        c_opps = self._q4_opps(comp_snap, exclude_deleted=exclude_deleted_lost, target_date=snap.snapshot_date)
        
        t_df = _opps_to_df(t_opps)
        c_df = _opps_to_df(c_opps)

        t_reg = t_df[t_df["region"] == region] if not t_df.empty else pd.DataFrame()
        c_reg = c_df[c_df["region"] == region] if not c_df.empty else pd.DataFrame()

        t_idx = set(t_reg["opportunity_id_18"].tolist()) if not t_reg.empty else set()
        c_idx = set(c_reg["opportunity_id_18"].tolist()) if not c_reg.empty else set()

        # new to slice (in t but not c)
        new_ids = t_idx - c_idx
        new_list = []
        if new_ids:
            for i in new_ids:
                row = t_reg[t_reg["opportunity_id_18"] == i].iloc[0]
                new_list.append({
                    "opportunity_id_18": i,
                    "opportunity_name": row["opportunity_name"],
                    "account_name": row["account_name"],
                    "forecast_acv_amount": float(row["forecast_acv_amount"]),
                    "forecast_category": row["forecast_category"]
                })
        
        # slipped out (in c but not t)
        slip_ids = c_idx - t_idx
        slip_list = []
        if slip_ids:
            for i in slip_ids:
                row = c_reg[c_reg["opportunity_id_18"] == i].iloc[0]
                slip_list.append({
                    "opportunity_id_18": i,
                    "opportunity_name": row["opportunity_name"],
                    "account_name": row["account_name"],
                    "forecast_acv_amount": float(row["forecast_acv_amount"]),
                    "forecast_category": row["forecast_category"]
                })

        cat_moves = []
        app_moves = []
        common_ids = t_idx.intersection(c_idx)
        for i in common_ids:
            t_row = t_reg[t_reg["opportunity_id_18"] == i].iloc[0]
            c_row = c_reg[c_reg["opportunity_id_18"] == i].iloc[0]
            
            if t_row["forecast_category"] != c_row["forecast_category"]:
                cat_moves.append({
                    "from_category": c_row["forecast_category"],
                    "to_category": t_row["forecast_category"],
                    "count": 1,
                    "acv": float(t_row["forecast_acv_amount"]),
                    "deals": [{
                        "opportunity_id_18": i,
                        "opportunity_name": t_row["opportunity_name"],
                        "account_name": t_row["account_name"],
                        "forecast_acv_amount": float(t_row["forecast_acv_amount"]),
                    }]
                })
            
            if t_row["approval_status"] != c_row["approval_status"]:
                app_moves.append({
                    "from_status": c_row["approval_status"],
                    "to_status": t_row["approval_status"],
                    "count": 1,
                    "acv": float(t_row["forecast_acv_amount"]),
                    "deals": [{
                        "opportunity_id_18": i,
                        "opportunity_name": t_row["opportunity_name"],
                        "account_name": t_row["account_name"],
                        "forecast_acv_amount": float(t_row["forecast_acv_amount"]),
                    }]
                })
        
        c_agg = {}
        for m in cat_moves:
            k = (m["from_category"], m["to_category"])
            if k not in c_agg:
                c_agg[k] = {"from_category": k[0], "to_category": k[1], "count": 0, "acv": 0.0, "deals": []}
            c_agg[k]["count"] += 1
            c_agg[k]["acv"] = round(c_agg[k]["acv"] + m["acv"], 2)
            c_agg[k]["deals"].extend(m["deals"])
            
        a_agg = {}
        for m in app_moves:
            k = (m["from_status"], m["to_status"])
            if k not in a_agg:
                a_agg[k] = {"from_status": k[0], "to_status": k[1], "count": 0, "acv": 0.0, "deals": []}
            a_agg[k]["count"] += 1
            a_agg[k]["acv"] = round(a_agg[k]["acv"] + m["acv"], 2)
            a_agg[k]["deals"].extend(m["deals"])

        return {
            "category_moves": list(c_agg.values()),
            "approval_moves": list(a_agg.values()),
            "new_to_slice": {"count": len(new_list), "acv": round(sum(d["forecast_acv_amount"] for d in new_list), 2), "deals": new_list},
            "slipped_out": {"count": len(slip_list), "acv": round(sum(d["forecast_acv_amount"] for d in slip_list), 2), "deals": slip_list}
        }

    def get_deals(self, ctx: UserContext, region: str = "", category: str = "", status: str = "", bu: str = "", as_of: str = "", filter_spec: Optional[ScopeService.FilterSpec] = None) -> dict:
        from backend.services.scopes import FilterSpec
        fs = filter_spec.model_copy() if filter_spec else FilterSpec()
        if as_of: fs.as_of = as_of
        if region: fs.regions = [region]
        if category: fs.forecast_categories = [category]
        if status: fs.approval_statuses = [status]
        if bu: fs.business_units = [bu]

        snap = self._active_snap(fs.as_of)
        if not snap: return {"error": "no_snapshot"}
            
        opps, res = self._scoped_opps(snap, filter_spec=fs)
        df = _opps_to_df(opps)
                
        deals = df.to_dict("records") if not df.empty else []
        for d in deals:
            d["id"] = d["opportunity_id_18"]
        return {
            "count": len(deals),
            "acv": round(float(df["forecast_acv_amount"].sum()) if not df.empty else 0.0, 2),
            "filters_applied": res.filters_applied,
            "deals": deals
        }

    def get_top_opportunities(self, ctx: UserContext, region: str, limit: int = 10) -> list[dict]:
        snap = self._active_snap()
        if not snap: return []
        
        opps = self._q4_opps(snap, exclude_deleted=True, target_date=snap.snapshot_date)
        df = _opps_to_df(opps)
        
        if df.empty: return []
        df = df[df["region"] == region]
        df = df.sort_values(by="forecast_acv_amount", ascending=False).head(limit)
        
        deals = df.to_dict("records")
        for d in deals:
            d["id"] = d["opportunity_id_18"]
        return deals
