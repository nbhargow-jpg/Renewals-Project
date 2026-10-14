import sys
sys.path.insert(0, '.')
from backend.services.analytics_service import AnalyticsService
from backend.database import SessionLocal
from backend.services.context import UserContext
from backend.models.snapshot import UploadSnapshot

db = SessionLocal()
svc = AnalyticsService(db)
ctx = UserContext()

today_snap = db.query(UploadSnapshot).filter(UploadSnapshot.label == 'Today').first()
yesterday_snap = db.query(UploadSnapshot).filter(UploadSnapshot.label == 'Yesterday').first()

print(f"Today ID: {today_snap.id}, Yesterday ID: {yesterday_snap.id}")

# Let's inspect sub-region reference figures:
expected = {
    "North America": (328, 79885241.32, "Verizon_AMC", 4968375.00),
    "West Europe": (912, 77950209.50, "OFR RR", 4563084.65),
    "Middle East": (374, 74343552.73, "Mobilis", 13800000.00),
    "AFRICA": (390, 71672803.13, "CAK", 4000000.00),
    "SEAO": (338, 48958583.57, None, None),
    "South America": (276, 35055573.86, "AMX", 1032629.03),
    "NASA": (170, 34506916.51, "NTT", 4000000.00),
    "East Europe": (292, 19139173.92, "Azercell", 912616.93),
    "NAMR GUAVUS": (6, 8528196.00, "Verizon Guavus", 5435136.00),
}

from backend.models.opportunity import Opportunity
import pandas as pd

opps = db.query(Opportunity).filter(Opportunity.snapshot_id == today_snap.id).all()
df = pd.DataFrame([{
    'opportunity_id_18': o.opportunity_id_18,
    'opportunity_name': o.opportunity_name,
    'sub_region': o.sub_region,
    'business_unit': o.business_unit_primary,
    'acv': float(o.forecast_acv_amount or 0),
} for o in opps])

for r_name, (exp_count, exp_acv, top_needle, top_acv) in expected.items():
    rdf = df[df['sub_region'] == r_name].sort_values('acv', ascending=False)
    actual_count = len(rdf)
    actual_acv = round(rdf['acv'].sum(), 2)
    assert actual_count == exp_count, f"{r_name} count {actual_count} != {exp_count}"
    assert actual_acv == exp_acv, f"{r_name} ACV {actual_acv} != {exp_acv}"
    if top_needle:
        top_row = rdf.iloc[0]
        assert top_needle in top_row['opportunity_name'], f"{r_name} top opp name mismatch: {top_row['opportunity_name']}"
        assert round(top_row['acv'], 2) == top_acv, f"{r_name} top opp acv {top_row['acv']} != {top_acv}"
    print(f"PASS: {r_name} -> {actual_count} opps, ${actual_acv:,.2f}")

print("\nALL 9 SUB-REGIONS MATCH EXACTLY TO THE CENT!")
db.close()
