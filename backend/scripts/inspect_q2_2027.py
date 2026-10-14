import sys, os
sys.path.insert(0, os.path.abspath('.'))
from backend.database import SessionLocal
from backend.models.snapshot import UploadSnapshot
from backend.models.opportunity import Opportunity

db = SessionLocal()
for s in db.query(UploadSnapshot).order_by(UploadSnapshot.snapshot_date).all():
    opps = db.query(Opportunity).filter(Opportunity.snapshot_id==s.id, Opportunity.service_expiry_period=='Q2-2027').all()
    print(s.snapshot_date, s.label)
    for o in opps:
        print(f"   {o.opportunity_id_18} | cat={o.forecast_category} | acv={o.forecast_acv_amount}")
db.close()
