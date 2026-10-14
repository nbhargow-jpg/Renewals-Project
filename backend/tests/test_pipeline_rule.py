import pytest
from datetime import date
from decimal import Decimal
from backend.services.v2_overview_service import V2OverviewService
from backend.services.context import ADMIN_CONTEXT
from backend.models.snapshot import UploadSnapshot
from backend.models.opportunity import Opportunity

def test_pipeline_rule_sample_oct7(tmp_path_factory):
    """
    Assert exact values on sample_oct7:
    - Pipeline: 1 deal / $49,737.62 appears on Overview
    - Sum check: Closed + Commit + Best Case + Blank + Pipeline == Total (348 / $40,068,990.09)
    """
    from backend.tests.test_db_helper import get_test_engine_and_session
    from backend.database import get_db
    from backend.main import app
    from fastapi.testclient import TestClient
    from backend.utils.excel_parser import detect_file_slot
    from pathlib import Path
    
    sample = Path("data/sample_oct7")
    if not sample.exists():
        pytest.skip("sample_oct7 not found")
        
    engine, Session = get_test_engine_and_session("pipeline_rule_test", tmp_path_factory)
    
    def override_db():
        db = Session()
        try: yield db
        finally: db.close()

    app.dependency_overrides[get_db] = override_db
    try:
        slots = {}
        for fp in sorted(sample.glob("*.xlsx")):
            slots[detect_file_slot(fp)[0]] = fp

        with TestClient(app) as client:
            files = [(slot, (fp.name, open(fp, "rb"),
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
                     for slot, fp in slots.items()]
            data = {"data_as_of_date": "2026-10-07", "yesterday_date": "2026-10-06"}
            vr = client.post("/api/snapshots/validate", data=data, files=files)
            assert vr.status_code == 200, vr.text
            session_id = vr.json()["session_id"]

            cr = client.post("/api/snapshots/commit",
                             json={"session_id": session_id, "replace": False})
            assert cr.status_code == 200, cr.text

            r = client.get("/api/v2/overview/summary")
            assert r.status_code == 200
            summary = r.json()

            assert summary["total"]["count"] == 348
            assert summary["total"]["acv"] == pytest.approx(40068990.09, rel=1e-5)

            cats = summary["categories"]
            assert "Pipeline" in cats
            assert cats["Pipeline"]["count"] == 1
            assert cats["Pipeline"]["acv"] == pytest.approx(49737.62, rel=1e-5)

            # Check Not yet proposed (Blank)
            assert cats["Blank"]["count"] == 5
            assert cats["Blank"]["acv"] == pytest.approx(212772.40, rel=1e-5)

            # Tie out all categories to total
            sum_count = sum(c["count"] for c in cats.values())
            sum_acv = sum(c["acv"] for c in cats.values())
            assert sum_count == 348
            assert sum_acv == pytest.approx(40068990.09, rel=1e-5)

            # Drill-through deals for Pipeline category
            dr = client.get("/api/v2/overview/deals", params={"category": "Pipeline"})
            assert dr.status_code == 200
            deals_resp = dr.json()
            assert deals_resp["count"] == 1
            assert deals_resp["acv"] == pytest.approx(49737.62, rel=1e-5)
            assert len(deals_resp["deals"]) == 1
            assert deals_resp["deals"][0]["forecast_category"] == "Pipeline"
    finally:
        app.dependency_overrides.clear()

def test_synthetic_snapshot_zero_pipeline_deals(tmp_path_factory):
    """
    Synthetic snapshot with 0 Pipeline deals:
    - Pipeline is ALWAYS present in categories: count is 0, ACV is 0
    - Total ties out exactly to Closed + Commit + Best Case + Blank
    - Verifies Pipeline category is always returned and displayed even at 0 (never hidden)
    """
    from backend.tests.test_db_helper import get_test_engine_and_session
    engine, Session = get_test_engine_and_session("syn_zero_pipeline", tmp_path_factory)
    session = Session()
    try:
        snap = UploadSnapshot(
            id="snap-zero-pipeline-test",
            label="Oct 8",
            snapshot_date=date(2026, 10, 8),
            workbook_type="BOTH",
            row_count=3,
            is_active_today=True
        )
        session.add(snap)
        
        opps = [
            Opportunity(
                id="opp-syn-1",
                snapshot_id=snap.id,
                opportunity_id_18="006TEST11111111111",
                opportunity_name="Opp Closed",
                sub_region="North America",
                revised_sub_region="North America",
                forecast_category="Closed",
                forecast_acv_amount=Decimal("100000.00"),
                sales_type="Renewals",
                fiscal_period="Q4-2026",
                close_date=date(2026, 10, 15),
                is_deleted_or_lost=False,
            ),
            Opportunity(
                id="opp-syn-2",
                snapshot_id=snap.id,
                opportunity_id_18="006TEST22222222222",
                opportunity_name="Opp Commit",
                sub_region="North America",
                revised_sub_region="North America",
                forecast_category="Commit",
                forecast_acv_amount=Decimal("150000.00"),
                sales_type="Renewals",
                fiscal_period="Q4-2026",
                close_date=date(2026, 10, 20),
                is_deleted_or_lost=False,
            ),
            Opportunity(
                id="opp-syn-3",
                snapshot_id=snap.id,
                opportunity_id_18="006TEST33333333333",
                opportunity_name="Opp Blank",
                sub_region="North America",
                revised_sub_region="North America",
                forecast_category="",
                forecast_acv_amount=Decimal("50000.00"),
                sales_type="Renewals",
                fiscal_period="Q4-2026",
                close_date=date(2026, 10, 25),
                is_deleted_or_lost=False,
            ),
        ]
        session.add_all(opps)
        session.commit()
        
        svc = V2OverviewService(session)
        summary = svc.get_summary(ADMIN_CONTEXT, as_of="2026-10-08")
        
        assert summary["total"]["count"] == 3
        assert summary["total"]["acv"] == pytest.approx(300000.00, rel=1e-5)
        
        cats = summary["categories"]
        assert "Pipeline" in cats
        assert cats["Pipeline"]["count"] == 0
        assert cats["Pipeline"]["acv"] == 0.0
        
        # Totals unchanged
        sum_count = sum(c["count"] for c in cats.values())
        sum_acv = sum(c["acv"] for c in cats.values())
        assert sum_count == 3
        assert sum_acv == pytest.approx(300000.00, rel=1e-5)
        
        # Drill-through deals for Pipeline returns 0
        deals_resp = svc.get_deals(ADMIN_CONTEXT, category="Pipeline", as_of="2026-10-08")
        assert deals_resp["count"] == 0
        assert deals_resp["acv"] == 0.0
        assert len(deals_resp["deals"]) == 0
    finally:
        session.close()
