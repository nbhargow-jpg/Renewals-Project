import sys
sys.path.insert(0, '.')
from backend.services.analytics_service import AnalyticsService, _opps_to_df
from backend.database import SessionLocal
from backend.services.context import UserContext
from backend.models.snapshot import UploadSnapshot

db = SessionLocal()
svc = AnalyticsService(db)
ctx = UserContext()

# Test history overview logic
snaps = db.query(UploadSnapshot).order_by(UploadSnapshot.snapshot_date.asc()).all()
for s in snaps:
    df = _opps_to_df(svc._opps_for(s))
    print(f"Snap {s.snapshot_date} ({s.label}): {len(df)} rows, ${df['forecast_acv_amount'].sum():,.2f}")

db.close()
