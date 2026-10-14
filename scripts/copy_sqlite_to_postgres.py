#!/usr/bin/env python3
"""
scripts/copy_sqlite_to_postgres.py

Migrates data from an existing SQLite database file into the target
PostgreSQL database (read from DATABASE_URL or settings).
Tables are copied in foreign-key dependency order derived dynamically
from SQLAlchemy models (Base.metadata.sorted_tables).
Values are converted by column type (SQLite 0/1 -> bool, JSON strings -> JSON).
Postgres sequences are reset after copying.
At the end, a table of source vs target row counts is printed and exit 1 if any differ.
"""
import os
import sys
import json
import argparse
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import create_engine, text, inspect, Boolean, JSON
from backend.config import settings
from backend.database import Base
# Import models to ensure Base.metadata is fully populated
import backend.models.opportunity
import backend.models.snapshot
import backend.models.change_log
import backend.models.daily_summary


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(str(cell)))

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    header_line = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"

    lines = [sep, header_line, sep]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)) + " |")
    lines.append(sep)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Copy SQLite renewal data to PostgreSQL.")
    parser.add_argument("--sqlite", required=True, help="Path to source SQLite .db file")
    parser.add_argument("--force", action="store_true", help="Force copy even if target PostgreSQL already contains rows")
    parser.add_argument("--target-url", default=None, help="Optional target database URL (defaults to DATABASE_URL)")
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.is_absolute():
        sqlite_path = ROOT_DIR / sqlite_path

    if not sqlite_path.exists():
        print(f"Error: SQLite source file not found at {sqlite_path}", file=sys.stderr)
        return 1

    # Connect to SQLite source
    sqlite_url = f"sqlite:///{sqlite_path}"
    print(f"Reading from source SQLite: {sqlite_path}...")
    src_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

    # Connect to target database
    target_url = args.target_url or settings.sqlalchemy_database_url
    masked_url = target_url.split("@")[-1] if "@" in target_url else target_url
    print(f"Target database: {masked_url}")

    dst_engine = create_engine(target_url, pool_pre_ping=True)

    # 1. Build table list dynamically from SQLAlchemy models in foreign-key order
    model_tables = Base.metadata.sorted_tables
    print(f"Discovered {len(model_tables)} models in FK dependency order:")
    for t in model_tables:
        print(f"  - {t.name}")

    with src_engine.connect() as src_conn, dst_engine.connect() as dst_conn:
        src_insp = inspect(src_engine)
        src_table_names = set(src_insp.get_table_names())

        dst_insp = inspect(dst_engine)
        dst_table_names = set(dst_insp.get_table_names())

        # Check existing data in target
        target_has_data = False
        for t in model_tables:
            if t.name in dst_table_names:
                count = dst_conn.execute(text(f"SELECT count(*) FROM {t.name}")).scalar() or 0
                if count > 0:
                    target_has_data = True
                    break

        if target_has_data and not args.force:
            print(
                "Error: Target database already contains existing data.\n"
                "Refusing to overwrite. Pass --force to override and proceed.",
                file=sys.stderr,
            )
            return 1

        # Delete existing data if force is specified (in reverse FK order)
        if target_has_data and args.force:
            print("Purging existing data in target database in reverse FK order...")
            with dst_engine.begin() as del_conn:
                for t in reversed(model_tables):
                    if t.name in dst_table_names:
                        del_conn.execute(text(f"DELETE FROM {t.name}"))

        # Copy each table in FK order
        with dst_engine.begin() as copy_conn:
            for t in model_tables:
                tbl_name = t.name

                # If a source table is missing, print a warning
                if tbl_name not in src_table_names:
                    print(f"WARNING: Source table '{tbl_name}' is missing in SQLite file {sqlite_path.name}")
                    # If a table exists in models but isn't in SQLite, only skip when empty
                    continue

                # Query rows from SQLite
                src_rows = src_conn.execute(text(f"SELECT * FROM {tbl_name}")).mappings().all()

                if not src_rows:
                    print(f"Table '{tbl_name}': 0 rows in source, skipping copy.")
                    continue

                # Identify column types for conversion
                bool_cols = {c.name for c in t.columns if isinstance(c.type, Boolean)}
                json_cols = {c.name for c in t.columns if isinstance(c.type, JSON)}

                insert_stmt = t.insert()

                print(f"Copying {len(src_rows)} rows into '{tbl_name}'...")
                chunk_size = 500
                for i in range(0, len(src_rows), chunk_size):
                    chunk = []
                    for raw_row in src_rows[i : i + chunk_size]:
                        row_dict = dict(raw_row)
                        for k, v in row_dict.items():
                            if k in bool_cols and v is not None:
                                row_dict[k] = bool(v)
                            elif k in json_cols and v is not None:
                                if isinstance(v, str):
                                    try:
                                        row_dict[k] = json.loads(v)
                                    except Exception:
                                        pass
                        chunk.append(row_dict)
                    copy_conn.execute(insert_stmt, chunk)

    # 2. Reset every Postgres sequence
    is_postgres = dst_engine.dialect.name == "postgresql"
    if is_postgres:
        print("Resetting PostgreSQL sequences...")
        with dst_engine.begin() as seq_conn:
            for t in model_tables:
                tbl_name = t.name
                # Check each column for sequence association
                for c in t.columns:
                    col_name = c.name
                    seq_check_sql = text("SELECT pg_get_serial_sequence(:tbl, :col)")
                    seq_name = seq_conn.execute(seq_check_sql, {"tbl": tbl_name, "col": col_name}).scalar()
                    if seq_name:
                        reset_sql = text(
                            f"SELECT setval(:seq, COALESCE((SELECT MAX({col_name}) FROM {tbl_name}), 1), "
                            f"(SELECT COUNT(*) > 0 FROM {tbl_name}))"
                        )
                        seq_conn.execute(reset_sql, {"seq": seq_name})
                        print(f"  Reset sequence '{seq_name}' for {tbl_name}.{col_name}")

    # 3. Print table of source versus target row counts and verify
    print("\nVerifying row counts across all model tables...")
    headers = ["Table Name", "Source (SQLite)", "Target (Postgres)", "Status"]
    table_rows = []
    has_mismatch = False

    with src_engine.connect() as s_conn, dst_engine.connect() as d_conn:
        src_tables = set(inspect(src_engine).get_table_names())
        dst_tables = set(inspect(dst_engine).get_table_names())

        for t in model_tables:
            tbl_name = t.name
            src_count = s_conn.execute(text(f"SELECT count(*) FROM {tbl_name}")).scalar() if tbl_name in src_tables else 0
            dst_count = d_conn.execute(text(f"SELECT count(*) FROM {tbl_name}")).scalar() if tbl_name in dst_tables else 0

            status = "MATCH" if src_count == dst_count else "MISMATCH"
            if src_count != dst_count:
                has_mismatch = True

            table_rows.append([tbl_name, str(src_count), str(dst_count), status])

    summary_output = format_table(headers, table_rows)
    print("\n" + summary_output + "\n")

    if has_mismatch:
        print("ERROR: Row count mismatch detected between source and target databases!", file=sys.stderr)
        return 1

    print("Data migration completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
