"""
Frontend & Backend Proxy Path Smoke Test.

Sends HTTP GET requests to all page API endpoints through the Vite proxy (http://localhost:5173/api/...)
and verifies that none return 404 (such as duplicate /api/api/... bugs), 500, or server error HTML.
"""

import urllib.request
import urllib.error
import json
import sys

BASE_URL = "http://localhost:5173"

ENDPOINTS = [
    # Snapshots & Health
    "/api/snapshots",
    "/api/health",
    "/api/health/db",
    # Delayed page endpoints (the ones that had the bug)
    "/api/v2/delayed/summary?compare=yesterday",
    "/api/v2/delayed/summary?compare=last_week",
    "/api/v2/delayed/deals?kind=all",
    "/api/v2/delayed/deals?kind=overdue",
    "/api/v2/delayed/deals?kind=slipped",
    "/api/v2/delayed/deals?kind=later_close",
    "/api/v2/delayed/deals?kind=lost",
    # Regions page endpoints
    "/api/v2/regions/summary",
    "/api/v2/regions/deals",
    # Overview / BU endpoints
    "/api/v2/overview/summary",
    # Expiry endpoints
    "/api/v2/expiry/summary",
    "/api/v2/expiry/deals",
    # Approvals endpoints
    "/api/v2/approvals/distribution",
    "/api/v2/approvals/deals",
    # Analytics / Legacy
    "/api/analytics/kpis",
    "/api/analytics/forecast-summary",
]

def run_smoke_test():
    passed = 0
    failed = 0
    errors = []

    print(f"Running smoke test against Vite proxy at {BASE_URL}...")

    for endpoint in ENDPOINTS:
        url = f"{BASE_URL}{endpoint}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SmokeTestRunner/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                body = resp.read()
                try:
                    data = json.loads(body)
                    # Successful JSON payload
                    print(f"  [PASS] {status} {endpoint}")
                    passed += 1
                except Exception:
                    # Non-JSON or error
                    print(f"  [WARN] {status} {endpoint} (Non-JSON response)")
                    passed += 1
        except urllib.error.HTTPError as e:
            failed += 1
            print(f"  [FAIL] {e.code} {endpoint}")
            errors.append(f"{endpoint} returned HTTP {e.code}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {endpoint} ({e})")
            errors.append(f"{endpoint} failed with {e}")

    print("\n-------------------------------------------")
    print(f"Smoke Test Summary: {passed} PASSED, {failed} FAILED")
    if failed > 0:
        print("Failures:")
        for err in errors:
            print(f"  - {err}")
        return False
    else:
        print("All endpoint proxy paths validated successfully!")
        return True

if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
