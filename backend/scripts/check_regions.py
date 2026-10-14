import sys, os
sys.path.insert(0, os.path.abspath('.'))
from backend.database import SessionLocal
from backend.models.snapshot import UploadSnapshot
from backend.models.opportunity import Opportunity
from sqlalchemy import func

db = SessionLocal()
snap = db.query(UploadSnapshot).filter(UploadSnapshot.is_active_today == True).first()
if not snap:
    snap = db.query(UploadSnapshot).order_by(UploadSnapshot.snapshot_date.desc()).first()

print(f"Active snapshot: {snap.snapshot_date} (id={snap.id})")
regs = db.query(
    Opportunity.sub_region,
    func.count(Opportunity.id),
    func.sum(Opportunity.forecast_acv_amount)
).filter(Opportunity.snapshot_id == snap.id).group_by(Opportunity.sub_region).all()

print(f"\nRegions ({len(regs)}):")
for r in sorted(regs, key=lambda x: float(x[2] or 0), reverse=True):
    print(f"  {r[0]}: count={r[1]}, acv=${float(r[2] or 0):,.2f}")

db.close()
