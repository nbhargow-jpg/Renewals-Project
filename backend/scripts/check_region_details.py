import sys
sys.path.insert(0, '.')
from backend.services.analytics_service import AnalyticsService
from backend.database import SessionLocal
from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot
import pandas as pd

db = SessionLocal()
snap = db.query(UploadSnapshot).filter(UploadSnapshot.label == 'Today').first()
opps = db.query(Opportunity).filter(Opportunity.snapshot_id == snap.id).all()
df = pd.DataFrame([{
    'opportunity_id_18': o.opportunity_id_18,
    'opportunity_name': o.opportunity_name,
    'account_name': o.account_name,
    'sub_region': o.sub_region,
    'business_unit_primary': o.business_unit_primary,
    'business_unit_raw': o.business_unit_raw,
    'forecast_category': o.forecast_category or 'Blank',
    'approval_status': o.approval_status or 'Blank',
    'forecast_acv_amount': float(o.forecast_acv_amount or 0),
} for o in opps])

for sub_r in ['North America', 'West Europe', 'Middle East', 'AFRICA', 'SEAO', 'South America', 'NASA', 'East Europe', 'NAMR GUAVUS']:
    rdf = df[df['sub_region'] == sub_r].sort_values('forecast_acv_amount', ascending=False)
    top1 = rdf.iloc[0] if not rdf.empty else None
    leading_bu = top1['business_unit_primary'] if top1 is not None else None
    print(f"\n=== Region: {sub_r} ===")
    print(f"Total Opps: {len(rdf)}, Total ACV: ${rdf['forecast_acv_amount'].sum():,.2f}")
    if top1 is not None:
        print(f"Top 1 Opp: {top1['opportunity_id_18']} | {top1['opportunity_name']} | BU: {leading_bu} | ${top1['forecast_acv_amount']:,.2f}")
    if leading_bu:
        bu_df = rdf[rdf['business_unit_primary'] == leading_bu].sort_values('forecast_acv_amount', ascending=False)
        print(f"Leading BU ({leading_bu}) count in {sub_r}: {len(bu_df)}, Top opp in BU: ${bu_df.iloc[0]['forecast_acv_amount']:,.2f}")

db.close()
