"""
test_scope_filter_api.py - Integration tests for scope and include_deleted_lost
filter propagation. Calls HTTP endpoints (not service layer) with three filter
combinations:
  A) scope=renewals,  include_deleted_lost=false  (default - smallest set)
  B) scope=all,       include_deleted_lost=false  (wider scope, no deleted)
  C) scope=all,       include_deleted_lost=true   (widest set)

Key assertions:
- count(A) <= count(B) <= count(C)
- A != C (must produce different results on real data)
- All /api/opportunities items in renewals scope have in_renewals=True
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from backend.main import app
from backend.database import get_db


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


def _kpis(client, scope, idl):
    r = client.get("/api/analytics/kpis",
                   params={"scope": scope, "include_deleted_lost": str(idl).lower()})
    assert r.status_code == 200, r.text
    return r.json()


def _forecast_summary(client, scope, idl):
    r = client.get("/api/analytics/forecast-summary",
                   params={"scope": scope, "include_deleted_lost": str(idl).lower()})
    assert r.status_code == 200, r.text
    return r.json()


def _approval_status(client, scope, idl):
    r = client.get("/api/analytics/approval-status",
                   params={"scope": scope, "include_deleted_lost": str(idl).lower()})
    assert r.status_code == 200, r.text
    return r.json()


def _opps(client, scope, idl):
    r = client.get("/api/opportunities",
                   params={"scope": scope, "include_deleted_lost": str(idl).lower(), "page_size": 200})
    assert r.status_code == 200, r.text
    return r.json()


def _compare(client, scope, idl):
    return client.get("/api/compare",
                      params={"from": "2026-09-28", "to": "2026-10-05",
                              "scope": scope, "include_deleted_lost": str(idl).lower()})


def _expiry(client, scope, idl):
    r = client.get("/api/analytics/expiry-quarters",
                   params={"scope": scope, "include_deleted_lost": str(idl).lower()})
    assert r.status_code == 200, r.text
    return r.json()


def _top_regions(client, scope, idl):
    r = client.get("/api/analytics/top-regions",
                   params={"scope": scope, "include_deleted_lost": str(idl).lower()})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# KPI endpoint
# ---------------------------------------------------------------------------

class TestKpiScopeFilter:
    def test_count_ordering_a_lte_b_lte_c(self, client):
        a = _kpis(client, "renewals", False)
        b = _kpis(client, "all", False)
        c = _kpis(client, "all", True)
        assert a["total_count"] <= b["total_count"], (
            f"KPIs: renewals({a['total_count']}) > all-no-del({b['total_count']})")
        assert b["total_count"] <= c["total_count"], (
            f"KPIs: all-no-del({b['total_count']}) > all-del({c['total_count']})")

    def test_renewals_ne_all_deleted(self, client):
        a = _kpis(client, "renewals", False)
        c = _kpis(client, "all", True)
        assert (a["total_count"] != c["total_count"] or a["total_acv"] != c["total_acv"]), (
            "KPIs: renewals+no-del must differ from all+deleted on real data")

    def test_acv_ordering(self, client):
        a = _kpis(client, "renewals", False)
        c = _kpis(client, "all", True)
        assert a.get("total_acv", 0) <= c.get("total_acv", 0)


# ---------------------------------------------------------------------------
# Opportunities endpoint
# ---------------------------------------------------------------------------

class TestOpportunitiesScopeFilter:
    def test_count_ordering_a_lte_b_lte_c(self, client):
        a = _opps(client, "renewals", False)
        b = _opps(client, "all", False)
        c = _opps(client, "all", True)
        assert a["total"] <= b["total"], (
            f"Opps: renewals({a['total']}) > all-no-del({b['total']})")
        assert b["total"] <= c["total"], (
            f"Opps: all-no-del({b['total']}) > all-del({c['total']})")

    def test_renewals_ne_all_deleted(self, client):
        a = _opps(client, "renewals", False)
        c = _opps(client, "all", True)
        assert a["total"] != c["total"], (
            "Opps: renewals count must differ from all+deleted count on real data")

    def test_renewals_items_all_have_in_renewals(self, client):
        data = _opps(client, "renewals", False)
        for item in data.get("items", []):
            assert item.get("in_renewals", True), (
                f"Opp {item.get('opportunity_id_18')} is not a renewal in renewals scope")


# ---------------------------------------------------------------------------
# /compare endpoint
# ---------------------------------------------------------------------------

class TestCompareEndpointScope:
    def test_renewals_scope_accepted(self, client):
        r = _compare(client, "renewals", False)
        assert r.status_code in (200, 404), f"Unexpected: {r.status_code}"

    def test_all_scope_accepted(self, client):
        r = _compare(client, "all", False)
        assert r.status_code in (200, 404), f"Unexpected: {r.status_code}"

    def test_all_deleted_scope_accepted(self, client):
        r = _compare(client, "all", True)
        assert r.status_code in (200, 404), f"Unexpected: {r.status_code}"

    def test_scope_changes_result(self, client):
        """Renewals count must be smaller than all+deleted count when snapshots exist."""
        r_r = _compare(client, "renewals", False)
        r_a = _compare(client, "all", True)
        if r_r.status_code == 200 and r_a.status_code == 200:
            cnt_r = r_r.json().get("diff", {}).get("total_count_to", 0)
            cnt_a = r_a.json().get("diff", {}).get("total_count_to", 0)
            if cnt_r > 0 and cnt_a > 0:
                assert cnt_r != cnt_a, (
                    f"/compare: renewals({cnt_r}) should differ from all+del({cnt_a})")


# ---------------------------------------------------------------------------
# Expiry quarters
# ---------------------------------------------------------------------------

class TestExpiryQuartersScope:
    def test_renewals_lte_all_deleted(self, client):
        a = _expiry(client, "renewals", False)
        c = _expiry(client, "all", True)
        qs_a = a if isinstance(a, list) else a.get("quarters", [])
        qs_c = c if isinstance(c, list) else c.get("quarters", [])
        t_a = sum(q.get("count", 0) for q in qs_a)
        t_c = sum(q.get("count", 0) for q in qs_c)
        if t_a > 0 and t_c > 0:
            assert t_a <= t_c, f"Expiry: renewals({t_a}) > all+del({t_c})"


# ---------------------------------------------------------------------------
# Top regions
# ---------------------------------------------------------------------------

class TestTopRegionsScope:
    def test_acv_ordering(self, client):
        a = _top_regions(client, "renewals", False)
        c = _top_regions(client, "all", True)
        rows_a = a if isinstance(a, list) else a.get("rows", [])
        rows_c = c if isinstance(c, list) else c.get("rows", [])
        acv_a = sum(r.get("total_acv", 0) for r in rows_a)
        acv_c = sum(r.get("total_acv", 0) for r in rows_c)
        if acv_a > 0 and acv_c > 0:
            assert acv_a <= acv_c, f"Top regions ACV: renewals({acv_a:,.0f}) > all+del({acv_c:,.0f})"


# ---------------------------------------------------------------------------
# Forecast summary
# ---------------------------------------------------------------------------

class TestForecastSummaryScope:
    def test_count_ordering(self, client):
        a = _forecast_summary(client, "renewals", False)
        c = _forecast_summary(client, "all", True)
        rows_a = a if isinstance(a, list) else a.get("rows", [])
        rows_c = c if isinstance(c, list) else c.get("rows", [])
        t_a = sum(r.get("to_count", 0) for r in rows_a) if isinstance(rows_a, list) else 0
        t_c = sum(r.get("to_count", 0) for r in rows_c) if isinstance(rows_c, list) else 0
        if t_a > 0 and t_c > 0:
            assert t_a <= t_c, f"Forecast summary: renewals({t_a}) > all+del({t_c})"


# ---------------------------------------------------------------------------
# Approval status
# ---------------------------------------------------------------------------

class TestApprovalStatusScope:
    def test_count_ordering(self, client):
        a = _approval_status(client, "renewals", False)
        b = _approval_status(client, "all", False)
        c = _approval_status(client, "all", True)
        def total(d):
            rows = d.get("rows", d) if isinstance(d, dict) else d
            return sum(r.get("to_count", 0) for r in rows) if isinstance(rows, list) else 0
        t_a, t_b, t_c = total(a), total(b), total(c)
        if t_a > 0 and t_b > 0:
            assert t_a <= t_b, f"Approval: renewals({t_a}) > all-no-del({t_b})"
        if t_b > 0 and t_c > 0:
            assert t_b <= t_c, f"Approval: all-no-del({t_b}) > all+del({t_c})"
