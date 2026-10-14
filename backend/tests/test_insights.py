"""
test_insights.py — tests Deal Risk Scoring and Insights page endpoints:
- Score is in range 0-100.
- Factors sum exactly to the score.
- Known high-risk open deal ranks above a Closed deal (Closed deal is 0).
- /api/insights returns top 15 at-risk deals, renewals at risk, commit slippage, history card, and model card.
"""
import pytest
from datetime import date
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import get_db
from backend.models.opportunity import Opportunity
from backend.models.snapshot import UploadSnapshot
from backend.services.risk_service import RiskService
from backend.services.context import ADMIN_CONTEXT


from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client(seeded_session, db_engine):
    Session = sessionmaker(bind=db_engine)

    def _override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_deal_risk_score_bounds_and_factor_sum(seeded_session):
    svc = RiskService(seeded_session)
    opps = seeded_session.query(Opportunity).limit(50).all()
    assert len(opps) > 0

    for o in opps:
        res = svc.compute_deal_risk(o, as_of_date=date(2026, 10, 6))
        score = res["score"]
        factors = res["factors"]

        # Score is within 0-100
        assert 0 <= score <= 100, f"Score {score} not in [0, 100] for {o.opportunity_id_18}"

        # Factors sum exactly to the score
        factor_sum = sum(f["points"] for f in factors)
        assert factor_sum == score, f"Factor sum {factor_sum} != score {score} for {o.opportunity_id_18}"

        # Level matches score
        if score >= 65:
            assert res["level"] == "high"
        elif score >= 35:
            assert res["level"] == "medium"
        else:
            assert res["level"] == "low"


def test_high_risk_ranks_above_closed_deal(seeded_session):
    svc = RiskService(seeded_session)

    # 1. Closed deal
    closed_opp = Opportunity(
        opportunity_id_18="006CLOSEDTEST1111",
        opportunity_name="Closed Deal Test",
        forecast_category="Closed",
        forecast_acv_amount=500000,
        probability_pct=1.0,
        approval_status="Approved",
    )
    closed_res = svc.compute_deal_risk(closed_opp, as_of_date=date(2026, 10, 6))
    assert closed_res["score"] == 0

    # 2. Known high-risk open deal: low prob, delayed, unapproved, past close date
    high_risk_opp = Opportunity(
        opportunity_id_18="006RISKYTEST2222",
        opportunity_name="High Risk Deal Test",
        forecast_category="Pipeline",
        forecast_acv_amount=1500000,
        probability_pct=0.1,
        months_delayed=8.5,
        approval_status="Blank",
        close_date=date(2026, 8, 1),
    )
    risky_res = svc.compute_deal_risk(high_risk_opp, as_of_date=date(2026, 10, 6))
    assert risky_res["score"] >= 65
    assert risky_res["score"] > closed_res["score"]
    assert risky_res["level"] == "high"


def test_insights_endpoint(client, seeded_session):
    snap = seeded_session.query(UploadSnapshot).filter_by(is_active_today=True).first()
    assert snap is not None

    res = client.get(f"/api/insights?snapshot_id={snap.id}")
    assert res.status_code == 200
    data = res.json()

    # Verify top 15 at-risk deals
    assert "top_at_risk" in data
    assert len(data["top_at_risk"]) <= 15
    for deal in data["top_at_risk"]:
        assert 0 <= deal["risk_score"] <= 100
        assert len(deal["risk_factors"]) > 0
        assert deal["forecast_category"].lower() != "closed"

    # Verify renewals at risk
    assert "renewals_at_risk" in data
    assert isinstance(data["renewals_at_risk"], list)

    # Verify commit slippage
    assert "commit_slippage" in data
    assert isinstance(data["commit_slippage"], list)

    # Verify history card status
    assert "history_status" in data
    hs = data["history_status"]
    assert "available_snapshots" in hs
    assert hs["target_snapshots"] == 7
    assert "Collecting history" in hs["message"]

    # Verify model card
    assert "model_card" in data
    mc = data["model_card"]
    assert "Deterministic Deal Risk Scoring Model" in mc["title"]
    assert len(mc["scoring_breakdown"]) == 6
    assert len(mc["limitations"]) > 0


def test_opportunity_detail_includes_risk(client, seeded_session):
    opp = seeded_session.query(Opportunity).first()
    assert opp is not None

    res = client.get(f"/api/opportunities/{opp.opportunity_id_18}")
    assert res.status_code == 200
    data = res.json()
    assert "risk_score" in data
    assert "risk_factors" in data
    assert "risk_level" in data
    assert 0 <= data["risk_score"] <= 100


def test_date_handling_relative_to_snapshot_date(seeded_session):
    svc = RiskService(seeded_session)

    # Opportunity with close date July 15, 2026 and last modified July 1, 2026
    opp = Opportunity(
        opportunity_id_18="006DATERELATIVE1",
        opportunity_name="Date Relative Test",
        forecast_category="Pipeline",
        forecast_acv_amount=200000,
        probability_pct=0.8,
        months_delayed=0,
        approval_status="Approved",
        close_date=date(2026, 7, 15),
        last_modified_date=date(2026, 7, 1),
    )

    # As of snapshot June 1, 2026:
    # Close date (July 15) is safely in the future (>30 days away) -> 0 pts
    # Last modified (July 1) is recent / future -> 0 pts
    res_june = svc.compute_deal_risk(opp, as_of_date=date(2026, 6, 1))
    c_factor_june = next(f for f in res_june["factors"] if f["name"] == "Close Date Proximity")
    s_factor_june = next(f for f in res_june["factors"] if f["name"] == "Activity & Staleness")
    assert c_factor_june["points"] == 0
    assert s_factor_june["points"] == 0

    # As of snapshot October 6, 2026:
    # Close date (July 15) has passed before snapshot -> 15 pts
    # Last modified (July 1) is 97 days before snapshot (>60 days) -> 10 pts
    res_oct = svc.compute_deal_risk(opp, as_of_date=date(2026, 10, 6))
    c_factor_oct = next(f for f in res_oct["factors"] if f["name"] == "Close Date Proximity")
    s_factor_oct = next(f for f in res_oct["factors"] if f["name"] == "Activity & Staleness")
    assert c_factor_oct["points"] == 15
    assert s_factor_oct["points"] == 10
    assert res_oct["score"] > res_june["score"]


def test_renewals_at_risk_quarters_derived_from_snapshot_date(client, seeded_session):
    # 1. Existing seeded snapshot (Oct 5, 2026: Month 10 -> Q4-2026 and Q1-2027)
    snap_oct = seeded_session.query(UploadSnapshot).filter_by(is_active_today=True).first()
    assert snap_oct is not None
    res_oct = client.get(f"/api/insights?snapshot_id={snap_oct.id}")
    assert res_oct.status_code == 200
    data_oct = res_oct.json()
    assert data_oct["target_quarters"] == ["Q4-2026", "Q1-2027"]

    # 2. Snapshot in Q1 (e.g. Feb 15, 2026: Month 2 -> Q1-2026 and Q2-2026)
    snap_q1 = UploadSnapshot(
        snapshot_date=date(2026, 2, 15),
        label="Q1 Test Snapshot",
        is_active_today=False,
    )
    seeded_session.add(snap_q1)
    seeded_session.commit()

    res_q1 = client.get(f"/api/insights?snapshot_id={snap_q1.id}")
    assert res_q1.status_code == 200
    data_q1 = res_q1.json()
    assert data_q1["target_quarters"] == ["Q1-2026", "Q2-2026"]


