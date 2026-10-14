"""
Excel parser — reads raw sheets from workbooks into pandas DataFrames.
Column mapping and slot detection defined here.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pandas as pd
from datetime import date, datetime, timedelta


# ---------------------------------------------------------------------------
# Column name → canonical attribute name mapping
# ---------------------------------------------------------------------------
RENEWALS_COLUMN_MAP: dict[str, str] = {
    "opportunity id 18 digit": "opportunity_id_18",
    "opportunity name":         "opportunity_name",
    "account name":             "account_name",
    "sub-region":               "sub_region",
    "revised sub-region":       "revised_sub_region",
    "country: territory name":  "country_territory",
    "country / territory":      "country_territory",
    "business unit":            "business_unit_raw",
    "forecast category":        "forecast_category",
    "forecast acv amount":      "forecast_acv_amount",
    "close date":               "close_date",
    "last modified date":       "last_modified_date",
    "probability (%)":          "probability_pct",
    "opportunity approval status": "approval_status",
    "approval status":          "approval_status",
    "service expiry period":    "service_expiry_period",
    "closing year":             "closing_year",
    "fiscal period":            "fiscal_period",
    "renewal category":         "renewal_category",
    "months delayed (working)": "months_delayed",
    "months\ndelayed (working)": "months_delayed",
    "opportunity owner":        "opportunity_owner",
    "sales type":               "sales_type",
    "stage number":             "stage_number",
    "stage":                    "stage_number",
}

RAW_DATA_SHEETS = ["Today_Data", "Yesterday_Data", "Lastweek_Data"]

COMPARISON_SHEETS = [
    "FinalChangeReport", "ACVChanges", "TodayForecastSummary",
    "YesterdayForecastSummary", "ForecastMovementSummary", "OpportunityStatus",
    "ApprovalStatusChanges", "ServiceExpiryChanges", "RenewalCategoryChanges",
    "RegionChanges", "ForecastChanges", "comparison", "today", "yesterday",
]

# ---------------------------------------------------------------------------
# Robust value parsing
# ---------------------------------------------------------------------------
_EXCEL_EPOCH = datetime(1899, 12, 30)


def parse_excel_datetime(val) -> datetime | None:
    """Convert any date-like cell value to datetime, or None.
    Handles Timestamp/datetime/date, Excel serial numbers, ISO and US text.
    Zero/blank/"nan" are treated as missing."""
    if val is None:
        return None
    if isinstance(val, pd.Timestamp):
        return None if pd.isna(val) else val.to_pydatetime()
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day)
    if isinstance(val, float) and pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "nat", "none", "0", "0.0"):
        return None
    # Excel serial number (plausible range 1950-2100)
    if re.fullmatch(r"\d{4,6}(\.\d+)?", s):
        n = float(s)
        if 18000 <= n <= 73415:
            return _EXCEL_EPOCH + timedelta(days=n)
        return None
    try:
        ts = pd.to_datetime(s, errors="coerce")
        return None if pd.isna(ts) else ts.to_pydatetime()
    except Exception:
        return None


def parse_excel_date(val) -> date | None:
    dt = parse_excel_datetime(val)
    return dt.date() if dt else None


def clean_record(rec: dict) -> dict:
    """Make a row dict JSON-safe: NaN/NaT -> None, Timestamps -> ISO strings."""
    out = {}
    for k, v in rec.items():
        if v is None or (isinstance(v, float) and pd.isna(v)):
            out[str(k)] = None
        elif isinstance(v, (pd.Timestamp, datetime, date)):
            out[str(k)] = v.isoformat()
        else:
            out[str(k)] = v
    return out


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _normalise_col(col: str) -> str:
    return re.sub(r"\s+", " ", str(col).replace("\u00a0", " ").strip().lower())


def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        normed = _normalise_col(col)
        if normed in RENEWALS_COLUMN_MAP:
            rename[col] = RENEWALS_COLUMN_MAP[normed]
    return df.rename(columns=rename)


def _open(path: Path) -> pd.ExcelFile:
    """Open a workbook ONCE; callers reuse the handle for every sheet they need."""
    try:
        return pd.ExcelFile(path)
    except Exception as exc:
        raise ValueError(f"Cannot open {Path(path).name}: {exc}") from exc


def _read_sheet(xf: pd.ExcelFile, sheet_name: str, **kwargs) -> pd.DataFrame:
    """Read one sheet from an already-open workbook as text."""
    try:
        return xf.parse(sheet_name, dtype=str, **kwargs)
    except Exception as exc:
        raise ValueError(f"Cannot read sheet '{sheet_name}': {exc}") from exc


def available_sheets(path: Path) -> list[str]:
    return _open(path).sheet_names


REAL_SLOT_NAMES: dict[str, str] = {
    "comparison_tool": "Renewal Comparison Tool",
}


def detect_file_slot(path: Path, xf: pd.ExcelFile | None = None) -> tuple[str, str]:
    """
    Detect slot by CONTENT and sheet signature dynamically (Addendum C: lifetime-proof).
    - If today & yesterday sheets are present: Renewal Comparison Tool ('comparison_tool')
    - If today_data sheet is present: Renewals Summary file.
      Reads Fiscal Period and Closing Year from Today_Data to derive a generic slot id:
      renewals_summary:<covered_period>
      and a human-readable title built from the data:
      e.g. "Renewals Summary - FY2026" or "Renewals Summary - Q4 FY26"
    """
    try:
        xf = xf or _open(path)
        sheet_names = xf.sheet_names
        sheet_names_lower = {s.lower(): s for s in sheet_names}
    except Exception as exc:
        return "unknown", f"Cannot open Excel file: {exc}"

    if "today" in sheet_names_lower and "yesterday" in sheet_names_lower:
        return "comparison_tool", "Renewal Comparison Tool (Today & Yesterday)"

    today_data_sheet = sheet_names_lower.get("today_data")
    if today_data_sheet:
        try:
            header = xf.parse(today_data_sheet, nrows=0, dtype=str)
            fp_col = next((c for c in header.columns if "fiscal period" in _normalise_col(c)), None)
            cy_col = next((c for c in header.columns if "closing year" in _normalise_col(c)), None)
            cols_to_read = [c for c in (fp_col, cy_col) if c]
            if cols_to_read:
                df_full = xf.parse(today_data_sheet, usecols=cols_to_read, dtype=str)
                fp_vals = (
                    sorted([str(x).strip() for x in df_full[fp_col].dropna().unique() if str(x).strip()])
                    if fp_col else []
                )
                cy_vals = (
                    sorted([str(x).replace(".0", "").strip() for x in df_full[cy_col].dropna().unique() if str(x).strip()])
                    if cy_col else []
                )

                # 1. Single fiscal period (e.g. Q4-2026, Q2-2027)
                if len(fp_vals) == 1 and re.match(r"Q[1-4]-\d{4}", fp_vals[0], re.IGNORECASE):
                    q_name = fp_vals[0].upper()
                    m = re.match(r"Q([1-4])-(\d{4})", q_name)
                    if m:
                        title = f"Renewals Summary - Q{m.group(1)} FY{m.group(2)[-2:]}"
                    else:
                        title = f"Renewals Summary - {q_name}"
                    return f"renewals_summary:{q_name}", title

                # 2. Single closing year / fiscal year (e.g. 2027)
                if len(cy_vals) == 1 and re.match(r"^\d{4}$", cy_vals[0]):
                    yr = cy_vals[0]
                    return f"renewals_summary:FY{yr}", f"Renewals Summary - FY{yr}"

                # 3. Dominant closing year (e.g. FY2026 where >=80% of rows are 2026)
                if cy_col:
                    cy_series = df_full[cy_col].dropna().astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
                    if not cy_series.empty:
                        vc = cy_series.value_counts()
                        top_yr = str(vc.index[0])
                        top_ratio = vc.iloc[0] / len(cy_series)
                        if top_ratio >= 0.8 and re.match(r"^\d{4}$", top_yr):
                            return f"renewals_summary:FY{top_yr}", f"Renewals Summary - FY{top_yr}"

                # 4. Multi-period / multi-year fallback
                if fp_vals:
                    summary_scope = ",".join(fp_vals[:3])
                    return f"renewals_summary:{summary_scope}", f"Renewals Summary - {summary_scope}"
                elif cy_vals:
                    summary_scope = f"FY{min(cy_vals)}-FY{max(cy_vals)}"
                    return f"renewals_summary:{summary_scope}", f"Renewals Summary - {summary_scope}"

            return "renewals_summary:all", "Renewals Summary - All"
        except Exception as exc:
            return "renewals_summary:default", f"Renewals Summary ({exc})"

    return "unknown", f"Unrecognized sheet structure: {sheet_names[:5]}"


def detect_suggested_snapshot_date(path: Path, xf: pd.ExcelFile | None = None) -> date | None:
    """Inspect filename or sheets for date suggestion."""
    # 1. Regex on filename
    fn = path.name
    m = re.search(r"(\d{4})[-_](\d{2})[-_](\d{2})", fn)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # 2. Check today sheet Last Modified Date max
    try:
        xf = xf or _open(path)
        lookup = {s.lower(): s for s in xf.sheet_names}
        today_sheet = lookup.get("today")
        if today_sheet:
            header = xf.parse(today_sheet, nrows=0, dtype=str)
            lmd_col = next((c for c in header.columns if "last modified date" in _normalise_col(c)), None)
            if lmd_col:
                df = xf.parse(today_sheet, usecols=[lmd_col], dtype=str)
                s = pd.to_datetime(df[lmd_col], errors="coerce").dropna()
                if not s.empty:
                    return s.max().date()
    except Exception:
        pass

    return None


COMPARISON_NEEDED = [
    "today",
    "yesterday",
    "finalchangereport",
    "todayforecastsummary",
    "yesterdayforecastsummary",
    "forecastmovementsummary",
    "forecastchanges",
    "approvalstatuschanges",
]
SUMMARY_NEEDED = [
    "today_data",
    "yesterday_data",
    "lastweek_data",
    "approvalstatus_summary",
    "today_expiry",
    "expiry_final",
    "approvalstatus_bu_acv",
    "top 10 region summary",
]


def parse_comparison_tool(path: Path, xf: pd.ExcelFile | None = None) -> dict[str, pd.DataFrame]:
    """Read needed sheets of Comparison Tool workbook (one open, no re-parsing)."""
    xf = xf or _open(path)
    lookup = {s.lower(): s for s in xf.sheet_names}
    result: dict[str, pd.DataFrame] = {}
    for key in COMPARISON_NEEDED:
        real = lookup.get(key)
        if real is None:
            continue
        try:
            df = _read_sheet(xf, real).dropna(how="all")
        except ValueError:
            df = pd.DataFrame()
        result[key] = df
        result[real] = df
    return result


def parse_summary_workbook(path: Path, xf: pd.ExcelFile | None = None) -> dict[str, pd.DataFrame]:
    """Read raw data sheets and ApprovalStatus_Summary."""
    xf = xf or _open(path)
    lookup = {s.lower(): s for s in xf.sheet_names}
    result: dict[str, pd.DataFrame] = {}
    for key in SUMMARY_NEEDED:
        real = lookup.get(key)
        if real is None:
            continue
        try:
            df = _read_sheet(xf, real).dropna(how="all")
        except ValueError:
            df = pd.DataFrame()
        result[key] = df
        result[real] = df
    return result


# Legacy alias
parse_renewals_summary = parse_summary_workbook
