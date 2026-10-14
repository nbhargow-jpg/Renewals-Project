import sys, os
sys.path.insert(0, os.path.abspath('.'))
from backend.database import SessionLocal
from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot
from sqlalchemy import func

db = SessionLocal()
for s in db.query(UploadSnapshot).all():
    print(f"\n--- Snapshot {s.snapshot_date} (id={s.id}) ---")
    tot_acv = db.query(func.sum(Opportunity.forecast_acv_amount)).filter(Opportunity.snapshot_id == s.id).scalar()
    cnt = db.query(func.count(Opportunity.id)).filter(Opportunity.snapshot_id == s.id).scalar()
    print(f"Total Opps: {cnt}, Total ACV: {tot_acv:,.2f}")
    
    # approval status counts
    apps = db.query(Opportunity.approval_status, func.count(Opportunity.id)).filter(Opportunity.snapshot_id == s.id).group_by(Opportunity.approval_status).all()
    print(f"Approvals: {apps}")
    
    # forecast category counts
    fcs = db.query(Opportunity.forecast_category, func.count(Opportunity.id)).filter(Opportunity.snapshot_id == s.id).group_by(Opportunity.forecast_category).all()
    print(f"Forecast Categories: {fcs}")

db.close()
