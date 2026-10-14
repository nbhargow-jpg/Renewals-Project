"""
STEP 0 gate test: close_date and last_modified_date parsing.
Excel serial numbers (e.g. 46023 = 2026-01-01) must convert correctly.
Last Modified Date text like "9/15/2026" must convert correctly.
Run with:  pytest backend/tests/test_date_parsing_gate.py -v
"""
import pytest
from datetime import date, datetime
from backend.utils.excel_parser import parse_excel_date, parse_excel_datetime


class TestParseExcelDate:
    """Close Date comes as Excel serial numbers OR ISO/US text strings."""

    def test_int_serial_46023_is_2026_01_01(self):
        assert parse_excel_date(46023) == date(2026, 1, 1)

    def test_str_serial_46023_is_2026_01_01(self):
        assert parse_excel_date("46023") == date(2026, 1, 1)

    def test_float_serial_46023_is_2026_01_01(self):
        assert parse_excel_date(46023.0) == date(2026, 1, 1)

    def test_str_float_serial_46023_is_2026_01_01(self):
        assert parse_excel_date("46023.0") == date(2026, 1, 1)

    def test_int_serial_46378_is_2026_12_22(self):
        assert parse_excel_date(46378) == date(2026, 12, 22)

    def test_str_serial_46378_is_2026_12_22(self):
        assert parse_excel_date("46378") == date(2026, 12, 22)

    def test_serial_46243_is_2026_08_09(self):
        assert parse_excel_date(46243) == date(2026, 8, 9)

    def test_us_date_6_30_2026(self):
        assert parse_excel_date("6/30/2026") == date(2026, 6, 30)

    def test_us_date_9_15_2026(self):
        assert parse_excel_date("9/15/2026") == date(2026, 9, 15)

    def test_iso_date(self):
        assert parse_excel_date("2026-10-07") == date(2026, 10, 7)

    def test_iso_datetime_text(self):
        assert parse_excel_date("2026-06-02 00:00:00") == date(2026, 6, 2)

    def test_none_returns_none(self):
        assert parse_excel_date(None) is None

    def test_zero_int_returns_none(self):
        assert parse_excel_date(0) is None

    def test_zero_str_returns_none(self):
        assert parse_excel_date("0") is None

    def test_zero_float_str_returns_none(self):
        assert parse_excel_date("0.0") is None

    def test_nan_str_returns_none(self):
        assert parse_excel_date("nan") is None

    def test_empty_str_returns_none(self):
        assert parse_excel_date("") is None

    def test_nat_str_returns_none(self):
        assert parse_excel_date("NaT") is None

    def test_serial_below_range_returns_none(self):
        assert parse_excel_date(100) is None

    def test_serial_above_range_returns_none(self):
        assert parse_excel_date(99999) is None

    @pytest.mark.parametrize("serial,expected", [
        (46023, date(2026, 1, 1)),
        (46100, date(2026, 3, 19)),
        (46200, date(2026, 6, 27)),
        (46300, date(2026, 10, 5)),
        (46383, date(2026, 12, 27)),
    ])
    def test_serial_roundtrip(self, serial, expected):
        assert parse_excel_date(serial) == expected


class TestParseExcelDatetime:
    """Last Modified Date comes as US text like '9/15/2026' or ISO."""

    def test_us_date_text(self):
        r = parse_excel_datetime("9/15/2026")
        assert r is not None and r.date() == date(2026, 9, 15)

    def test_us_datetime_text(self):
        r = parse_excel_datetime("9/15/2026 14:30:00")
        assert r is not None
        assert r.date() == date(2026, 9, 15)
        assert r.hour == 14 and r.minute == 30

    def test_serial_to_datetime(self):
        r = parse_excel_datetime(46243)
        assert r is not None and r.date() == date(2026, 8, 9)

    def test_none_returns_none(self):
        assert parse_excel_datetime(None) is None

    def test_zero_returns_none(self):
        assert parse_excel_datetime(0) is None

    def test_nan_returns_none(self):
        assert parse_excel_datetime("nan") is None
