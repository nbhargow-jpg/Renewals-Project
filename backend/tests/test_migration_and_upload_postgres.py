"""
backend/tests/test_migration_and_upload_postgres.py

Automated test that runs when TEST_DATABASE_URL is set:
1. Creates a SQLite database by uploading the Oct 7 files.
2. Copies it to a fresh Postgres database using scripts/copy_sqlite_to_postgres.py.
3. Checks that all table row counts match between SQLite and Postgres.
4. Uploads the Oct 8 files on Postgres and confirms it succeeds.
"""
import os
import sys
import subprocess
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.services.context import ADMIN_CONTEXT
from backend.services.ingest_service import IngestService
from backend.models.snapshot import UploadSnapshot

ROOT_DIR = Path(__file__).resolve().parents[2]
SAMPLE_OCT7 = ROOT_DIR / "data" / "sample_oct7"
FILES = sorted(SAMPLE_OCT7.glob("*.xlsx")) if SAMPLE_OCT7.exists() else []

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.skipif(not TEST_DB_URL, reason="TEST_DATABASE_URL not set"),
    pytest.mark.skipif(len(FILES) < 4, reason="Oct 7 sample files not found in data/sample_oct7"),
]


def test_sqlite_to_postgres_migration_and_oct8_upload(tmp_path):
    # 1. Setup SQLite database file
    sqlite_file = tmp_path / "test_migration_source.db"
    sqlite_url = f"sqlite:///{sqlite_file}"
    sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=sqlite_engine)

    SqliteSession = sessionmaker(bind=sqlite_engine)
    sqlite_db = SqliteSession()

    files_dict_oct7 = {
        "comparison_tool": SAMPLE_OCT7 / "Renewal Comparison Tool.xlsx",
        "renewals_summary:FY2026": SAMPLE_OCT7 / "Renewals Summary - Fiscal 2026.xlsx",
        "renewals_summary:FY2027": SAMPLE_OCT7 / "Renewals Summary - Fiscal 2027.xlsx",
        "renewals_summary:Q4-2026": SAMPLE_OCT7 / "Renewals Summary - Fiscal Q4.xlsx",
    }

    # Ingest Oct 7 into SQLite
    ingest_sqlite = IngestService(sqlite_db)
    val_sqlite = ingest_sqlite.validate_upload(
        ADMIN_CONTEXT,
        files_dict_oct7,
        data_as_of=date(2026, 10, 7),
        yesterday_date=date(2026, 10, 6),
    )
    assert val_sqlite["can_commit"] is True, f"SQLite validation failed: {val_sqlite['errors']}"
    snap_sqlite = ingest_sqlite.commit_upload(ADMIN_CONTEXT, val_sqlite["session_id"])
    assert snap_sqlite is not None
    sqlite_db.close()

    # 2. Reset Postgres target tables to ensure a fresh state
    pg_url = TEST_DB_URL
    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif pg_url.startswith("postgresql://") and not pg_url.startswith("postgresql+"):
        pg_url = pg_url.replace("postgresql://", "postgresql+psycopg://", 1)

    pg_engine = create_engine(pg_url, pool_pre_ping=True)
    Base.metadata.drop_all(bind=pg_engine)
    Base.metadata.create_all(bind=pg_engine)

    # 3. Run migration script: copy SQLite to Postgres
    script_path = ROOT_DIR / "scripts" / "copy_sqlite_to_postgres.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--sqlite",
        str(sqlite_file),
        "--target-url",
        pg_url,
        "--force",
    ]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
    print("Migration output:\n", res.stdout)
    if res.stderr:
        print("Migration stderr:\n", res.stderr)
    assert res.returncode == 0, f"copy_sqlite_to_postgres failed with code {res.returncode}"

    # 4. Verify row counts match across all model tables
    with sqlite_engine.connect() as s_conn, pg_engine.connect() as p_conn:
        for t in Base.metadata.sorted_tables:
            tbl_name = t.name
            s_count = s_conn.execute(text(f"SELECT count(*) FROM {tbl_name}")).scalar()
            p_count = p_conn.execute(text(f"SELECT count(*) FROM {tbl_name}")).scalar()
            assert s_count == p_count, f"Table {tbl_name} row count mismatch: SQLite={s_count}, Postgres={p_count}"

    # 5. Upload Oct 8 on Postgres and confirm it succeeds
    PgSession = sessionmaker(bind=pg_engine)
    pg_db = PgSession()
    ingest_pg = IngestService(pg_db)

    val_oct8 = ingest_pg.validate_upload(
        ADMIN_CONTEXT,
        files_dict_oct7,
        data_as_of=date(2026, 10, 8),
        yesterday_date=date(2026, 10, 7),
    )
    assert val_oct8["can_commit"] is True, f"Oct 8 upload validation on Postgres failed: {val_oct8['errors']}"
    snap_oct8 = ingest_pg.commit_upload(ADMIN_CONTEXT, val_oct8["session_id"])
    assert snap_oct8 is not None
    assert snap_oct8.snapshot_date == date(2026, 10, 8)

    # Confirm snapshot exists in Postgres DB
    saved_snap = pg_db.query(UploadSnapshot).filter(UploadSnapshot.snapshot_date == date(2026, 10, 8)).first()
    assert saved_snap is not None
    pg_db.close()
