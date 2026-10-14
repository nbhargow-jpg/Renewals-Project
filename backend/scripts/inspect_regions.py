from backend.database import SessionLocal
from backend.models import UploadSnapshot, Opportunity

db = SessionLocal()
s5 = db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == '2026-10-05').first()

regions = [
    "North America", "West Europe", "Middle East", "AFRICA",
    "SEAO", "South America", "NASA", "East Europe", "NAMR GUAVUS"
]

for reg in regions:
    opps = db.query(Opportunity).filter(
        Opportunity.snapshot_id == s5.id,
        Opportunity.sub_region == reg
    ).order_by(Opportunity.forecast_acv_amount.desc()).limit(3).all()
    print(f"=== {reg} ===")
    for o in opps:
        print(f"ID: {o.opportunity_id_18} | Name: {o.opportunity_name!r} | BU Raw: {o.business_unit_raw!r} | BU Prim: {o.business_unit_primary!r} | ACV: {o.forecast_acv_amount}")
