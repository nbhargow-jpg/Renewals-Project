"""
Normalisation helpers for raw Excel values.
All normalisation lives here so it is reused by both the ingest
and the diff services without duplication.
"""
import re
from decimal import Decimal, InvalidOperation


# ---------------------------------------------------------------------------
# Approval status normalisation
# Maps messy raw strings → canonical values used throughout the app.
# ---------------------------------------------------------------------------

APPROVAL_STATUS_MAP: dict[str, str] = {
    "approved": "Approved",
    "approved - 2nd": "Approved - 2nd",
    "approved-2nd": "Approved - 2nd",
    "approved 2nd": "Approved - 2nd",
    "pending-approval": "Pending Approval",
    "pending approval": "Pending Approval",
    "pending": "Pending Approval",
    "rejected": "Rejected",
}

CANONICAL_APPROVAL_STATUSES = [
    "Approved",
    "Approved - 2nd",
    "Pending Approval",
    "Rejected",
    "Blank",
]


def normalise_approval_status(raw: str | None) -> str:
    """
    Normalise approval status to one of the canonical values.
    None / empty → "Blank".
    """
    if raw is None or str(raw).strip() == "" or str(raw).strip().lower() == "nan":
        return "Blank"
    cleaned = str(raw).strip().lower()
    return APPROVAL_STATUS_MAP.get(cleaned, str(raw).strip())


# ---------------------------------------------------------------------------
# Forecast category normalisation
# ---------------------------------------------------------------------------

CANONICAL_FORECAST_CATEGORIES = [
    "Closed",
    "Commit",
    "Best Case",
    "Pipeline",
    "Blank",
]


def normalise_forecast_category(raw: str | None) -> str:
    if raw is None or str(raw).strip() == "" or str(raw).strip().lower() == "nan":
        return "Blank"
    return str(raw).strip()


# ---------------------------------------------------------------------------
# Business unit splitting
# ---------------------------------------------------------------------------

def split_business_units(raw: str | None) -> list[str]:
    """Split a '; '-delimited BU string into a list of individual BUs."""
    if raw is None or str(raw).strip() == "":
        return []
    return [bu.strip() for bu in re.split(r";\s*", str(raw).strip()) if bu.strip()]


def primary_business_unit(raw: str | None) -> str | None:
    """Return the first BU from the raw string."""
    parts = split_business_units(raw)
    return parts[0] if parts else None


# ---------------------------------------------------------------------------
# Currency / numeric helpers
# ---------------------------------------------------------------------------

def to_decimal(val) -> Decimal | None:
    if val is None:
        return None
    try:
        s = str(val).replace(",", "").strip()
        if s == "" or s.lower() == "nan":
            return None
        return Decimal(s)
    except InvalidOperation:
        return None


def format_acv(val: float | Decimal | None, *, show_sign: bool = False) -> str:
    """
    Format a USD ACV value like the UI expects:
      120_511_647.51 → "$120.51M"
      -5_650_000    → "-$5.65M"
      500_000       → "$500.00K"
    """
    if val is None:
        return "—"
    v = float(val)
    sign = ""
    if show_sign:
        sign = "+" if v >= 0 else ""
    abs_v = abs(v)
    if abs_v >= 1_000_000:
        formatted = f"${abs_v / 1_000_000:.2f}M"
    elif abs_v >= 1_000:
        formatted = f"${abs_v / 1_000:.2f}K"
    else:
        formatted = f"${abs_v:.2f}"
    prefix = "-" if v < 0 else sign
    return f"{prefix}{formatted}"


def format_count(val: int | None) -> str:
    """1234567 → '1,234,567'"""
    if val is None:
        return "—"
    return f"{val:,}"
