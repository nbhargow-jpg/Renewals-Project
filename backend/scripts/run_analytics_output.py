import sys, os
sys.path.insert(0, os.path.abspath('.'))
from backend.database import SessionLocal
from backend.services.analytics_service import AnalyticsService
from backend.services.context import ADMIN_CONTEXT
from backend.models.snapshot import UploadSnapshot

db = SessionLocal()
svc = AnalyticsService(db)

# 1. Active snapshot
snap = svc.get_active_snapshot(ADMIN_CONTEXT)
print(f"Active snapshot: {snap.snapshot_date} (id={snap.id})")

# 2. Forecast summary
fs = svc.get_forecast_summary(ADMIN_CONTEXT, snapshot_id=snap.id)
totals = fs.get("totals", {})
print("\nForecast summary totals:", totals)

# 3. Approval status
aps = svc.get_approval_status(ADMIN_CONTEXT, snapshot_id=snap.id)
print("\nApproval status rows:")
for r in aps.get("rows", []):
    print(f"  {r['approval_status']}: count={r['count']}, acv=${r['acv']:,.2f}")
print("Approval changes:", aps.get("changes", {}))

# 4. BU Approval
bu_aps = svc.get_approval_by_bu(ADMIN_CONTEXT, snapshot_id=snap.id, mode="as_in_excel")
print(f"\nBU Approval rows count: {len(bu_aps.get('rows', []))}")
for r in bu_aps.get("rows", [])[:5]:
    print(f"  {r['business_unit']}: count={r['total_count']}")
print("BU Total row:", bu_aps.get("total", {}))

# 5. Top regions
tr = svc.get_top_regions(ADMIN_CONTEXT, snapshot_id=snap.id, top_n=10)
print(f"\nTop regions ({len(tr.get('rows', []))}):")
for r in tr.get("rows", []):
    print(f"  {r['sub_region']}: count={r['count']}, acv=${r['acv']:,.2f}")

# 6. Comparison
comp = svc.get_comparison(ADMIN_CONTEXT, from_snapshot_id=None, to_snapshot_id=snap.id)
print("\nForecast category diffs:")
for fc in comp.get("categories", []):
    print(f"  {fc['category']}: Today={fc['to_count']} (${fc['to_acv']:,.2f}), Yest={fc['from_count']} (${fc['from_acv']:,.2f}), Diff={fc['count_diff']} (${fc['acv_diff']:,.2f})")

print("\nForecast movements count:", len(comp.get("forecast_movements", [])))
for fm in comp.get("forecast_movements", [])[:6]:
    print(f"  {fm.get('from_category')} -> {fm.get('to_category')}: {fm.get('count')}")

print("\nMovers count:", len(comp.get("biggest_movers", [])))
for bm in comp.get("biggest_movers", [])[:5]:
    print(f"  {bm.get('opportunity_name')}: old={bm.get('old_acv')}, new={bm.get('new_acv')}, tag={bm.get('tag')}")

db.close()
