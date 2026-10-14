import sys, os
sys.path.insert(0, os.path.abspath('.'))
from backend.database import SessionLocal
from backend.models.change_log import ChangeLog, ForecastMovementLog

db = SessionLocal()
cl_cnt = db.query(ChangeLog).count()
fml_cnt = db.query(ForecastMovementLog).count()
print(f"ChangeLog count: {cl_cnt}, ForecastMovementLog count: {fml_cnt}")

# Sample changelogs by change_type
types = db.query(ChangeLog.change_type).distinct().all()
print("ChangeLog types:", [t[0] for t in types])

# Sample forecast movements
fms = db.query(ForecastMovementLog).all()
print(f"Forecast movements ({len(fms)}):", [(f.movement_label, f.opportunity_count) for f in fms[:10]])

db.close()
