import pytest
import os
from fastapi.testclient import TestClient

def test_executive_view_contracts_sqlite():
    """
    Test Prompt C requirements:
    - Headline numbers must equal Overview endpoint for Oct 7:
        348 deals / $40,068,990.09
        Commit: 308 / $30,349,636.71
        Best Case: 34 / $9,456,843.36
        Pipeline: 1 / $49,737.62
        Not yet proposed (Blank): 5 / $212,772.40
        Delayed total: 9 / $339,305.70
    - Risk block counts equal the Delayed endpoint:
        Overdue: 6 deals / $228,071.49
        Slipped to next year: 2 deals / $59,514.21
        Lost / Removed: 0 deals / $0.00
        Not yet proposed: 5 deals / $212,772.40
    """
    from backend.main import app
    from backend.database import get_db, SessionLocal

    with TestClient(app) as client:
        # 1. Overview summary check
        r_ov = client.get("/api/v2/overview/summary")
        assert r_ov.status_code == 200, r_ov.text
        ov_data = r_ov.json()

        total = ov_data.get("total", {})
        assert total.get("count") == 348
        assert abs(total.get("acv") - 40068990.09) < 0.1

        cats = ov_data.get("categories", {})
        assert cats["Commit"]["count"] == 308
        assert abs(cats["Commit"]["acv"] - 30349636.71) < 0.1

        assert cats["Best Case"]["count"] == 34
        assert abs(cats["Best Case"]["acv"] - 9456843.36) < 0.1

        assert cats["Pipeline"]["count"] == 1
        assert abs(cats["Pipeline"]["acv"] - 49737.62) < 0.1

        assert cats["Blank"]["count"] == 5
        assert abs(cats["Blank"]["acv"] - 212772.40) < 0.1

        # 2. Delayed summary check
        r_del = client.get("/api/v2/delayed/summary?compare=yesterday")
        assert r_del.status_code == 200, r_del.text
        del_data = r_del.json()

        del_total = del_data.get("total", {})
        assert del_total.get("count") == 9
        assert abs(del_total.get("acv") - 339305.70) < 0.1

        # 3. Risk block components matching Delayed endpoint & Overview Blank
        overdue = del_data.get("overdue", {})
        assert overdue.get("count") == 6
        assert abs(overdue.get("acv") - 228071.49) < 0.1

        slipped = del_data.get("slipped", {})
        assert slipped.get("count") == 2
        assert abs(slipped.get("acv") - 59514.21) < 0.1

        lost = del_data.get("lost", {})
        assert lost.get("count") == 0
        assert abs(lost.get("acv") - 0.0) < 0.1

        blank = cats["Blank"]
        assert blank.get("count") == 5
        assert abs(blank.get("acv") - 212772.40) < 0.1
