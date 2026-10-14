import sys, os
sys.path.insert(0, os.path.abspath('.'))
from backend.database import SessionLocal
from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot

db = SessionLocal()
s = db.query(UploadSnapshot).filter_by(snapshot_date='2026-10-05').first() or db.query(UploadSnapshot).first()
opps = db.query(Opportunity).filter_by(snapshot_id=s.id, sub_region='North America').order_by(Opportunity.forecast_acv_amount.desc()).all()
for i, o in enumerate(opps[8:14], 9):
    print(i, o.opportunity_id_18, o.opportunity_name, float(o.forecast_acv_amount))
db.close()
