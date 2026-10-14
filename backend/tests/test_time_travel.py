import pytest
from datetime import date
from backend.services.scopes import ScopeService

def test_time_travel_scopes():
    # 2026-10-07 -> Q4-2026
    d_oct = date(2026, 10, 7)
    assert ScopeService.current_quarter(d_oct) == "Q4-2026"
    
    # 2027-01-05 -> Q1-2027
    d_jan = date(2027, 1, 5)
    assert ScopeService.current_quarter(d_jan) == "Q1-2027"
    
    # 2027-04-02 -> Q2-2027
    d_apr = date(2027, 4, 2)
    assert ScopeService.current_quarter(d_apr) == "Q2-2027"
    
    # Check slippage bounds logic
    s_oct, e_oct = ScopeService.quarter_bounds(ScopeService.current_quarter(d_oct))
    assert s_oct == date(2026, 10, 1)
    assert e_oct == date(2026, 12, 31)
    
    s_jan, e_jan = ScopeService.quarter_bounds(ScopeService.current_quarter(d_jan))
    assert s_jan == date(2027, 1, 1)
    assert e_jan == date(2027, 3, 31)
    
    s_apr, e_apr = ScopeService.quarter_bounds(ScopeService.current_quarter(d_apr))
    assert s_apr == date(2027, 4, 1)
    assert e_apr == date(2027, 6, 30)

    # Note: if FISCAL_YEAR_START_MONTH changes, these assertions would fail,
    # ensuring the logical slice behaves consistently as intended.
