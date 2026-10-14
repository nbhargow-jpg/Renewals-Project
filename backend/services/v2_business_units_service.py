from __future__ import annotations
from typing import Optional, Any
import pandas as pd
from datetime import date
from sqlalchemy.orm import Session
from backend.models.snapshot import UploadSnapshot
from backend.models.opportunity import Opportunity
from backend.services.scopes import ScopeService
from backend.services.context import UserContext

ALL_FC = ["Best Case", "Blank", "Closed", "Commit", "Pipeline"]

def _parse_fp(fp: str) -> tuple[int, int]:
    """Parse 'Q4-2026' into (2026, 4)."""
    if not fp or "-" not in fp:
        return (0, 0)
    q_str, y_str = fp.split("-")
    return (int(y_str), int(q_str[1:]))

def _opps_to_df(opps: list[Opportunity]) -> pd.DataFrame:
    if not opps:
        return pd.DataFrame()
    records = []
    for o in opps:
        fc = (o.forecast_category or "Blank").strip()
        if fc == "":
            fc = "Blank"
            
        bu = str(o.business_unit_raw).strip() if o.business_unit_raw else "Unassigned"
        if bu == "" or bu.lower() == "nan":
            bu = "Unassigned"

        records.append({
            "opportunity_id_18": o.opportunity_id_18,
            "opportunity_name": o.opportunity_name,
            "account_name": o.account_name,
            "forecast_acv_amount": float(o.forecast_acv_amount or 0.0),
            "forecast_category": fc,
            "business_unit": bu,
            "is_deleted_or_lost": bool(o.is_deleted_or_lost),
            "fiscal_period": o.fiscal_period or "",
            "close_date": o.close_date,
            "approval_status": o.approval_status or "",
        })
    return pd.DataFrame(records)


class V2BusinessUnitsService:
    def __init__(self, db: Session):
        self.db = db

    def _active_snap(self, as_of: str = None) -> UploadSnapshot | None:
        if as_of:
            try:
                d = date.fromisoformat(as_of)
                return self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date <= d).order_by(UploadSnapshot.snapshot_date.desc()).first()
            except ValueError:
                pass
        return (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.is_active_today == True)
            .order_by(UploadSnapshot.snapshot_date.desc())
            .first()
        )

    def _yesterday_snap(self, snap: UploadSnapshot) -> UploadSnapshot | None:
        from datetime import timedelta
        yd = getattr(snap, "yesterday_date", None)
        if yd:
            return self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == yd).first()
        for i in range(1, 5):
            d = snap.snapshot_date - timedelta(days=i)
            s = self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == d).first()
            if s:
                return s
        return None

    def _lastweek_snap(self, snap: UploadSnapshot) -> UploadSnapshot | None:
        from datetime import timedelta
        ld = getattr(snap, "last_week_date", None)
        if ld:
            return self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == ld).first()
        d = snap.snapshot_date - timedelta(days=7)
        s = self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == d).first()
        if s: return s
        for i in range(6, 9):
            d = snap.snapshot_date - timedelta(days=i)
            s = self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == d).first()
            if s: return s
        return None

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


    def get_summary(
        self,
        ctx: UserContext,
        as_of: str = None,
        compare: str = None,
        exclude_deleted_lost: bool = False,
        filter_spec: Optional[ScopeService.FilterSpec] = None,
    ) -> dict:
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

        comp = fs.compare if fs.compare in ("yesterday", "last_week") else "yesterday"
        y_snap = self._yesterday_snap(snap)
        lw_snap = self._lastweek_snap(snap)

        y_opps, _ = self._scoped_opps(y_snap, filter_spec=fs, target_date=eff_as_of_date) if y_snap else ([], None)
        lw_opps, _ = self._scoped_opps(lw_snap, filter_spec=fs, target_date=eff_as_of_date) if lw_snap else ([], None)
        y_df = _opps_to_df(y_opps)
        lw_df = _opps_to_df(lw_opps)

        def _get_bu_totals(df_in: pd.DataFrame) -> dict:
            if df_in.empty: return {}
            # Group by BU and Forecast Category
            g = df_in.groupby(["business_unit", "forecast_category"])["forecast_acv_amount"].agg(["count", "sum"])
            # Unstack for matrix
            counts = g["count"].unstack(fill_value=0)
            sums = g["sum"].unstack(fill_value=0.0)
            
            # Row totals
            row_counts = counts.sum(axis=1)
            row_sums = sums.sum(axis=1)
            
            res = {}
            for bu in counts.index:
                cells = {}
                for fc in counts.columns:
                    cells[fc] = {"count": int(counts.loc[bu, fc]), "acv": float(sums.loc[bu, fc])}
                res[bu] = {
                    "count": int(row_counts[bu]),
                    "acv": float(row_sums[bu]),
                    "cells": cells
                }
            return res

        today_totals = _get_bu_totals(df)
        y_totals = _get_bu_totals(y_df)
        lw_totals = _get_bu_totals(lw_df)
        
        all_bus = list(today_totals.keys())
        # Sort all_bus by today's ACV descending
        all_bus.sort(key=lambda bu: today_totals[bu]["acv"], reverse=True)

        rows = []
        grand_count = 0
        grand_acv = 0.0
        
        fc_grand_totals = {fc: {"count": 0, "acv": 0.0} for fc in ALL_FC}
        
        if not df.empty:
            grand_count = len(df)
            grand_acv = float(df["forecast_acv_amount"].sum())
            for fc in ALL_FC:
                fc_df = df[df["forecast_category"] == fc]
                fc_grand_totals[fc]["count"] = len(fc_df)
                fc_grand_totals[fc]["acv"] = float(fc_df["forecast_acv_amount"].sum())

        def _calc_delta(td, prev):
            if not prev: return {"count": 0, "acv": 0.0}
            c = td.get("count", 0) - prev.get("count", 0)
            a = td.get("acv", 0.0) - prev.get("acv", 0.0)
            return {"count": c, "acv": round(a, 2)}
            
        def _get_grand_delta(fc, df_in, prev_df_in):
            td_c = len(df_in[df_in["forecast_category"] == fc]) if not df_in.empty else 0
            td_a = float(df_in[df_in["forecast_category"] == fc]["forecast_acv_amount"].sum()) if not df_in.empty else 0.0
            
            pr_c = len(prev_df_in[prev_df_in["forecast_category"] == fc]) if not prev_df_in.empty else 0
            pr_a = float(prev_df_in[prev_df_in["forecast_category"] == fc]["forecast_acv_amount"].sum()) if not prev_df_in.empty else 0.0
            
            return {"count": td_c - pr_c, "acv": round(td_a - pr_a, 2)}

        for bu in all_bus:
            t = today_totals[bu]
            yt = y_totals.get(bu, {})
            lwt = lw_totals.get(bu, {})
            
            cells = {fc: {"count": 0, "acv": 0.0} for fc in ALL_FC}
            for fc, c_data in t["cells"].items():
                if fc in cells:
                    cells[fc] = c_data
            
            # calculate deltas per cell
            for fc in ALL_FC:
                y_cell = yt.get("cells", {}).get(fc, {})
                lw_cell = lwt.get("cells", {}).get(fc, {})
                cells[fc]["delta_yesterday"] = _calc_delta(cells[fc], y_cell)
                cells[fc]["delta_lastweek"] = _calc_delta(cells[fc], lw_cell)

            commit_acv = cells["Commit"]["acv"]
            commit_pct = round((commit_acv / t["acv"] * 100), 1) if t["acv"] > 0 else 0.0
            
            rows.append({
                "bu": bu,
                "count": t["count"],
                "acv": round(t["acv"], 2),
                "pct_acv": round((t["acv"] / grand_acv * 100), 1) if grand_acv > 0 else 0.0,
                "commit_pct": commit_pct,
                "cells": cells,
                "delta_yesterday": _calc_delta(t, yt),
                "delta_lastweek": _calc_delta(t, lwt),
                "yesterday_date": y_snap.snapshot_date.isoformat() if y_snap else None,
                "lastweek_date": lw_snap.snapshot_date.isoformat() if lw_snap else None,
            })

        # Calculate category and grand totals
        totals = {
            "categories": {},
            "grand": {
                "count": grand_count,
                "acv": round(grand_acv, 2),
                "delta_yesterday": _calc_delta({"count": grand_count, "acv": grand_acv}, {"count": len(y_df) if not y_df.empty else 0, "acv": float(y_df["forecast_acv_amount"].sum()) if not y_df.empty else 0.0}),
                "delta_lastweek": _calc_delta({"count": grand_count, "acv": grand_acv}, {"count": len(lw_df) if not lw_df.empty else 0, "acv": float(lw_df["forecast_acv_amount"].sum()) if not lw_df.empty else 0.0})
            }
        }
        
        for fc in ALL_FC:
            totals["categories"][fc] = {
                "count": fc_grand_totals[fc]["count"],
                "acv": round(fc_grand_totals[fc]["acv"], 2),
                "delta_yesterday": _get_grand_delta(fc, df, y_df),
                "delta_lastweek": _get_grand_delta(fc, df, lw_df),
            }

        target_fp = res.resolved_quarter
        return {
            "snapshot_date": snap.snapshot_date.isoformat(),
            "requested_as_of": fs.as_of or snap.snapshot_date.isoformat(),
            "compare_date": None,
            "yesterday_date": y_snap.snapshot_date.isoformat() if y_snap else None,
            "lastweek_date": lw_snap.snapshot_date.isoformat() if lw_snap else None,
            "data_slice": res.data_slice,
            "data_slice_key": target_fp,
            "filters_applied": res.filters_applied,
            "total": {
                "count": grand_count,
                "acv": round(grand_acv, 2)
            },
            "categories": ALL_FC,
            "rows": rows,
            "totals": totals
        }

    def get_deals(
        self,
        ctx: UserContext,
        bu: str = None,
        category: str = None,
        status: str = None,
        as_of: str = None,
        exclude_deleted_lost: bool = False,
        filter_spec: Optional[ScopeService.FilterSpec] = None,
    ) -> dict:
        from backend.services.scopes import FilterSpec
        fs = filter_spec.model_copy() if filter_spec else FilterSpec()
        if as_of:
            fs.as_of = as_of
        if exclude_deleted_lost:
            fs.include_deleted_lost = False
        if bu and bu != "All":
            fs.business_units = [bu]
        if category:
            fs.forecast_categories = [category]
        if status:
            fs.approval_statuses = [status]

        snap = self._active_snap(fs.as_of)
        if not snap:
            return {"error": "no_snapshot"}
            
        opps, res = self._scoped_opps(snap, filter_spec=fs)
        df = _opps_to_df(opps)
        
        if df.empty:
            return {"count": 0, "acv": 0.0, "filters_applied": res.filters_applied, "deals": []}

        df = df.sort_values("forecast_acv_amount", ascending=False)
        deals = df.to_dict(orient="records")
        for d in deals:
            if d["close_date"]: d["close_date"] = d["close_date"].isoformat()
            
        return {
            "count": len(deals),
            "acv": round(float(df["forecast_acv_amount"].sum()) if not df.empty else 0.0, 2),
            "filters_applied": res.filters_applied,
            "deals": deals
        }
        
    def get_top_opportunities(
        self,
        ctx: UserContext,
        bu: str = None,
        limit: int = 10,
        as_of: str = None,
        filter_spec: Optional[ScopeService.FilterSpec] = None,
    ) -> dict:
        from backend.services.scopes import FilterSpec
        fs = filter_spec.model_copy() if filter_spec else FilterSpec()
        fs.include_deleted_lost = False
        if as_of:
            fs.as_of = as_of
        if bu and bu != "All":
            fs.business_units = [bu]

        snap = self._active_snap(fs.as_of)
        if not snap:
            return {"error": "no_snapshot"}
            
        opps, _ = self._scoped_opps(snap, filter_spec=fs)
        df = _opps_to_df(opps)
        
        if df.empty:
            return {"deals": []}
            
        df = df.sort_values("forecast_acv_amount", ascending=False).head(limit)
        deals = df.to_dict(orient="records")
        for d in deals:
            if d["close_date"]: d["close_date"] = d["close_date"].isoformat()
            
        return {"deals": deals}

