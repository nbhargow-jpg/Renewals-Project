from __future__ import annotations
import logging
import pandas as pd
from datetime import date, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot
from backend.services.context import UserContext
from backend.services.scopes import ScopeService

log = logging.getLogger(__name__)

def _parse_fp(fp: str) -> tuple[int, int]:
    """Q4-2026 -> (2026, 4)"""
    try:
        q, y = fp.split("-")
        return int(y), int(q[1])
    except:
        return (0, 0)

def _norm_fc(s: str | None) -> str:
    if not s or str(s).strip() in ("", "nan", "None"): return "Blank"
    s = str(s).strip()
    if s not in ["Closed", "Commit", "Best Case", "Pipeline"]: return "Blank"
    return s

def _norm_approval(s: str | None) -> str:
    if not s or str(s).strip() in ("", "nan", "None", "Blank"): return "Blank"
    s = str(s).strip()
    if s in ("Approved", "Approved - 2nd"): return "Approved"
    if s in ("Pending Approval", "Pending-Approval"): return "Pending Approval"
    return s

def _map_region(s: str | None) -> str:
    if not s or str(s).strip() in ("", "nan", "None"): return "Other"
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
            "id": o.opportunity_id_18,
            "opportunity_id_18": o.opportunity_id_18,
            "opportunity_name": o.opportunity_name,
            "account_name": o.account_name,
            "forecast_acv_amount": float(o.forecast_acv_amount or 0.0),
            "forecast_category": _norm_fc(o.forecast_category),
            "business_unit": (o.business_unit_primary or "").strip() or "Unassigned",
            "business_unit_primary": (o.business_unit_primary or "").strip() or "Unassigned",
            "is_deleted_or_lost": bool(o.is_deleted_or_lost),
            "fiscal_period": o.fiscal_period or "",
            "close_date": pd.to_datetime(o.close_date) if o.close_date else pd.NaT,
            "approval_status": _norm_approval(o.approval_status),
            "region": _map_region(o.revised_sub_region),
            "sub_region": _map_region(o.revised_sub_region),
            "sales_type": o.sales_type or ""
        })
    df = pd.DataFrame(records)
    df = df.drop_duplicates(subset=["opportunity_id_18"], keep="last")
    return df

class V2DelayedService:
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
        return q.filter(UploadSnapshot.is_active_today == True).order_by(UploadSnapshot.snapshot_date.desc()).first()

    def _snap_by_date(self, d: date) -> UploadSnapshot | None:
        return self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == d).first()

    def _get_opps(self, snap: UploadSnapshot) -> list[Opportunity]:
        return self.db.query(Opportunity).filter(Opportunity.snapshot_id == snap.id).all()
    
    def _filter_df(self, df: pd.DataFrame, filter_spec: Optional[ScopeService.FilterSpec] = None) -> pd.DataFrame:
        if df.empty:
            return df
        res_df = df
        from backend.services.scopes import FilterSpec
        fs = filter_spec or FilterSpec()
        
        # sales_types
        if fs.sales_types:
            res_df = res_df[res_df["sales_type"].isin(fs.sales_types)]
        # include_deleted_lost
        if not fs.include_deleted_lost:
            res_df = res_df[~res_df["is_deleted_or_lost"]]
        # regions
        if fs.regions:
            res_df = res_df[res_df["region"].isin(fs.regions) | res_df["sub_region"].isin(fs.regions)]
        # business_units
        if fs.business_units:
            res_df = res_df[res_df["business_unit"].isin(fs.business_units) | res_df["business_unit_primary"].isin(fs.business_units)]
        # forecast_categories
        if fs.forecast_categories:
            norm_cats = ["Blank" if c in ("Not yet proposed", "Blank", "") else c for c in fs.forecast_categories]
            res_df = res_df[res_df["forecast_category"].isin(norm_cats)]
        # approval_statuses
        if fs.approval_statuses:
            norm_apps = ["Blank" if a in ("Not submitted", "Blank", "") else a for a in fs.approval_statuses]
            res_df = res_df[res_df["approval_status"].isin(norm_apps)]
            
        return res_df

    def _slice_renewals(self, df: pd.DataFrame, filter_spec: Optional[ScopeService.FilterSpec] = None) -> pd.DataFrame:
        return self._filter_df(df, filter_spec)

    def _get_dataframes(self, as_of: str | None, compare: str):
        t_snap = self._active_snap(as_of)
        if not t_snap:
            return None
            
        y_snap = self._snap_by_date(t_snap.snapshot_date - timedelta(days=1))
        w_snap = self._snap_by_date(t_snap.snapshot_date - timedelta(days=7))
        
        # Fallbacks
        if not y_snap:
            y_snap = self.db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date < t_snap.snapshot_date).order_by(UploadSnapshot.snapshot_date.desc()).first()
        if not w_snap:
            w_snap = y_snap
            
        p_snap = y_snap if compare != "last_week" else w_snap
        if not p_snap:
            p_snap = y_snap
        if not y_snap:
            return None # no history
            
        t_df = _opps_to_df(self._get_opps(t_snap))
        y_df = _opps_to_df(self._get_opps(y_snap))
        w_df = _opps_to_df(self._get_opps(w_snap))
        
        return {
            "t_snap": t_snap, "y_snap": y_snap, "w_snap": w_snap, "p_snap": p_snap,
            "t_df": t_df, "y_df": y_df, "w_df": w_df, "p_df": y_df if compare != "last_week" else w_df
        }

    def _compute_delayed_and_overdue(self, data: dict, filter_spec: Optional[ScopeService.FilterSpec] = None):
        t_snap = data["t_snap"]
        t_df = data["t_df"]
        y_df = data["y_df"]
        w_df = data["w_df"]
        
        t_ren = self._slice_renewals(t_df, filter_spec)
        y_ren = self._slice_renewals(y_df, filter_spec)
        w_ren = self._slice_renewals(w_df, filter_spec)
        
        target_q_str = ScopeService.current_quarter(t_snap.snapshot_date)
        target_parsed = _parse_fp(target_q_str)
        t_snap_date = pd.Timestamp(t_snap.snapshot_date)
        y_snap_date = pd.Timestamp(data["y_snap"].snapshot_date)
        w_snap_date = pd.Timestamp(data["w_snap"].snapshot_date)
        
        # 1. OVERDUE (based only on AS-OF)
        # Overdue = Renewals deal in the current-quarter slice, Close Date < snapshot date, category not Closed.
        t_q4 = t_ren[t_ren["fiscal_period"] == target_q_str]
        overdue_df = pd.DataFrame()
        if not t_q4.empty:
            is_overdue = pd.notna(t_q4["close_date"]) & (t_q4["close_date"] < t_snap_date) & (t_q4["forecast_category"] != "Closed") & (~t_q4["is_deleted_or_lost"])
            overdue_df = t_q4[is_overdue].copy()
            overdue_df["reason"] = "Overdue"
            overdue_df["push_out_days"] = 0
            
            # For each overdue deal, was it overdue yesterday? (i.e. Close Date < yesterday date and not closed yesterday)
            y_indexed = y_ren.set_index("opportunity_id_18")
            w_indexed = w_ren.set_index("opportunity_id_18")
            
            def check_overdue_hist(row, hist_idx, hist_date):
                if row["opportunity_id_18"] not in hist_idx.index: return False
                h = hist_idx.loc[row["opportunity_id_18"]]
                return (pd.notna(h["close_date"]) and h["close_date"] < hist_date and 
                        h["forecast_category"] != "Closed" and not h["is_deleted_or_lost"] and 
                        h["fiscal_period"] == target_q_str)
                
            overdue_df["overdue_yesterday"] = overdue_df.apply(lambda r: check_overdue_hist(r, y_indexed, y_snap_date), axis=1)
            overdue_df["overdue_lastweek"] = overdue_df.apply(lambda r: check_overdue_hist(r, w_indexed, w_snap_date), axis=1)

        # 2. DELAYED (Slipped / Later Close Date / Lost)
        def _get_delayed_from_base(base_ren, base_snap_date):
            base_q4 = base_ren[(base_ren["fiscal_period"] == target_q_str) & (~base_ren["is_deleted_or_lost"])]
            if base_q4.empty: return pd.DataFrame()
            base_q4 = base_q4.set_index("opportunity_id_18")
            
            t_indexed = t_ren.set_index("opportunity_id_18")
            
            res_ids = []
            reasons = []
            push_days = []
            
            for opp_id, b_row in base_q4.iterrows():
                # Check if missing or deleted/lost
                if opp_id not in t_indexed.index:
                    res_ids.append(opp_id)
                    reasons.append("Lost/removed")
                    push_days.append(0)
                    continue
                    
                t_row = t_indexed.loc[opp_id]
                if t_row["is_deleted_or_lost"]:
                    res_ids.append(opp_id)
                    reasons.append("Lost/removed")
                    push_days.append(0)
                    continue
                    
                t_fp = t_row["fiscal_period"]
                if not t_fp or '-' not in t_fp: continue
                t_parsed = _parse_fp(t_fp)
                
                is_slipped = (t_parsed[0] > target_parsed[0]) or (t_parsed[0] == target_parsed[0] and t_parsed[1] > target_parsed[1])
                is_later_close = pd.notna(t_row["close_date"]) and pd.notna(b_row["close_date"]) and t_row["close_date"] > b_row["close_date"]
                
                # if it's slipped, it's not in the quarter anymore, so "Slipped quarter" is the primary reason
                # if it's in the same quarter but later close date, "Later close date"
                if is_slipped:
                    res_ids.append(opp_id)
                    reasons.append("Slipped quarter")
                    push_days.append((t_row["close_date"] - b_row["close_date"]).days if pd.notna(t_row["close_date"]) and pd.notna(b_row["close_date"]) else 0)
                elif is_later_close:
                    res_ids.append(opp_id)
                    reasons.append("Later close date")
                    push_days.append((t_row["close_date"] - b_row["close_date"]).days)
            
            if not res_ids: return pd.DataFrame()
            
            base_idx = base_q4.copy()
            res_df = []
            for i, oid in enumerate(res_ids):
                row = t_indexed.loc[oid].copy() if oid in t_indexed.index else base_idx.loc[oid].copy()
                row["opportunity_id_18"] = oid
                row["reason"] = reasons[i]
                row["push_out_days"] = push_days[i]
                res_df.append(row)
            return pd.DataFrame(res_df)

        delayed_y = _get_delayed_from_base(y_ren, y_snap_date)
        delayed_w = _get_delayed_from_base(w_ren, w_snap_date)
        
        return overdue_df, delayed_y, delayed_w

    def get_summary(self, as_of: str | None = None, compare: str | None = None, filter_spec: Optional[ScopeService.FilterSpec] = None) -> dict:
        eff_as_of = as_of or (filter_spec.as_of if filter_spec else None)
        eff_compare = compare or (filter_spec.compare if filter_spec else "yesterday")
        data = self._get_dataframes(eff_as_of, eff_compare)
        if not data: return {"error": "No data"}
        
        t_snap = data["t_snap"]
        from backend.services.scopes import FilterSpec
        fs = filter_spec.model_copy() if filter_spec else FilterSpec()
        res = ScopeService.resolve(fs, snapshot=t_snap, as_of_date=t_snap.snapshot_date)
        target_q_str = res.period if res.period.startswith("Q") and "-" in res.period else ScopeService.current_quarter(t_snap.snapshot_date)
        target_q_label = res.label
        
        overdue_df, delayed_y, delayed_w = self._compute_delayed_and_overdue(data, filter_spec=fs)
        
        delayed_df = delayed_y if eff_compare != "last_week" else delayed_w
        
        # Exclude "Lost/removed" from delayed totals
        delayed_active = delayed_df[delayed_df["reason"] != "Lost/removed"] if not delayed_df.empty else pd.DataFrame()
        if not overdue_df.empty:
            delayed_active = pd.concat([delayed_active, overdue_df], ignore_index=True) if not delayed_active.empty else overdue_df.copy()
            delayed_active = delayed_active.drop_duplicates(subset=["opportunity_id_18"], keep="first")
            
        slipped_df = delayed_active[delayed_active["reason"] == "Slipped quarter"] if not delayed_active.empty else pd.DataFrame()
        later_df = delayed_active[delayed_active["reason"] == "Later close date"] if not delayed_active.empty else pd.DataFrame()
        lost_df = delayed_df[delayed_df["reason"] == "Lost/removed"] if not delayed_df.empty else pd.DataFrame()
        
        d_act_y = delayed_y[delayed_y["reason"] != "Lost/removed"] if not delayed_y.empty else pd.DataFrame()
        d_act_w = delayed_w[delayed_w["reason"] != "Lost/removed"] if not delayed_w.empty else pd.DataFrame()

        overdue_not_y = overdue_df[~overdue_df["overdue_yesterday"]] if not overdue_df.empty else pd.DataFrame()
        overdue_not_w = overdue_df[~overdue_df["overdue_lastweek"]] if not overdue_df.empty else pd.DataFrame()

        def _get_deltas(df_act_y, df_act_w):
            c_y = len(df_act_y)
            c_w = len(df_act_w)
            a_y = df_act_y["forecast_acv_amount"].sum() if not df_act_y.empty else 0.0
            a_w = df_act_w["forecast_acv_amount"].sum() if not df_act_w.empty else 0.0
            return {
                "delayed_vs_yesterday": {"count": c_y, "acv": a_y},
                "delayed_vs_lastweek": {"count": c_w, "acv": a_w}
            }

        def _aggregate_by(col: str):
            res_agg = []
            if delayed_active.empty: return res_agg
            for val in delayed_active[col].unique():
                d = delayed_active[delayed_active[col] == val]
                d_y = d_act_y[d_act_y[col] == val] if not d_act_y.empty else pd.DataFrame()
                d_w = d_act_w[d_act_w[col] == val] if not d_act_w.empty else pd.DataFrame()
                
                cats = {}
                ALL_FC = ["Commit", "Best Case", "Pipeline", "Closed", "Blank"]
                for cat in ALL_FC:
                    d_cat = d[d["forecast_category"] == cat]
                    dy_cat = d_y[d_y["forecast_category"] == cat] if not d_y.empty else pd.DataFrame()
                    dw_cat = d_w[d_w["forecast_category"] == cat] if not d_w.empty else pd.DataFrame()
                    cats[cat] = {
                        "count": len(d_cat),
                        "acv": d_cat["forecast_acv_amount"].sum(),
                        **_get_deltas(dy_cat, dw_cat)
                    }
                    
                res_agg.append({
                    "label": val,
                    "count": len(d),
                    "acv": d["forecast_acv_amount"].sum(),
                    "avg_push_out": round(d["push_out_days"].mean(), 1) if len(d) > 0 else 0,
                    "max_push_out": int(d["push_out_days"].max()) if len(d) > 0 else 0,
                    "categories": cats,
                    **_get_deltas(d_y, d_w)
                })
            return sorted(res_agg, key=lambda x: x["acv"], reverse=True)

        overdue_y = overdue_df[overdue_df["overdue_yesterday"]] if not overdue_df.empty else pd.DataFrame()
        overdue_w = overdue_df[overdue_df["overdue_lastweek"]] if not overdue_df.empty else pd.DataFrame()

        total_count = len(delayed_active)
        total_acv = delayed_active["forecast_acv_amount"].sum() if not delayed_active.empty else 0.0

        return {
            "data_slice": target_q_label,
            "data_slice_key": target_q_str,
            "filters_applied": res.filters_applied,
            "snapshot_date": t_snap.snapshot_date.isoformat(),
            "compare_date": data["p_snap"].snapshot_date.isoformat(),
            "yesterday_date": data["y_snap"].snapshot_date.isoformat(),
            "lastweek_date": data["w_snap"].snapshot_date.isoformat(),
            "total": {
                "count": total_count,
                "acv": round(total_acv, 2),
                **_get_deltas(d_act_y, d_act_w)
            },
            "overdue": {
                "count": len(overdue_df),
                "acv": round(overdue_df["forecast_acv_amount"].sum() if not overdue_df.empty else 0.0, 2),
                "delayed_vs_yesterday": {"count": len(overdue_y), "acv": round(overdue_y["forecast_acv_amount"].sum() if not overdue_y.empty else 0, 2)},
                "delayed_vs_lastweek": {"count": len(overdue_w), "acv": round(overdue_w["forecast_acv_amount"].sum() if not overdue_w.empty else 0, 2)}
            },
            "slipped": {
                "count": len(slipped_df),
                "acv": round(slipped_df["forecast_acv_amount"].sum() if not slipped_df.empty else 0.0, 2),
                **_get_deltas(
                    d_act_y[d_act_y["reason"] == "Slipped quarter"] if not d_act_y.empty else pd.DataFrame(),
                    d_act_w[d_act_w["reason"] == "Slipped quarter"] if not d_act_w.empty else pd.DataFrame()
                )
            },
            "later_close": {
                "count": len(later_df),
                "acv": round(later_df["forecast_acv_amount"].sum() if not later_df.empty else 0.0, 2),
                **_get_deltas(
                    d_act_y[d_act_y["reason"] == "Later close date"] if not d_act_y.empty else pd.DataFrame(),
                    d_act_w[d_act_w["reason"] == "Later close date"] if not d_act_w.empty else pd.DataFrame()
                )
            },
            "lost": {
                "count": len(lost_df),
                "acv": round(lost_df["forecast_acv_amount"].sum() if not lost_df.empty else 0.0, 2),
            },
            "by_region": _aggregate_by("region"),
            "by_bu": _aggregate_by("business_unit"),
            "by_category": _aggregate_by("forecast_category"),
            "by_approval": _aggregate_by("approval_status"),
            "top_deals": delayed_active.sort_values(by="forecast_acv_amount", ascending=False).head(10).fillna("").to_dict("records") if not delayed_active.empty else []
        }

    def get_deals(self, as_of: str | None, compare: str | None, kind: str, region: str | None, category: str | None, status: str | None, bu: str | None, filter_spec: Optional[ScopeService.FilterSpec] = None) -> dict:
        eff_as_of = as_of or (filter_spec.as_of if filter_spec else None)
        eff_compare = compare or (filter_spec.compare if filter_spec else "yesterday")
        data = self._get_dataframes(eff_as_of, eff_compare)
        if not data: return {"count": 0, "acv": 0.0, "deals": []}
        
        overdue_df, delayed_y, delayed_w = self._compute_delayed_and_overdue(data, filter_spec=filter_spec)
        delayed_df = delayed_y if eff_compare != "last_week" else delayed_w
        
        df = pd.DataFrame()
        if kind == "overdue":
            df = overdue_df
        elif kind == "slipped":
            df = delayed_df[delayed_df["reason"] == "Slipped quarter"] if not delayed_df.empty else pd.DataFrame()
        elif kind == "later_close":
            df = delayed_df[delayed_df["reason"] == "Later close date"] if not delayed_df.empty else pd.DataFrame()
        elif kind == "lost":
            df = delayed_df[delayed_df["reason"] == "Lost/removed"] if not delayed_df.empty else pd.DataFrame()
        elif kind == "all":
            df = delayed_df[delayed_df["reason"] != "Lost/removed"] if not delayed_df.empty else pd.DataFrame()
            if not overdue_df.empty:
                df = pd.concat([df, overdue_df], ignore_index=True) if not df.empty else overdue_df.copy()
                df = df.drop_duplicates(subset=["opportunity_id_18"], keep="first")
        else:
            return {"count": 0, "acv": 0.0, "deals": []}
            
        if df.empty:
            return {"count": 0, "acv": 0.0, "deals": []}
            
        if region and region != "All":
            df = df[df["region"] == region]
        if category and category != "All":
            df = df[df["forecast_category"] == category]
        if status and status != "All":
            df = df[df["approval_status"] == status]
        if bu and bu != "All":
            df = df[df["business_unit"] == bu]
            
        if df.empty:
            return {"count": 0, "acv": 0.0, "deals": []}
            
        df["close_date"] = df["close_date"].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else None)
        df = df.fillna("")
        deals = df.to_dict("records")
        return {
            "count": len(deals),
            "acv": round(df["forecast_acv_amount"].sum(), 2),
            "deals": deals
        }
