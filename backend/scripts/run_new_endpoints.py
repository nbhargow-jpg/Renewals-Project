import sys
sys.path.insert(0, '.')
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

# 1. Test /analytics/regions
res = client.get("/analytics/regions")
assert res.status_code == 200, res.text
reg_data = res.json()
print("Regions count:", len(reg_data["regions"]), "Total ACV:", reg_data["total_acv"])
assert reg_data["total_acv"] == 450040250.54, f"Total ACV {reg_data['total_acv']}"
assert reg_data["total_count"] == 3086, f"Total count {reg_data['total_count']}"

# 2. Test /analytics/history-overview
res_hist = client.get("/analytics/history-overview")
assert res_hist.status_code == 200, res_hist.text
hist_data = res_hist.json()
print("History snapshots:", len(hist_data["snapshots"]))
print("History note:", hist_data["history_note"])

# 3. Test /opportunities with filters
res_opps = client.get("/opportunities?sub_region=North America&page_size=10")
assert res_opps.status_code == 200, res_opps.text
opp_data = res_opps.json()
print("North America opps total:", opp_data["total"])
assert opp_data["total"] == 328, f"Expected 328 North America opps, got {opp_data['total']}"

# 4. Test /opportunities/export
res_export = client.get("/opportunities/export?sub_region=North America")
assert res_export.status_code == 200, res_export.text
lines = res_export.text.strip().split("\n")
print("Export lines (header + rows):", len(lines))
assert len(lines) == 329, f"Expected 329 lines (1 header + 328 rows), got {len(lines)}"

print("ALL NEW BACKEND ENDPOINTS PASSED SUCCESSFULLY!")
