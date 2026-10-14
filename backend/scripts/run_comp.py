import sys, os
from datetime import date
sys.path.insert(0, os.path.abspath('.'))
from backend.database import SessionLocal
from backend.services.analytics_service import AnalyticsService
from backend.services.context import ADMIN_CONTEXT

db = SessionLocal()
svc = AnalyticsService(db)
comp = svc.get_comparison(ADMIN_CONTEXT, date(2026, 10, 5), date(2026, 10, 6))

print("Keys in comparison:", list(comp.keys()))
print("\nCategories:")
for c in comp.get("categories", []):
    print(" ", c)

print("\nForecast movements:")
for fm in comp.get("forecast_movements", []):
    print(" ", fm)

print("\nBiggest movers (first 10):")
for bm in comp.get("biggest_movers", [])[:10]:
    print(" ", bm)

db.close()
