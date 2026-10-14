"""
DiffService — computes field-level diffs between two snapshots and stores
them in change_logs and forecast_movement_log.

Can be fed either from the Comparison Tool workbook (faster path when
the user uploads both files) or computed from scratch by comparing
two snapshot's Opportunity rows (fallback path).
"""
from __future__ import annotations

import logging
import re
from decimal import Decimal

import pandas as pd
from sqlalchemy.orm import Session

from backend.models.change_log import ChangeLog, ForecastMovementLog
from backend.models.snapshot import UploadSnapshot
from backend.models.opportunity import Opportunity
from backend.services.context import UserContext
from backend.utils.normalise import (
    normalise_approval_status,
    normalise_forecast_category,
    to_decimal,
)

log = logging.getLogger(__name__)


def _safe_str(val) -> str | None:
    """Return stripped string or None for blanks/NaN."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ("nan", "none", "nat") else None

TRACKED_FIELDS = [
    "forecast_category",
    "forecast_acv_amount",
    "approval_status",
    "close_date",
    "probability_pct",
    "opportunity_owner",
    "service_expiry_period",
    "renewal_category",
    "months_delayed",
]


class DiffService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Path A: ingest from Comparison Tool sheets
    # ------------------------------------------------------------------

    def ingest_from_comparison_tool(
        self,
        ctx: UserContext,
        to_snapshot: UploadSnapshot,
        sheets: dict[str, pd.DataFrame],
    ) -> None:
        """
        Read FinalChangeReport and ForecastMovementSummary sheets and persist
        as ChangeLog + ForecastMovementLog rows.

        Sheet keys in `sheets` dict match exact Excel sheet names (case-sensitive).
        """
        from_snapshot = self._get_previous_snapshot(to_snapshot)
        if from_snapshot is None:
            log.warning("No previous snapshot to diff against; skipping change log.")
            return

        # Clear old change logs for this pair
        self._clear_pair(from_snapshot.id, to_snapshot.id)

        # --- FinalChangeReport (exact sheet name confirmed) ---
        change_df = sheets.get("FinalChangeReport", sheets.get("finalchangereport", pd.DataFrame()))
        if not change_df.empty:
            self._ingest_change_report(change_df, from_snapshot, to_snapshot)

        # --- ForecastMovementSummary (Movement / Count format confirmed) ---
        movement_df = sheets.get("ForecastMovementSummary", sheets.get("forecastmovementsummary", pd.DataFrame()))
        if not movement_df.empty:
            self._ingest_forecast_movement(movement_df, from_snapshot, to_snapshot)

    # ------------------------------------------------------------------
    # Path B: compute diffs from raw opportunity rows (fallback)
    # ------------------------------------------------------------------

    def compute_diffs(
        self,
        ctx: UserContext,
        from_snapshot: UploadSnapshot,
        to_snapshot: UploadSnapshot,
    ) -> None:
        """
        Compare all tracked fields between two snapshots and write ChangeLog rows.
        """
        self._clear_pair(from_snapshot.id, to_snapshot.id)

        from_opps = {
            o.opportunity_id_18: o
            for o in self.db.query(Opportunity)
            .filter(Opportunity.snapshot_id == from_snapshot.id)
            .all()
            if o.opportunity_id_18
        }
        to_opps = {
            o.opportunity_id_18: o
            for o in self.db.query(Opportunity)
            .filter(Opportunity.snapshot_id == to_snapshot.id)
            .all()
            if o.opportunity_id_18
        }

        logs: list[ChangeLog] = []
        movements: dict[tuple[str, str], dict] = {}  # (from_cat, to_cat) → {count, acv}

        all_ids = set(from_opps) | set(to_opps)
        for opp_id in all_ids:
            from_opp = from_opps.get(opp_id)
            to_opp = to_opps.get(opp_id)
            status = "New" if from_opp is None else "Existing"

            opp_name = (to_opp or from_opp).opportunity_name  # type: ignore[union-attr]

            if from_opp is None:
                # Brand new opportunity
                cl = ChangeLog(
                    snapshot_from_id=from_snapshot.id,
                    snapshot_to_id=to_snapshot.id,
                    opportunity_id_18=opp_id,
                    opportunity_name=opp_name,
                    changed_column="opportunity_id_18",
                    old_value=None,
                    new_value=opp_id,
                    opportunity_status="New",
                    change_type="New Opportunity",
                )
                logs.append(cl)
                continue

            if to_opp is None:
                # Opportunity disappeared (closed / removed)
                cl = ChangeLog(
                    snapshot_from_id=from_snapshot.id,
                    snapshot_to_id=to_snapshot.id,
                    opportunity_id_18=opp_id,
                    opportunity_name=opp_name,
                    changed_column="opportunity_id_18",
                    old_value=opp_id,
                    new_value=None,
                    opportunity_status="Existing",
                    change_type="Opportunity Removed",
                )
                logs.append(cl)
                continue

            # Field-by-field diff
            for field in TRACKED_FIELDS:
                old_val = getattr(from_opp, field, None)
                new_val = getattr(to_opp, field, None)
                if str(old_val) != str(new_val):
                    change_type = self._classify_change(field, old_val, new_val)
                    logs.append(
                        ChangeLog(
                            snapshot_from_id=from_snapshot.id,
                            snapshot_to_id=to_snapshot.id,
                            opportunity_id_18=opp_id,
                            opportunity_name=opp_name,
                            changed_column=field,
                            old_value=str(old_val) if old_val is not None else None,
                            new_value=str(new_val) if new_val is not None else None,
                            opportunity_status=status,
                            change_type=change_type,
                        )
                    )

            # Track forecast category movements
            fc_from = from_opp.forecast_category or "Blank"
            fc_to = to_opp.forecast_category or "Blank"
            if fc_from != fc_to:
                key = (fc_from, fc_to)
                if key not in movements:
                    movements[key] = {"count": 0, "acv": Decimal(0)}
                movements[key]["count"] += 1
                movements[key]["acv"] += to_opp.forecast_acv_amount or Decimal(0)

        self.db.bulk_save_objects(logs)

        for (fc_from, fc_to), data in movements.items():
            self.db.add(
                ForecastMovementLog(
                    snapshot_from_id=from_snapshot.id,
                    snapshot_to_id=to_snapshot.id,
                    from_category=fc_from,
                    to_category=fc_to,
                    opportunity_count=data["count"],
                    acv_total=data["acv"],
                )
            )
        log.info(
            "Computed %d change log rows for %s→%s",
            len(logs),
            from_snapshot.label,
            to_snapshot.label,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_previous_snapshot(self, snapshot: UploadSnapshot) -> UploadSnapshot | None:
        return (
            self.db.query(UploadSnapshot)
            .filter(UploadSnapshot.snapshot_date < snapshot.snapshot_date)
            .order_by(UploadSnapshot.snapshot_date.desc())
            .first()
        )

    def _clear_pair(self, from_id: str, to_id: str) -> None:
        self.db.query(ChangeLog).filter(
            ChangeLog.snapshot_from_id == from_id,
            ChangeLog.snapshot_to_id == to_id,
        ).delete()
        self.db.query(ForecastMovementLog).filter(
            ForecastMovementLog.snapshot_from_id == from_id,
            ForecastMovementLog.snapshot_to_id == to_id,
        ).delete()

    def _classify_change(self, field: str, old_val, new_val) -> str:
        if field == "forecast_acv_amount":
            return "ACV Change"
        if field == "forecast_category":
            return "Category Move"
        if field == "approval_status":
            return "Approval Change"
        if field == "close_date":
            return "Date Change"
        if field == "probability_pct":
            return "Probability Change"
        if field == "opportunity_owner":
            return "Owner Change"
        return "Field Change"

    def _ingest_change_report(
        self,
        df: pd.DataFrame,
        from_snapshot: UploadSnapshot,
        to_snapshot: UploadSnapshot,
    ) -> None:
        """
        Parse FinalChangeReport sheet into ChangeLog rows.

        Confirmed columns from the real file:
          'Opportunity ID 18 Digit', 'Opportunity Name', 'Changed Column',
          'Old Value', 'New Value', 'Affected Pivot', 'Opportunity Status',
          'Change Type'
        """
        logs: list[ChangeLog] = []
        for _, row in df.iterrows():
            opp_id = _safe_str(row.get("Opportunity ID 18 Digit") or row.get("opportunity id 18 digit"))
            logs.append(
                ChangeLog(
                    snapshot_from_id=from_snapshot.id,
                    snapshot_to_id=to_snapshot.id,
                    opportunity_id_18=opp_id,
                    opportunity_name=_safe_str(
                        row.get("Opportunity Name") or row.get("opportunity name")
                    ),
                    changed_column=_safe_str(
                        row.get("Changed Column") or row.get("changed column")
                    ),
                    old_value=_safe_str(row.get("Old Value") or row.get("old value")),
                    new_value=_safe_str(row.get("New Value") or row.get("new value")),
                    opportunity_status=_safe_str(
                        row.get("Opportunity Status") or row.get("opportunity status") or "Existing"
                    ),
                    change_type=_safe_str(
                        row.get("Change Type") or row.get("change type") or "Field Change"
                    ),
                )
            )
        self.db.bulk_save_objects(logs)
        log.info("Ingested %d change log rows from FinalChangeReport", len(logs))


    def _ingest_forecast_movement(
        self,
        df: pd.DataFrame,
        from_snapshot: UploadSnapshot,
        to_snapshot: UploadSnapshot,
    ) -> None:
        """
        Parse ForecastMovementSummary into ForecastMovementLog rows.

        Confirmed columns from real file:
          'Movement'  — e.g. "Commit -> Closed"
          'Count'     — number of opportunities (no ACV column in this sheet)

        The ACV is left as 0; it can be joined from opportunity rows if needed.
        """
        added = 0
        for _, row in df.iterrows():
            movement_raw = str(row.get("Movement", "")).strip()
            count_raw    = row.get("Count", 0)

            if not movement_raw or movement_raw.lower() in ("nan", "movement", "total"):
                continue  # skip header repeat rows / totals

            # Parse "Commit -> Closed"  (also handle "→" or ">" as separator)
            for sep in [" -> ", " → ", " > ", "->", "→"]:
                if sep in movement_raw:
                    parts = movement_raw.split(sep, 1)
                    from_cat = parts[0].strip()
                    to_cat   = parts[1].strip()
                    break
            else:
                log.debug("Cannot parse movement string: %r", movement_raw)
                continue

            try:
                count = int(float(str(count_raw).replace(",", "") or 0))
            except (ValueError, TypeError):
                count = 0

            self.db.add(
                ForecastMovementLog(
                    snapshot_from_id=from_snapshot.id,
                    snapshot_to_id=to_snapshot.id,
                    from_category=from_cat,
                    to_category=to_cat,
                    opportunity_count=count,
                    acv_total=Decimal(0),   # not available in this sheet
                )
            )
            added += 1

        log.info("Ingested %d forecast movement rows", added)
