"""
test_api_endpoints.py — verifies FastAPI HTTP endpoints:
  - GET /snapshots
  - GET /compare?from=DATE&to=DATE
  - GET /opportunities/{id}/history
  - GET /api/health
  - GET /api/analytics/kpis
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import get_db
from backend.models.opportunity import Opportunity


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


def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_get_snapshots(client):
    # Both /snapshots and /api/snapshots should work
    res = client.get("/snapshots")
    assert res.status_code == 200
    snaps = res.json()
    assert isinstance(snaps, list)
    assert len(snaps) >= 1

    res_api = client.get("/api/snapshots")
    assert res_api.status_code == 200
    assert len(res_api.json()) == len(snaps)


def test_get_compare_endpoint(client):
    # Test unified comparison route with ?from=DATE&to=DATE
    res = client.get("/compare?from=2026-10-02&to=2026-10-05")
    assert res.status_code == 200
    data = res.json()

    assert "from_snapshot" in data
    assert "to_snapshot" in data
    assert "diff" in data
    assert "expiry_pivot" in data
    assert "forecast_category" in data
    assert "approval_status" in data
    assert "region" in data
    assert "business_unit" in data
    assert "movement" in data


def test_get_compare_via_api_prefix(client):
    res = client.get("/api/compare?from=2026-10-02&to=2026-10-05")
    assert res.status_code == 200
    data = res.json()
    assert "diff" in data


def test_opportunity_history_endpoint(client, seeded_session):
    opp = seeded_session.query(Opportunity).first()
    assert opp is not None

    res = client.get(f"/api/opportunities/{opp.opportunity_id_18}/history")
    assert res.status_code == 200
    history = res.json()
    assert isinstance(history, list)
    assert len(history) >= 1
    assert history[0]["opportunity_id_18"] == opp.opportunity_id_18


def test_kpis_endpoint(client):
    res = client.get("/api/analytics/kpis")
    assert res.status_code == 200
    kpis = res.json()
    assert "total_acv" in kpis
    assert "total_count" in kpis
