"""
V2 Overview Service — powers Tab 1 (Overview / Dashboard).

Data slice: Q4 slice = opportunities where in_q4_2026 is True, deduped by
opportunity_id_18 (multiple snapshots may contain the same opp; we always use
the LATEST record for a given opp_id within the active snapshot).

Deleted/Lost: INCLUDED by default (matches Excel pivots).
Movements: computed by diffing two scoped snapshots by Opportunity ID —
  NOT from change_logs (unscoped, only exists for yesterday, inflates Q4).
Blank category: treated as its own column alongside Closed/Commit/Best Case/Pipeline.
Slippage to 2027: Q4 opps whose close_date.year == 2027.
Region mapping: EXACT match on revised_sub_region value.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot
from backend.services.context import UserContext
from backend.services.scopes import ScopeService


def _sum(df: pd.DataFrame, col: str) -> float:
    if df.empty or col not in df.columns:
        return 0.0
    return float(df[col].sum())

log = logging.getLogger(__name__)

# ── Region normalisation (EXACT match as specified) ──────────────────────────
REGION_MAP: dict[str, str] = {
    "Europe":        "Europe",
    "APAC":          "APAC",
    "AFRICA":        "Africa",
    "MENA":          "Middle East and North Africa",
    "NAMR":          "North America",
    "South America": "LATAM",
}
CANONICAL_REGIONS = list(REGION_MAP.values())  # preserves insertion order
ALL_FC = ["Closed", "Commit", "Best Case", "Pipeline", "Blank"]
POSITIVE_MOVES = [
    ("Commit",     "Closed"),
    ("Best Case",  "Commit"),
    ("Pipeline",   "Best Case"),
]
NEGATIVE_MOVES = [
    ("Commit",     "Best Case"),
    ("Best Case",  "Pipeline"),
    # third row is Slippage to 2027 — computed separately, not a FC→FC transition
]
APPROVAL_STATUSES = ["Approved", "Pending Approval", "Blank", "Rejected"]


def _norm_approval(s: str | None) -> str:
    if not s or str(s).strip() in ("", "nan", "None", "Blank"):
        return "Blank"
    s = s.strip()
    if s in ("Approved", "Approved - 2nd"):
        return "Approved"
    if s in ("Pending Approval", "Pending-Approval"):
        return "Pending Approval"
    return s  # Rejected or anything else


def _norm_fc(s: str | None) -> str:
    if not s or str(s).strip() in ("", "nan", "None"):
        return "Blank"
    return s.strip()


def _norm_region(revised_sub_region: str | None) -> str:
    """Exact-match region mapping; returns 'Other' if not in the map."""
    if not revised_sub_region:
        return "Other"
    return REGION_MAP.get(str(revised_sub_region).strip(), "Other")


def _opps_to_df(opps: list[Opportunity]) -> pd.DataFrame:
    if not opps:
        return pd.DataFrame()
    records = []
    for o in opps:
        records.append({
            "opportunity_id_18": o.opportunity_id_18 or "",
            "opportunity_name":  o.opportunity_name or "",
            "account_name":      o.account_name or "",
            "revised_sub_region": o.revised_sub_region or "",
            "canonical_region":   _norm_region(o.revised_sub_region),
            "business_unit_primary": o.business_unit_primary or "",
            "forecast_category":  _norm_fc(o.forecast_category),
            "forecast_acv_amount": float(o.forecast_acv_amount or 0),
            "approval_status":    _norm_approval(o.approval_status),
            "close_date":         o.close_date,
            "close_year":         o.close_date.year if o.close_date else None,
            "is_deleted_or_lost": bool(o.is_deleted_or_lost),
            "fiscal_period":      o.fiscal_period or "",
            "sales_type":         o.sales_type or "",
        })
    return pd.DataFrame(records)


class V2OverviewService:
    def __init__(self, db: Session):
        self.db = db

    # ── snapshot helpers ──────────────────────────────────────────────────────

    def _active_snap(self, as_of: str | None = None) -> UploadSnapshot | None:
        q = self.db.query(UploadSnapshot)
        if as_of:
            try:
                from datetime import date
                d = date.fromisoformat(as_of)
                return q.filter(UploadSnapshot.snapshot_date <= d).order_by(UploadSnapshot.snapshot_date.desc()).first()
            except ValueError:
                pass
        return (
            q.filter(UploadSnapshot.is_active_today == True)  # noqa: E712
            .order_by(UploadSnapshot.snapshot_date.desc())
            .first()
        )

    def _snap_by_date(self, d: date) -> UploadSnapshot | None:
        return (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.snapshot_date == d)
            .first()
        )

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
        from datetime import timedelta
        # Try yesterday_date attribute first, then date-1
        if getattr(snap, "yesterday_date", None):
            s = self._snap_by_date(snap.yesterday_date)
            if s:
                return s
        return self._snap_by_date(snap.snapshot_date - timedelta(days=1))

    def _lastweek_snap(self, snap: UploadSnapshot) -> UploadSnapshot | None:
        from datetime import timedelta
        return self._snap_by_date(snap.snapshot_date - timedelta(days=7))

    # ── core aggregation helpers ──────────────────────────────────────────────

    def _category_summary(self, df: pd.DataFrame) -> dict:
        """Count + ACV per forecast category including Blank and any dynamic/new categories (Addendum C)."""
        result = {fc: {"count": 0, "acv": 0.0} for fc in ALL_FC}
        if df.empty or "forecast_category" not in df.columns:
            return result
        
        # Standard ALL_FC
        for fc in ALL_FC:
            sub = df[df["forecast_category"] == fc]
            result[fc] = {
                "count": len(sub),
                "acv": round(_sum(sub, "forecast_acv_amount"), 2),
            }
        
        # Dynamic / new categories (Addendum C: new category gets its own entry/card)
        all_unique = df["forecast_category"].dropna().unique()
        for cat in all_unique:
            cat_str = str(cat).strip()
            if cat_str and cat_str not in result:
                sub = df[df["forecast_category"] == cat_str]
                result[cat_str] = {
                    "count": len(sub),
                    "acv": round(_sum(sub, "forecast_acv_amount"), 2),
                }
        return result

    def _movements(
        self,
        today_df: pd.DataFrame,
        prev_df: pd.DataFrame,
        today_all_df: pd.DataFrame,
        target_fp: str,
    ) -> dict:
        """
        Compute forecast category and approval movements by diffing two scoped DataFrames.
        Joins on opportunity_id_18.
        Returns positive_moves, negative_moves, approval_moves lists.
        """
        if today_df.empty or prev_df.empty:
            return {
                "positive": [], "negative": [], "approval": [],
                "slippage_to_2027": {"count": 0, "acv": 0.0},
                "slipped_later_quarter": {"count": 0, "acv": 0.0},
                "slipped_earlier": {"count": 0, "acv": 0.0},
            }

        t = today_df.set_index("opportunity_id_18")
        p = prev_df.set_index("opportunity_id_18")
        common = t.index.intersection(p.index)

        positive: list[dict] = []
        negative: list[dict] = []
        approval_moves: list[dict] = []

        # Pre-build move buckets
        pos_buckets: dict[tuple, list] = {m: [] for m in POSITIVE_MOVES}
        neg_buckets: dict[tuple, list] = {m: [] for m in NEGATIVE_MOVES}
        app_buckets: dict[tuple, list] = {}

        for opp_id in common:
            tr = t.loc[opp_id]
            pr = p.loc[opp_id]
            fc_now  = tr["forecast_category"] if isinstance(tr, pd.Series) else tr.iloc[0]["forecast_category"]
            fc_prev = pr["forecast_category"] if isinstance(pr, pd.Series) else pr.iloc[0]["forecast_category"]
            acv     = float(tr["forecast_acv_amount"] if isinstance(tr, pd.Series) else tr.iloc[0]["forecast_acv_amount"])
            name    = str(tr["opportunity_name"] if isinstance(tr, pd.Series) else tr.iloc[0]["opportunity_name"])
            region  = str(tr["canonical_region"] if isinstance(tr, pd.Series) else tr.iloc[0]["canonical_region"])
            ap_now  = str(tr["approval_status"] if isinstance(tr, pd.Series) else tr.iloc[0]["approval_status"])
            ap_prev = str(pr["approval_status"] if isinstance(pr, pd.Series) else pr.iloc[0]["approval_status"])

            move_key = (fc_prev, fc_now)
            if fc_prev != fc_now:
                deal = {"opportunity_id_18": opp_id, "opportunity_name": name,
                        "region": region, "from_category": fc_prev, "to_category": fc_now, "acv": acv}
                if move_key in pos_buckets:
                    pos_buckets[move_key].append(deal)
                elif move_key in neg_buckets:
                    neg_buckets[move_key].append(deal)

            if ap_now != ap_prev:
                ak = (ap_prev, ap_now)
                if ak not in app_buckets:
                    app_buckets[ak] = []
                app_buckets[ak].append({
                    "opportunity_id_18": opp_id, "opportunity_name": name,
                    "from_status": ap_prev, "to_status": ap_now, "acv": acv, "region": region,
                })

        def _bucket_summary(bucket: list[dict]) -> dict:
            return {
                "count": len(bucket),
                "acv": round(sum(d["acv"] for d in bucket), 2),
                "deals": bucket,
            }

        for (f, t_), deals in pos_buckets.items():
            positive.append({
                "from_category": f, "to_category": t_,
                **_bucket_summary(deals),
            })
        for (f, t_), deals in neg_buckets.items():
            negative.append({
                "from_category": f, "to_category": t_,
                **_bucket_summary(deals),
            })
        for (fa, ta), deals in app_buckets.items():
            approval_moves.append({
                "from_status": fa, "to_status": ta,
                **_bucket_summary(deals),
            })

        # New Slippage logic
        def _parse_fp(fp: str):
            if not fp or '-' not in fp: return (0, 0)
            q, y = fp.split('-')
            return (int(y), int(q.replace('Q', '')))

        target_parsed = _parse_fp(target_fp)
        
        slipped_next_year_deals = []
        slipped_later_quarter_same_year_deals = []
        slipped_earlier_quarter_deals = []

        if not prev_df.empty and not today_all_df.empty:
            t_all = today_all_df.set_index("opportunity_id_18")
            for opp_id in p.index:
                if opp_id in t_all.index:
                    t_opp = t_all.loc[opp_id]
                    t_fp = str(t_opp["fiscal_period"] if isinstance(t_opp, pd.Series) else t_opp.iloc[0]["fiscal_period"])
                    if not t_fp or '-' not in t_fp: continue
                    t_parsed = _parse_fp(t_fp)
                    
                    deal = {
                        "opportunity_id_18": opp_id,
                        "opportunity_name": str(t_opp["opportunity_name"] if isinstance(t_opp, pd.Series) else t_opp.iloc[0]["opportunity_name"]),
                        "account_name": str(t_opp["account_name"] if isinstance(t_opp, pd.Series) else t_opp.iloc[0]["account_name"]),
                        "canonical_region": str(t_opp["canonical_region"] if isinstance(t_opp, pd.Series) else t_opp.iloc[0]["canonical_region"]),
                        "forecast_category": str(t_opp["forecast_category"] if isinstance(t_opp, pd.Series) else t_opp.iloc[0]["forecast_category"]),
                        "forecast_acv_amount": float(t_opp["forecast_acv_amount"] if isinstance(t_opp, pd.Series) else t_opp.iloc[0]["forecast_acv_amount"]),
                        "approval_status": str(t_opp["approval_status"] if isinstance(t_opp, pd.Series) else t_opp.iloc[0]["approval_status"]),
                        "business_unit_primary": str(t_opp["business_unit_primary"] if isinstance(t_opp, pd.Series) else t_opp.iloc[0]["business_unit_primary"]),
                        "fiscal_period": t_fp,
                        "close_date": (t_opp["close_date"].isoformat() if hasattr(t_opp["close_date"], "isoformat") else str(t_opp["close_date"])) if (t_opp["close_date"] is not None and not pd.isna(t_opp["close_date"])) else None,
                    }

                    
                    if t_parsed[0] > target_parsed[0]:
                        slipped_next_year_deals.append(deal)
                    elif t_parsed[0] == target_parsed[0] and t_parsed[1] > target_parsed[1]:
                        slipped_later_quarter_same_year_deals.append(deal)
                    elif t_parsed < target_parsed:
                        slipped_earlier_quarter_deals.append(deal)

        slippage = {
            "label": "Slipped to next year",
            "count": len(slipped_next_year_deals),
            "acv": round(sum(d["forecast_acv_amount"] for d in slipped_next_year_deals), 2),
            "deals": slipped_next_year_deals,
        }
        
        later_q = {
            "label": "Slipped to a later quarter, same year",
            "count": len(slipped_later_quarter_same_year_deals),
            "acv": round(sum(d["forecast_acv_amount"] for d in slipped_later_quarter_same_year_deals), 2),
            "deals": slipped_later_quarter_same_year_deals,
        }
        
        earlier_q = {
            "label": "Moved to earlier quarter",
            "count": len(slipped_earlier_quarter_deals),
            "acv": round(sum(d["forecast_acv_amount"] for d in slipped_earlier_quarter_deals), 2),
            "deals": slipped_earlier_quarter_deals,
        }

        # Append slippage as the third negative row
        negative.append(slippage)

        return {
            "positive": positive,
            "negative": negative,
            "approval": approval_moves,
            "slippage_to_2027": slippage,
            "slipped_later_quarter": later_q,
            "slipped_earlier": earlier_q,
        }

    # ── public API ────────────────────────────────────────────────────────────

    def get_summary(
        self,
        ctx: UserContext,
        exclude_deleted: bool = False,
        as_of: str | None = None,
        filter_spec: Optional[ScopeService.FilterSpec] = None,
    ) -> dict:
        """
        Main Overview summary:
        - Section 1: Total ACV + count + Δ yesterday + Δ last week
        - Section 2: 5 category cards (Closed/Commit/BC/Pipeline/Blank)
        - Section 3: Slippage
        - Snapshot metadata (date, files, uploaded_at)
        """
        from backend.services.scopes import FilterSpec
        fs = filter_spec.model_copy() if filter_spec else FilterSpec()
        if as_of:
            fs.as_of = as_of
        if exclude_deleted:
            fs.include_deleted_lost = False

        snap = self._active_snap(fs.as_of)
        if snap is None:
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

        total_count = len(df)
        total_acv   = round(_sum(df, "forecast_acv_amount"), 2) if not df.empty else 0.0
        cats = self._category_summary(df)

        target_fp = res.resolved_quarter
        data_slice = res.data_slice

        import pandas as pd
        _, q_end_date = ScopeService.quarter_bounds(target_fp)
        if not df.empty and "close_date" in df.columns:
            cd_dates = pd.to_datetime(df["close_date"], errors="coerce")
            slip_df = df[cd_dates > pd.Timestamp(q_end_date)]
        else:
            slip_df = pd.DataFrame()
        slippage = {
            "count": len(slip_df),
            "acv": round(_sum(slip_df, "forecast_acv_amount"), 2) if not slip_df.empty else 0.0,
        }

        # ── Yesterday deltas ──────────────────────────────────────────────────
        yest_snap = self._yesterday_snap(snap)
        delta_yesterday = None
        cats_delta_yesterday = None
        slip_delta_yesterday = None
        if yest_snap:
            y_opps, _ = self._scoped_opps(yest_snap, filter_spec=fs, target_date=eff_as_of_date)
            y_df   = _opps_to_df(y_opps)
            y_total_count = len(y_df)
            y_total_acv   = round(_sum(y_df, "forecast_acv_amount"), 2) if not y_df.empty else 0.0
            y_cats = self._category_summary(y_df)
            y_slip_df = y_df[pd.to_datetime(y_df["close_date"]).dt.date > q_end_date] if not y_df.empty else pd.DataFrame()
            delta_yesterday = {
                "count": total_count - y_total_count,
                "acv":   round(total_acv - y_total_acv, 2),
                "snapshot_date": yest_snap.snapshot_date.isoformat(),
            }
            cats_delta_yesterday = {
                fc: {
                    "count": cats[fc]["count"] - y_cats[fc]["count"],
                    "acv":   round(cats[fc]["acv"] - y_cats[fc]["acv"], 2),
                }
                for fc in ALL_FC
            }
            slip_delta_yesterday = {
                "count": slippage["count"] - len(y_slip_df),
                "acv":   round(slippage["acv"] - _sum(y_slip_df, "forecast_acv_amount"), 2),
            }

        # ── Last-week deltas ──────────────────────────────────────────────────
        lw_snap = self._lastweek_snap(snap)
        delta_lastweek = None
        cats_delta_lastweek = None
        slip_delta_lastweek = None
        if lw_snap:
            lw_opps, _ = self._scoped_opps(lw_snap, filter_spec=fs, target_date=eff_as_of_date)
            lw_df   = _opps_to_df(lw_opps)
            lw_total_count = len(lw_df)
            lw_total_acv   = round(_sum(lw_df, "forecast_acv_amount"), 2) if not lw_df.empty else 0.0
            lw_cats = self._category_summary(lw_df)
            lw_slip_df = lw_df[pd.to_datetime(lw_df["close_date"]).dt.date > q_end_date] if not lw_df.empty else pd.DataFrame()
            delta_lastweek = {
                "count": total_count - lw_total_count,
                "acv":   round(total_acv - lw_total_acv, 2),
                "snapshot_date": lw_snap.snapshot_date.isoformat(),
            }
            cats_delta_lastweek = {
                fc: {
                    "count": cats[fc]["count"] - lw_cats[fc]["count"],
                    "acv":   round(cats[fc]["acv"] - lw_cats[fc]["acv"], 2),
                }
                for fc in ALL_FC
            }
            slip_delta_lastweek = {
                "count": slippage["count"] - len(lw_slip_df),
                "acv":   round(slippage["acv"] - _sum(lw_slip_df, "forecast_acv_amount"), 2),
            }

        # ── Other regions notice ──────────────────────────────────────────────
        other_count = 0
        if not df.empty:
            other_count = int((df["canonical_region"] == "Other").sum())

        # Proposal confirmation totals for summary
        prop_totals = {
            "approved_count": int((df["approval_status"] == "Approved").sum()) if not df.empty and "approval_status" in df.columns else 0,
            "pending_count":  int((df["approval_status"] == "Pending Approval").sum()) if not df.empty and "approval_status" in df.columns else 0,
            "blank_count":    int((df["approval_status"] == "Blank").sum()) if not df.empty and "approval_status" in df.columns else 0,
            "approved_acv":   _sum(df[df["approval_status"] == "Approved"] if not df.empty and "approval_status" in df.columns else pd.DataFrame(), "forecast_acv_amount"),
            "pending_acv":    _sum(df[df["approval_status"] == "Pending Approval"] if not df.empty and "approval_status" in df.columns else pd.DataFrame(), "forecast_acv_amount"),
            "blank_acv":      _sum(df[df["approval_status"] == "Blank"] if not df.empty and "approval_status" in df.columns else pd.DataFrame(), "forecast_acv_amount"),
        }

        return {
            "snapshot_date":    snap.snapshot_date.isoformat(),
            "requested_as_of":  fs.as_of or snap.snapshot_date.isoformat(),
            "snapshot_id":      snap.id,
            "data_slice":       data_slice,
            "data_slice_key":   target_fp,
            "exclude_deleted":  not fs.include_deleted_lost,
            "other_region_count": other_count,
            "filters_applied":  res.filters_applied,
            # Section 1
            "total": {
                "count": total_count,
                "acv":   total_acv,
                "delta_yesterday": delta_yesterday,
                "delta_lastweek":  delta_lastweek,
            },
            # Section 2 — category cards (standard ALL_FC + any dynamic new categories)
            "categories": {
                fc: {
                    **cats[fc],
                    "delta_yesterday": cats_delta_yesterday.get(fc) if cats_delta_yesterday else None,
                    "delta_lastweek":  cats_delta_lastweek.get(fc) if cats_delta_lastweek else None,
                }
                for fc in cats.keys()
            },
            # Section 3 — slippage
            "slippage_to_2027": {
                **slippage,
                "delta_yesterday": slip_delta_yesterday,
                "delta_lastweek":  slip_delta_lastweek,
            },
            "proposal_confirmation_totals": prop_totals,
            "source_checks": {
                "total": len(snap.checks),
                "passed": sum(1 for c in snap.checks if c.status == "pass"),
                "failed": sum(1 for c in snap.checks if c.status == "fail"),
                "badge": "red" if any(c.status == "fail" for c in snap.checks) else ("green" if len(snap.checks) > 0 else "none"),
            },
        }

    def get_movements(
        self,
        ctx: UserContext,
        compare: Optional[str] = None,
        exclude_deleted: bool = False,
        filter_spec: Optional[ScopeService.FilterSpec] = None,
    ) -> dict:
        """
        Section 4: Forecast Category Movement + Approval Movement.
        compare: 'yesterday' | 'last_week'
        """
        from backend.services.scopes import FilterSpec
        fs = filter_spec.model_copy() if filter_spec else FilterSpec()
        if compare:
            fs.compare = compare
        if exclude_deleted:
            fs.include_deleted_lost = False

        snap = self._active_snap(fs.as_of)
        if snap is None:
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
        today_df = _opps_to_df(opps)

        comp = fs.compare if fs.compare in ("yesterday", "last_week") else "yesterday"
        prev_snap = self._yesterday_snap(snap) if comp == "yesterday" else self._lastweek_snap(snap)
        if prev_snap is None:
            return {
                "compare": comp,
                "compare_date": None,
                "data_slice": res.data_slice,
                "filters_applied": res.filters_applied,
                "positive": [], "negative": [], "approval": [],
                "slippage_to_2027": {"count": 0, "acv": 0.0},
                "slipped_later_quarter": {"count": 0, "acv": 0.0},
                "slipped_earlier": {"count": 0, "acv": 0.0},
            }

        prev_opps, _ = self._scoped_opps(prev_snap, filter_spec=fs, target_date=eff_as_of_date)
        prev_df   = _opps_to_df(prev_opps)

        # Get ALL renewals opps for today to see where prev_df deals went
        q = self.db.query(Opportunity).filter(
            Opportunity.snapshot_id == snap.id,
            ScopeService.is_renewals()
        )
        if not fs.include_deleted_lost:
            q = q.filter(Opportunity.is_deleted_or_lost == False)
        today_all_df = _opps_to_df(q.all())

        target_fp = res.resolved_quarter
        moves = self._movements(today_df, prev_df, today_all_df, target_fp)
        return {
            "compare": comp,
            "compare_date": prev_snap.snapshot_date.isoformat(),
            "data_slice": res.data_slice,
            "filters_applied": res.filters_applied,
            **moves,
        }

    def get_regional_breakdown(
        self,
        ctx: UserContext,
        exclude_deleted: bool = False,
        filter_spec: Optional[ScopeService.FilterSpec] = None,
    ) -> dict:
        from backend.services.scopes import FilterSpec
        fs = filter_spec.model_copy() if filter_spec else FilterSpec()
        if exclude_deleted:
            fs.include_deleted_lost = False

        snap = self._active_snap(fs.as_of)
        if snap is None:
            return {"error": "no_snapshot"}

        opps, res = self._scoped_opps(snap, filter_spec=fs)
        df = _opps_to_df(opps)
        
        yest_snap = self._yesterday_snap(snap)
        y_opps, _ = self._scoped_opps(yest_snap, filter_spec=fs, target_date=snap.snapshot_date) if yest_snap else ([], None)
        y_df = _opps_to_df(y_opps)
        
        lw_snap = self._lastweek_snap(snap)
        lw_opps, _ = self._scoped_opps(lw_snap, filter_spec=fs, target_date=snap.snapshot_date) if lw_snap else ([], None)
        lw_df = _opps_to_df(lw_opps)

        regions = list(CANONICAL_REGIONS)
        if not df.empty and "Other" in df["canonical_region"].values:
            regions.append("Other")

        prop_rows = []
        for region in regions:
            r_df = df[df["canonical_region"] == region] if not df.empty else pd.DataFrame()
            prop_rows.append({
                "region": region,
                "total_acv":    round(_sum(r_df, "forecast_acv_amount"), 2),
                "approved_count": int((r_df["approval_status"] == "Approved").sum()) if not r_df.empty and "approval_status" in r_df.columns else 0,
                "pending_count":  int((r_df["approval_status"] == "Pending Approval").sum()) if not r_df.empty and "approval_status" in r_df.columns else 0,
                "blank_count":    int((r_df["approval_status"] == "Blank").sum()) if not r_df.empty and "approval_status" in r_df.columns else 0,
                "approved_acv":  round(_sum(r_df[r_df["approval_status"] == "Approved"] if not r_df.empty and "approval_status" in r_df.columns else pd.DataFrame(), "forecast_acv_amount"), 2),
                "pending_acv":   round(_sum(r_df[r_df["approval_status"] == "Pending Approval"] if not r_df.empty and "approval_status" in r_df.columns else pd.DataFrame(), "forecast_acv_amount"), 2),
                "blank_acv":     round(_sum(r_df[r_df["approval_status"] == "Blank"] if not r_df.empty and "approval_status" in r_df.columns else pd.DataFrame(), "forecast_acv_amount"), 2),
            })

        prop_totals = {
            "region": "Total",
            "total_acv":     round(_sum(df, "forecast_acv_amount"), 2),
            "approved_count": int((df["approval_status"] == "Approved").sum()) if not df.empty and "approval_status" in df.columns else 0,
            "pending_count":  int((df["approval_status"] == "Pending Approval").sum()) if not df.empty and "approval_status" in df.columns else 0,
            "blank_count":    int((df["approval_status"] == "Blank").sum()) if not df.empty and "approval_status" in df.columns else 0,
        }

        trend_rows = []
        for region in regions:
            r_df = df[df["canonical_region"] == region] if not df.empty else pd.DataFrame()
            y_r_df = y_df[y_df["canonical_region"] == region] if not y_df.empty else pd.DataFrame()
            lw_r_df = lw_df[lw_df["canonical_region"] == region] if not lw_df.empty else pd.DataFrame()
            
            row = {
                "region":       region,
                "total_count":  len(r_df),
                "total_acv":    round(_sum(r_df, "forecast_acv_amount"), 2),
                "y_total_count": len(y_r_df),
                "y_total_acv":  round(_sum(y_r_df, "forecast_acv_amount"), 2),
                "lw_total_count": len(lw_r_df),
                "lw_total_acv": round(_sum(lw_r_df, "forecast_acv_amount"), 2),
            }
            for fc in ALL_FC:
                fc_key = fc.lower().replace(" ", "_")
                
                fc_df = r_df[r_df["forecast_category"] == fc] if not r_df.empty and "forecast_category" in r_df.columns else pd.DataFrame()
                row[f"{fc_key}_count"] = len(fc_df)
                row[f"{fc_key}_acv"]   = round(_sum(fc_df, "forecast_acv_amount"), 2)
                
                y_fc_df = y_r_df[y_r_df["forecast_category"] == fc] if not y_r_df.empty and "forecast_category" in y_r_df.columns else pd.DataFrame()
                row[f"y_{fc_key}_count"] = len(y_fc_df)
                row[f"y_{fc_key}_acv"]   = round(_sum(y_fc_df, "forecast_acv_amount"), 2)
                
                lw_fc_df = lw_r_df[lw_r_df["forecast_category"] == fc] if not lw_r_df.empty and "forecast_category" in lw_r_df.columns else pd.DataFrame()
                row[f"lw_{fc_key}_count"] = len(lw_fc_df)
                row[f"lw_{fc_key}_acv"]   = round(_sum(lw_fc_df, "forecast_acv_amount"), 2)
                
            trend_rows.append(row)

        total_row = {"region": "Total", "total_count": len(df), "total_acv": round(_sum(df, "forecast_acv_amount"), 2),
                     "y_total_count": len(y_df), "y_total_acv": round(_sum(y_df, "forecast_acv_amount"), 2),
                     "lw_total_count": len(lw_df), "lw_total_acv": round(_sum(lw_df, "forecast_acv_amount"), 2)}
                     
        for fc in ALL_FC:
            fc_key = fc.lower().replace(" ", "_")
            fc_df = df[df["forecast_category"] == fc] if not df.empty and "forecast_category" in df.columns else pd.DataFrame()
            total_row[f"{fc_key}_count"] = len(fc_df)
            total_row[f"{fc_key}_acv"]   = round(_sum(fc_df, "forecast_acv_amount"), 2)
            
            y_fc_df = y_df[y_df["forecast_category"] == fc] if not y_df.empty and "forecast_category" in y_df.columns else pd.DataFrame()
            total_row[f"y_{fc_key}_count"] = len(y_fc_df)
            total_row[f"y_{fc_key}_acv"]   = round(_sum(y_fc_df, "forecast_acv_amount"), 2)
            
            lw_fc_df = lw_df[lw_df["forecast_category"] == fc] if not lw_df.empty and "forecast_category" in lw_df.columns else pd.DataFrame()
            total_row[f"lw_{fc_key}_count"] = len(lw_fc_df)
            total_row[f"lw_{fc_key}_acv"]   = round(_sum(lw_fc_df, "forecast_acv_amount"), 2)

        regional_sum = sum(r["total_acv"] for r in trend_rows)
        check_passes = abs(regional_sum - total_row["total_acv"]) < 0.01

        return {
            "data_slice": res.data_slice,
            "filters_applied": res.filters_applied,
            "proposal_confirmation": prop_rows,
            "proposal_confirmation_totals": prop_totals,
            "regional_trend": trend_rows,
            "regional_trend_totals": total_row,
            "regional_sum": round(regional_sum, 2),
            "total_acv_check_passes": check_passes,
            "other_count": int((df["canonical_region"] == "Other").sum()) if not df.empty and "canonical_region" in df.columns else 0,
        }

    def get_deals(
        self,
        ctx: UserContext,
        category: str | None = None,
        region: str | None = None,
        approval_status: str | None = None,
        kind: str | None = None,
        compare: str | None = None,
        exclude_deleted: bool = False,
        as_of: str | None = None,
        filter_spec: Optional[ScopeService.FilterSpec] = None,
    ) -> dict:
        from backend.services.scopes import FilterSpec
        fs = filter_spec.model_copy() if filter_spec else FilterSpec()
        if as_of:
            fs.as_of = as_of
        if exclude_deleted:
            fs.include_deleted_lost = False
        if category:
            fs.forecast_categories = [category]
        if region:
            fs.regions = [region]
        if approval_status:
            fs.approval_statuses = [approval_status]

        snap = self._active_snap(fs.as_of)
        if snap is None:
            return {"count": 0, "acv": 0.0, "filters_applied": {}, "deals": []}

        filters_applied: dict[str, str] = {}
        if category:
            filters_applied["category"] = category
        if region:
            filters_applied["region"] = region
        if approval_status:
            filters_applied["approval_status"] = approval_status
        if kind:
            filters_applied["kind"] = kind
        if compare:
            filters_applied["compare"] = compare

        # ── Kind: slipped ─────────────────────────────────────────────────────
        if kind == "slipped":
            comp = compare if compare in ("yesterday", "last_week") else "yesterday"
            moves = self.get_movements(ctx, compare=comp, exclude_deleted=exclude_deleted)
            slip = moves.get("slippage_to_2027") or {"count": 0, "acv": 0.0, "deals": []}
            raw_deals = slip.get("deals", [])
            # Map deal fields consistently
            records = []
            for d in raw_deals:
                records.append({
                    "id": str(d.get("opportunity_id_18", "")),
                    "opportunity_id_18": str(d.get("opportunity_id_18", "")),
                    "opportunity_name": str(d.get("opportunity_name", "")),
                    "account_name": str(d.get("account_name", "")),
                    "forecast_category": str(d.get("forecast_category", "")),
                    "forecast_acv_amount": float(d.get("forecast_acv_amount") or d.get("acv") or 0),
                    "approval_status": str(d.get("approval_status", "")),
                    "sub_region": str(d.get("canonical_region") or d.get("region") or ""),
                    "business_unit_primary": str(d.get("business_unit_primary", "")),
                    "close_date": d.get("close_date"),
                })
            return {
                "count": slip.get("count", len(records)),
                "acv": round(float(slip.get("acv", sum(r["forecast_acv_amount"] for r in records))), 2),
                "filters_applied": filters_applied,
                "deals": records,
            }

        opps, res = self._scoped_opps(snap, filter_spec=fs)
        df = _opps_to_df(opps)
        if df.empty:
            return {"count": 0, "acv": 0.0, "filters_applied": res.filters_applied, "deals": []}

        if kind in ("delta_yesterday", "delta_lastweek"):
            prev_snap = self._yesterday_snap(snap) if kind == "delta_yesterday" else self._lastweek_snap(snap)
            if prev_snap:
                prev_opps = self._q4_opps(prev_snap, exclude_deleted=exclude_deleted, target_date=snap.snapshot_date)
                prev_df = _opps_to_df(prev_opps)

                t_map = {str(r["opportunity_id_18"]): r for _, r in df.iterrows()}
                p_map = {str(r["opportunity_id_18"]): r for _, r in prev_df.iterrows()} if not prev_df.empty else {}

                added_deals = []
                for oid, tr in t_map.items():
                    if oid not in p_map:
                        deal = {
                            "id": str(tr["opportunity_id_18"]),
                            "opportunity_id_18": str(tr["opportunity_id_18"]),
                            "opportunity_name": str(tr["opportunity_name"]),
                            "account_name": str(tr["account_name"]),
                            "forecast_category": str(tr["forecast_category"]),
                            "forecast_acv_amount": float(tr["forecast_acv_amount"] or 0),
                            "approval_status": str(tr["approval_status"]),
                            "sub_region": str(tr["canonical_region"]),
                            "business_unit_primary": str(tr["business_unit_primary"]),
                            "close_date": tr["close_date"].isoformat() if hasattr(tr["close_date"], "isoformat") else str(tr["close_date"]) if tr["close_date"] else None,
                            "delta_group": "Added to Q4",
                            "delta_acv_change": float(tr["forecast_acv_amount"] or 0),
                        }
                        added_deals.append(deal)

                left_deals = []
                for oid, pr in p_map.items():
                    if oid not in t_map:
                        deal = {
                            "id": str(pr["opportunity_id_18"]),
                            "opportunity_id_18": str(pr["opportunity_id_18"]),
                            "opportunity_name": str(pr["opportunity_name"]),
                            "account_name": str(pr["account_name"]),
                            "forecast_category": str(pr["forecast_category"]),
                            "forecast_acv_amount": float(pr["forecast_acv_amount"] or 0),
                            "approval_status": str(pr["approval_status"]),
                            "sub_region": str(pr["canonical_region"]),
                            "business_unit_primary": str(pr["business_unit_primary"]),
                            "close_date": pr["close_date"].isoformat() if hasattr(pr["close_date"], "isoformat") else str(pr["close_date"]) if pr["close_date"] else None,
                            "delta_group": "Left Q4 – moved or lost",
                            "delta_acv_change": -float(pr["forecast_acv_amount"] or 0),
                        }
                        left_deals.append(deal)

                changed_deals = []
                for oid in t_map:
                    if oid in p_map:
                        tr = t_map[oid]
                        pr = p_map[oid]
                        diff = round(float(tr["forecast_acv_amount"] or 0) - float(pr["forecast_acv_amount"] or 0), 2)
                        if abs(diff) > 0.001:
                            deal = {
                                "id": str(tr["opportunity_id_18"]),
                                "opportunity_id_18": str(tr["opportunity_id_18"]),
                                "opportunity_name": str(tr["opportunity_name"]),
                                "account_name": str(tr["account_name"]),
                                "forecast_category": str(tr["forecast_category"]),
                                "forecast_acv_amount": float(tr["forecast_acv_amount"] or 0),
                                "approval_status": str(tr["approval_status"]),
                                "sub_region": str(tr["canonical_region"]),
                                "business_unit_primary": str(tr["business_unit_primary"]),
                                "close_date": tr["close_date"].isoformat() if hasattr(tr["close_date"], "isoformat") else str(tr["close_date"]) if tr["close_date"] else None,
                                "delta_group": "Amount changed",
                                "delta_acv_change": diff,
                            }
                            changed_deals.append(deal)

                added_acv = round(sum(d["forecast_acv_amount"] for d in added_deals), 2)
                left_acv = round(sum(d["forecast_acv_amount"] for d in left_deals), 2)
                changed_diff = round(sum(d["delta_acv_change"] for d in changed_deals), 2)

                # Net calculations
                net_count = len(df) - len(prev_df)
                net_acv = round(float(_sum(df, "forecast_acv_amount") - _sum(prev_df, "forecast_acv_amount")), 2)

                all_delta_deals = added_deals + left_deals + changed_deals

                delta_groups = {
                    "added": {
                        "name": f"Added to Q4 ({len(added_deals)})",
                        "count": len(added_deals),
                        "acv": added_acv,
                        "deals": added_deals,
                    },
                    "left": {
                        "name": f"Left Q4 – moved or lost ({len(left_deals)})",
                        "count": len(left_deals),
                        "acv": left_acv,
                        "deals": left_deals,
                    },
                    "amount_changed": {
                        "name": f"Amount changed ({len(changed_deals)})",
                        "count": len(changed_deals),
                        "acv": changed_diff,
                        "deals": changed_deals,
                    },
                    "net": {
                        "count": net_count,
                        "acv": net_acv,
                    }
                }

                return {
                    "count": net_count,
                    "acv": net_acv,
                    "filters_applied": filters_applied,
                    "delta_groups": delta_groups,
                    "deals": all_delta_deals,
                }


        if category:
            df = df[df["forecast_category"] == category]

        if region and region != "Total":
            df = df[df["canonical_region"] == region]

        if approval_status and approval_status != "Total":
            df = df[df["approval_status"] == approval_status]

        records = []
        for _, r in df.iterrows():
            records.append({
                "id": str(r["opportunity_id_18"]),
                "opportunity_id_18": str(r["opportunity_id_18"]),
                "opportunity_name": str(r["opportunity_name"]),
                "account_name": str(r["account_name"]),
                "forecast_category": str(r["forecast_category"]),
                "forecast_acv_amount": float(r["forecast_acv_amount"] or 0),
                "approval_status": str(r["approval_status"]),
                "sub_region": str(r["canonical_region"]),
                "business_unit_primary": str(r["business_unit_primary"]),
                "close_date": r["close_date"].isoformat() if hasattr(r["close_date"], "isoformat") else str(r["close_date"]) if r["close_date"] else None,
            })
        return {
            "count": len(records),
            "acv": round(sum(r["forecast_acv_amount"] for r in records), 2),
            "filters_applied": res.filters_applied,
            "deals": records,
        }

