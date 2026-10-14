import sys
sys.path.insert(0, '.')
from backend.services.analytics_service import AnalyticsService
from backend.database import SessionLocal
from backend.services.context import UserContext
from datetime import date

db = SessionLocal()
svc = AnalyticsService(db)
ctx = UserContext()

res = svc.get_comparison(ctx, date(2026, 10, 5), date(2026, 10, 6))
print("kpi_strip items:")
for k in res["kpi_strip"]:
    print(k)
db.close()
