from datetime import date
import pytest
from sqlalchemy import or_, and_, select
from backend.services.scopes import ScopeService
from backend.models.opportunity import Opportunity
from backend.config import settings
from unittest import mock

def test_quarter_of_and_bounds():
    # Assuming FISCAL_YEAR_START_MONTH = 1 (Jan)
    settings.FISCAL_YEAR_START_MONTH = 1
    
    # 2026 Q4 (Oct, Nov, Dec)
    d1 = date(2026, 10, 7)
    q1 = ScopeService.quarter_of(d1)
    assert q1 == "Q4-2026"
    assert ScopeService.quarter_label(q1) == "Q4 FY26"
    s1, e1 = ScopeService.quarter_bounds(q1)
    assert s1 == date(2026, 10, 1)
    assert e1 == date(2026, 12, 31)

    # 2027 Q1 (Jan, Feb, Mar)
    d2 = date(2027, 1, 5)
    q2 = ScopeService.quarter_of(d2)
    assert q2 == "Q1-2027"
    assert ScopeService.quarter_label(q2) == "Q1 FY27"
    s2, e2 = ScopeService.quarter_bounds(q2)
    assert s2 == date(2027, 1, 1)
    assert e2 == date(2027, 3, 31)

    # 2027 Q2 (Apr, May, Jun)
    d3 = date(2027, 4, 2)
    q3 = ScopeService.quarter_of(d3)
    assert q3 == "Q2-2027"
    assert ScopeService.quarter_label(q3) == "Q2 FY27"
    s3, e3 = ScopeService.quarter_bounds(q3)
    assert s3 == date(2027, 4, 1)
    assert e3 == date(2027, 6, 30)

def test_scope_queries(db_session):
    # Ensure current quarter slices correctly based on logical scoping
    d = date(2026, 10, 7)
    
    cq = ScopeService.current_quarter(d)
    assert cq == "Q4-2026"
    
    stmt = select(Opportunity).where(ScopeService.current_quarter_slice(ScopeService.current_quarter(d)))
    # It should compile successfully
    
    stmt_slip = select(Opportunity).where(ScopeService.slippage(ScopeService.current_quarter(d)))
    # It should compile successfully
