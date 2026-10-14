import sys, os
sys.path.insert(0, os.path.abspath('.'))
from backend.database import SessionLocal, init_db
from backend.models.snapshot import UploadSnapshot
from backend.models.opportunity import Opportunity

init_db()
db = SessionLocal()
snaps = db.query(UploadSnapshot).all()
print(f"Snapshots in db: {len(snaps)}")
for s in snaps:
    opps_cnt = db.query(Opportunity).filter(Opportunity.snapshot_id == s.id).count()
    print(f"  ID: {s.id}, Date: {s.snapshot_date}, Label: {s.label}, Opps: {opps_cnt}")
db.close()
