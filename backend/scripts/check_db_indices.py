import sys, os
sys.path.insert(0, os.path.abspath('.'))
from backend.database import SessionLocal
from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot

db = SessionLocal()
s = db.query(UploadSnapshot).filter_by(snapshot_date='2026-10-05').first() or db.query(UploadSnapshot).first()

o1 = db.query(Opportunity).filter_by(snapshot_id=s.id, opportunity_id_18='006Qp00000YdMgGIAV').first()
o2 = db.query(Opportunity).filter_by(snapshot_id=s.id, opportunity_id_18='006Qp00000eV7mAIAS').first()

print(f"o1 (YdMg): id={o1.id}, row={o1.opportunity_id_18}")
print(f"o2 (eV7m): id={o2.id}, row={o2.opportunity_id_18}")

# Check all opportunities in this snapshot
opps = db.query(Opportunity).filter_by(snapshot_id=s.id).all()
idx1 = [i for i, o in enumerate(opps) if o.opportunity_id_18 == '006Qp00000YdMgGIAV']
idx2 = [i for i, o in enumerate(opps) if o.opportunity_id_18 == '006Qp00000eV7mAIAS']
print("Index in opps list: idx1=", idx1, "idx2=", idx2)
db.close()
