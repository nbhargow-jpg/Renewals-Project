import sys
sys.path.insert(0, '.')
from backend.services.analytics_service import AnalyticsService, _opps_to_df
from backend.database import SessionLocal
from backend.services.context import UserContext
from backend.models.snapshot import UploadSnapshot
from backend.models.opportunity import Opportunity
import pandas as pd

db = SessionLocal()
svc = AnalyticsService(db)
ctx = UserContext()

today_snap = db.query(UploadSnapshot).filter(UploadSnapshot.label == 'Today').first()
yesterday_snap = db.query(UploadSnapshot).filter(UploadSnapshot.label == 'Yesterday').first()

opps = db.query(Opportunity).filter(Opportunity.snapshot_id == today_snap.id).all()
df = _opps_to_df(opps)
print("DF columns:", df.columns.tolist())

# Group by sub_region
reg_agg = df.groupby('sub_region', dropna=False).agg(
    count=('opportunity_id_18', 'count'),
    acv=('forecast_acv_amount', 'sum')
).reset_index().sort_values('acv', ascending=False)

for _, r in reg_agg.iterrows():
    s_reg = r['sub_region']
    sub_df = df[df['sub_region'] == s_reg].sort_values('forecast_acv_amount', ascending=False)
    top_opp = sub_df.iloc[0] if not sub_df.empty else None
    leading_bu = top_opp['business_unit_primary'] if top_opp is not None else None
    bu_sub_df = sub_df[sub_df['business_unit_primary'] == leading_bu] if leading_bu else pd.DataFrame()
    print(f"Region: {s_reg:15} | Count: {r['count']:4} | ACV: ${r['acv']:13,.2f} | Top: {top_opp['opportunity_name'][:30]:30} | BU: {leading_bu:15} (bu opps: {len(bu_sub_df)})")

db.close()
