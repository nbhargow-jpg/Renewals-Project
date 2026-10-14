import sys, os
sys.path.insert(0, os.path.abspath('.'))
from backend.database import SessionLocal
from backend.models.snapshot import UploadSnapshot

db = SessionLocal()
for s in db.query(UploadSnapshot).all():
    print(f"ID: {s.id}, Date: {s.snapshot_date}, Label: {s.label}, Created: {s.created_at}, Notes: {s.notes}")
db.close()
