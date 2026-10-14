import sys, os
from datetime import date
sys.path.insert(0, os.path.abspath('.'))
from backend.database import SessionLocal
from backend.services.analytics_service import AnalyticsService
from backend.services.context import ADMIN_CONTEXT

db = SessionLocal()
svc = AnalyticsService(db)
comp = svc.get_comparison(ADMIN_CONTEXT, date(2026, 10, 5), date(2026, 10, 6))

for fc in comp.get("forecast_category", []):
    print(fc)
db.close()
