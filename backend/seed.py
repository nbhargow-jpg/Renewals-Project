"""
seed.py — loads the real Excel files from /data into the database as three
starter snapshots (today, today-1, today-7).

Run: python -m backend.seed
"""
import sys
import logging
from datetime import date, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("seed")


def main():
    # Must import after path setup
    from backend.database import init_db, SessionLocal
    from backend.config import settings
    from backend.services.ingest_service import IngestService
    from backend.services.diff_service import DiffService
    from backend.services.context import ADMIN_CONTEXT

    renewals_path = settings.DATA_DIR / "Renewals Summary 3.xlsx"
    comparison_path = settings.DATA_DIR / "Renewal Comparison Tool 11.xlsx"

    if not renewals_path.exists():
        log.error("File not found: %s", renewals_path)
        sys.exit(1)

    log.info("Initialising database tables...")
    init_db()

    db = SessionLocal()
    try:
        svc = IngestService(db)
        today = date.today()

        log.info("Ingesting Renewals Summary — will create 3 snapshots (today, yesterday, lastweek)...")
        snap_today = svc.ingest_renewals_summary(
            ADMIN_CONTEXT,
            renewals_path,
            snapshot_date=today,
            label="Today",
        )
        log.info("Today snapshot: %s (id=%s)", snap_today.snapshot_date, snap_today.id)

        if comparison_path.exists():
            log.info("Ingesting Comparison Tool change logs...")
            svc.ingest_comparison_tool(ADMIN_CONTEXT, comparison_path, snap_today)
        else:
            log.warning("Comparison Tool not found at %s — computing diffs from raw data", comparison_path)
            diff_svc = DiffService(db)
            # Find yesterday snapshot and compute diffs
            from backend.models.snapshot import UploadSnapshot
            yest_snap = (
                db.query(UploadSnapshot)
                .filter(UploadSnapshot.snapshot_date == today - timedelta(days=1))
                .first()
            )
            if yest_snap:
                diff_svc.compute_diffs(ADMIN_CONTEXT, yest_snap, snap_today)

        db.commit()
        log.info("✅ Seed complete. Database ready at: %s", settings.DATABASE_URL)

    except Exception as exc:
        db.rollback()
        log.error("Seed failed: %s", exc, exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    # Make sure project root is on path when running as script
    import os
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    main()
