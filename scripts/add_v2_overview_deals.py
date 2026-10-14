# Add get_deals to backend/services/v2_overview_service.py

get_deals_code = '''
    def get_deals(
        self,
        ctx: UserContext,
        category: str | None = None,
        region: str | None = None,
        approval_status: str | None = None,
        kind: str | None = None,
        exclude_deleted: bool = False,
        as_of: str | None = None,
    ) -> list[dict]:
        snap = self._active_snap(as_of)
        if snap is None:
            return []

        opps = self._q4_opps(snap, exclude_deleted=exclude_deleted)
        df = _opps_to_df(opps)
        if df.empty:
            return []

        if kind in ("delta_yesterday", "delta_lastweek"):
            prev_snap = self._yesterday_snap(snap) if kind == "delta_yesterday" else self._lastweek_snap(snap)
            if prev_snap:
                prev_opps = self._q4_opps(prev_snap, exclude_deleted=exclude_deleted, target_date=snap.snapshot_date)
                prev_df = _opps_to_df(prev_opps)
                # Deals in today not in prev, or where category/approval/acv/close_date changed
                today_indexed = df.set_index("opportunity_id_18")
                prev_indexed = prev_df.set_index("opportunity_id_18") if not prev_df.empty else pd.DataFrame()
                changed_ids = []
                for opp_id in today_indexed.index:
                    if opp_id not in prev_indexed.index:
                        changed_ids.append(opp_id)
                    else:
                        tr = today_indexed.loc[opp_id]
                        pr = prev_indexed.loc[opp_id]
                        fc_now = tr["forecast_category"] if isinstance(tr, pd.Series) else tr.iloc[0]["forecast_category"]
                        fc_prev = pr["forecast_category"] if isinstance(pr, pd.Series) else pr.iloc[0]["forecast_category"]
                        ap_now = tr["approval_status"] if isinstance(tr, pd.Series) else tr.iloc[0]["approval_status"]
                        ap_prev = pr["approval_status"] if isinstance(pr, pd.Series) else pr.iloc[0]["approval_status"]
                        acv_now = float(tr["forecast_acv_amount"] if isinstance(tr, pd.Series) else tr.iloc[0]["forecast_acv_amount"])
                        acv_prev = float(pr["forecast_acv_amount"] if isinstance(pr, pd.Series) else pr.iloc[0]["forecast_acv_amount"])
                        if fc_now != fc_prev or ap_now != ap_prev or acv_now != acv_prev:
                            changed_ids.append(opp_id)
                df = df[df["opportunity_id_18"].isin(changed_ids)]

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
        return records
'''

with open('backend/services/v2_overview_service.py', 'r', encoding='utf-8') as f:
    code = f.read()

if 'def get_deals(' not in code:
    code = code + get_deals_code
    with open('backend/services/v2_overview_service.py', 'w', encoding='utf-8', newline='\n') as f:
        f.write(code)
    print("Added get_deals to service")
else:
    print("get_deals already exists in service")

# Add router endpoint to backend/routers/v2_overview.py
router_endpoint = '''
@router.get("/deals")
def overview_deals(
    category: str = Query(None),
    region: str = Query(None),
    approval_status: str = Query(None),
    kind: str = Query(None),
    as_of: str = Query(None),
    exclude_deleted: bool = Query(False),
    svc: V2OverviewService = Depends(_svc),
    ctx: UserContext = Depends(get_user_context),
):
    return svc.get_deals(
        ctx,
        category=category,
        region=region,
        approval_status=approval_status,
        kind=kind,
        exclude_deleted=exclude_deleted,
        as_of=as_of,
    )
'''

with open('backend/routers/v2_overview.py', 'r', encoding='utf-8') as f:
    rcode = f.read()

if '@router.get("/deals")' not in rcode:
    rcode = rcode + router_endpoint
    with open('backend/routers/v2_overview.py', 'w', encoding='utf-8', newline='\n') as f:
        f.write(rcode)
    print("Added /deals to router")
else:
    print("/deals already in router")
