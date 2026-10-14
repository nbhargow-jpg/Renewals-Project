import sys, os
sys.path.insert(0, os.path.abspath('.'))
from backend.database import SessionLocal
from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot
from sqlalchemy import func

db = SessionLocal()
snap = db.query(UploadSnapshot).filter(UploadSnapshot.is_active_today == True).first()
opps = db.query(Opportunity).filter(Opportunity.snapshot_id == snap.id).all()

regions = sorted(list(set(o.sub_region for o in opps if o.sub_region)))
for reg in regions:
    reg_opps = [o for o in opps if o.sub_region == reg]
    # group by business_unit_raw
    bu_totals = {}
    for o in reg_opps:
        bu = o.business_unit_raw or "Unknown"
        if bu not in bu_totals:
            bu_totals[bu] = {"acv": 0.0, "count": 0, "opps": []}
        bu_totals[bu]["acv"] += float(o.forecast_acv_amount or 0)
        bu_totals[bu]["count"] += 1
        bu_totals[bu]["opps"].append(o)
    
    # leading BU by total ACV
    leading_bu = max(bu_totals.keys(), key=lambda b: bu_totals[b]["acv"])
    bu_stat = bu_totals[leading_bu]
    print(f"{reg}: Leading BU='{leading_bu}', ACV=${bu_stat['acv']/1e6:,.2f}M, Count={bu_stat['count']}")

db.close()
