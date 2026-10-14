#!/usr/bin/env python3
"""
scripts/check_db.py

Inspects DATABASE_URL from settings / environment, connects to the database,
checks connectivity, server version, Alembic migration state, and table row counts.
Never prints database passwords.
Exits 0 on success, or 1 on failure with a plain-English reason.
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import create_engine, text, inspect
from backend.config import settings


def sanitize_url(raw_url: str):
    """Parse database URL and return dialect, host, port, db_name, user without password."""
    # Handle sqlite:/// paths cleanly
    if raw_url.startswith("sqlite"):
        parsed = urlparse(raw_url)
        db_path = parsed.path or raw_url.replace("sqlite:///", "")
        return {
            "dialect": "sqlite",
            "host": "local",
            "port": None,
            "database": db_path or ":memory:",
            "user": None,
        }

    try:
        parsed = urlparse(raw_url)
        # dialect may be postgresql+psycopg2 or postgresql+psycopg
        dialect = parsed.scheme.split("+")[0] if "+" in parsed.scheme else parsed.scheme
        db_name = parsed.path.lstrip("/") if parsed.path else ""
        return {
            "dialect": dialect,
            "host": parsed.hostname or "localhost",
            "port": parsed.port or (5432 if "postgres" in dialect else None),
            "database": db_name,
            "user": parsed.username or None,
        }
    except Exception:
        return {
            "dialect": "unknown",
            "host": "unknown",
            "port": None,
            "database": "unknown",
            "user": None,
        }


def check_alembic(engine):
    """Compare current database revision against Alembic head."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext

        alembic_ini_path = ROOT_DIR / "alembic.ini"
        if not alembic_ini_path.exists():
            return None, None, "alembic.ini not found"

        alembic_cfg = Config(str(alembic_ini_path))
        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()

        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            current_rev = ctx.get_current_revision()

        return current_rev, head_rev, None
    except Exception as e:
        return None, None, str(e)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Check database connectivity and status.")
    parser.add_argument("--url", default=None, help="Database URL to check (defaults to DATABASE_URL)")
    args, _ = parser.parse_known_args()

    raw_url = args.url or os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    info = sanitize_url(raw_url)

    # 1. Print connection metadata (never print password)
    port_str = f":{info['port']}" if info.get("port") else ""
    user_str = f", User: {info['user']}" if info.get("user") else ""
    print(f"Dialect:  {info['dialect']}")
    print(f"Host:     {info['host']}{port_str}")
    print(f"Database: {info['database']}{user_str}")

    # 2. Connect and test
    if args.url or os.environ.get("DATABASE_URL"):
        target_url = raw_url
        if target_url.startswith("postgres://"):
            target_url = target_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif target_url.startswith("postgresql://") and not target_url.startswith("postgresql+"):
            target_url = target_url.replace("postgresql://", "postgresql+psycopg://", 1)
    else:
        target_url = settings.sqlalchemy_database_url
    engine_kwargs = {"pool_pre_ping": True}
    if info["dialect"] == "sqlite":
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    try:
        engine = create_engine(target_url, **engine_kwargs)
        with engine.connect() as conn:
            # Run SELECT 1
            conn.execute(text("SELECT 1"))

            # Server version check
            server_version = "unknown"
            if info["dialect"] == "sqlite":
                res = conn.execute(text("SELECT sqlite_version()")).scalar()
                server_version = f"SQLite {res}"
            elif "postgres" in info["dialect"]:
                res = conn.execute(text("SELECT version()")).scalar()
                # e.g. "PostgreSQL 16.2 on x86_64-pc-linux-gnu..." -> concise version
                server_version = res.split()[0] + " " + res.split()[1] if res else "PostgreSQL"
            else:
                server_version = getattr(engine.dialect, "server_version_info", "unknown")

            print(f"Server:   {server_version}")

            # 3. Alembic revision check
            current_rev, head_rev, err = check_alembic(engine)
            if err:
                print(f"Alembic:  Error reading revisions ({err})")
            else:
                status_str = "at head" if current_rev == head_rev else f"BEHIND head ({head_rev})"
                print(f"Alembic:  Current: {current_rev or 'none'} | Head: {head_rev} ({status_str})")

            # 4. Row counts
            insp = inspect(engine)
            tables = insp.get_table_names()
            snap_count = 0
            opp_count = 0
            if "upload_snapshots" in tables:
                snap_count = conn.execute(text("SELECT count(*) FROM upload_snapshots")).scalar() or 0
            if "opportunities" in tables:
                opp_count = conn.execute(text("SELECT count(*) FROM opportunities")).scalar() or 0

            print(f"Counts:   upload_snapshots: {snap_count} rows | opportunities: {opp_count} rows")

        print("Status:   OK")
        return 0

    except Exception as e:
        err_msg = str(e).lower()
        reason = "Connection failed"
        if "password authentication failed" in err_msg:
            reason = "Wrong password: password authentication failed for user"
        elif "could not connect to server" in err_msg or "connection refused" in err_msg:
            reason = "Host unreachable or port closed: could not establish TCP connection to server"
        elif "database" in err_msg and "does not exist" in err_msg:
            reason = f"Database missing: database '{info['database']}' does not exist on host"
        elif "timeout" in err_msg:
            reason = "Connection timed out: host unreachable"
        else:
            reason = f"Database error: {e}"

        print(f"Status:   FAILED - {reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
