import sys, os
sys.path.insert(0, os.path.abspath('.'))
from backend.database import SessionLocal
from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot

db = SessionLocal()
snap = db.query(UploadSnapshot).filter(UploadSnapshot.is_active_today == True).first()
opps = db.query(Opportunity).filter(Opportunity.snapshot_id == snap.id).all()

regions = sorted(list(set(o.sub_region for o in opps if o.sub_region)))
for reg in regions:
    reg_opps = [o for o in opps if o.sub_region == reg]
    # max single opp per BU
    bu_max = {}
    for o in reg_opps:
        bu = o.business_unit_raw or "Unknown"
        val = float(o.forecast_acv_amount or 0)
        if bu not in bu_max or val > bu_max[bu]:
            bu_max[bu] = val
    
    bu = max(bu_max.keys(), key=lambda b: bu_max[b])
    
    # All opps in reg with this BU
    tot_opps = [o for o in reg_opps if (o.business_unit_raw or "Unknown") == bu]
    tot_acv = sum(float(o.forecast_acv_amount or 0) for o in tot_opps)
    print(f"{reg} – {bu}: ${tot_acv/1e6:,.2f}M across {len(tot_opps)} opportunities (max={bu_max[bu]:,.2f})")

db.close()
