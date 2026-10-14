import urllib.request
import json

try:
    req = urllib.request.urlopen("http://localhost:8000/api/analytics/history-overview")
    data = json.loads(req.read().decode())
    print("History Overview status:", req.status)
    print("History keys:", list(data.keys()))
    print("Snapshots in history:", len(data["snapshots"]))
except Exception as e:
    print("History Overview error:", e)

try:
    req2 = urllib.request.urlopen("http://localhost:8000/api/compare?from=2026-10-05&to=2026-10-06")
    data2 = json.loads(req2.read().decode())
    print("Compare status:", req2.status)
    print("Compare keys:", list(data2.keys()))
except Exception as e:
    print("Compare error:", e)
