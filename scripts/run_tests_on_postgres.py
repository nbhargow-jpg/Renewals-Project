#!/usr/bin/env python3
"""
scripts/run_tests_on_postgres.py
Starts a throwaway PostgreSQL 16 server in scratch/pg_data on port 54329,
creates the test database, runs pytest with TEST_DATABASE_URL,
and ensures clean shutdown.
"""
import os
import sys
import time
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRATCH_DIR = ROOT_DIR / "scratch"
BIN_DIR = SCRATCH_DIR / "pgsql" / "bin"
DATA_DIR = SCRATCH_DIR / "pg_data"
PORT = 54329
DB_NAME = "renewals_test"
TEST_URL = f"postgresql+psycopg://postgres@localhost:{PORT}/{DB_NAME}"

def main():
    if not (BIN_DIR / "postgres.exe").exists():
        print(f"Postgres binary not found at {BIN_DIR / 'postgres.exe'}. Setting up...")
        res = subprocess.run([sys.executable, str(SCRATCH_DIR / "setup_pg_bin.py")], cwd=str(ROOT_DIR))
        if res.returncode != 0:
            print("Failed to setup postgres binary.")
            sys.exit(1)

    if not DATA_DIR.exists():
        print("Initializing postgres data directory...")
        subprocess.run(
            [str(BIN_DIR / "initdb.exe"), "-D", str(DATA_DIR), "-U", "postgres", "-A", "trust", "--no-locale", "-E", "UTF8"],
            check=True
        )

    print(f"Starting PostgreSQL 16 server on port {PORT}...")
    server_proc = subprocess.Popen(
        [str(BIN_DIR / "postgres.exe"), "-D", str(DATA_DIR), "-p", str(PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    import psycopg
    conn = None
    for attempt in range(20):
        try:
            conn = psycopg.connect(f"postgresql://postgres@localhost:{PORT}/postgres", autocommit=True)
            break
        except Exception:
            time.sleep(1)

    if not conn:
        print("Failed to connect to PostgreSQL server after 20 seconds.")
        server_proc.terminate()
        sys.exit(1)

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
                cur.execute(f"CREATE DATABASE {DB_NAME}")
        print(f"Created clean test database '{DB_NAME}'.")

        # Run pytest with TEST_DATABASE_URL set
        env = os.environ.copy()
        env["TEST_DATABASE_URL"] = TEST_URL
        env["DATABASE_URL"] = TEST_URL

        test_args = sys.argv[1:]
        if not test_args:
            test_args = [
                "backend/tests/test_v2_overview.py",
                "backend/tests/test_v2_business_units.py",
                "backend/tests/test_v2_regions.py",
                "backend/tests/test_v2_delayed.py",
                "backend/tests/test_v2_approvals.py",
                "backend/tests/test_v2_expiry.py",
                "backend/tests/test_oct7_upload_e2e.py",
                "backend/tests/test_scopes.py",
                "backend/tests/test_time_travel.py",
            ]

        cmd = [sys.executable, "-m", "pytest"] + test_args
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, env=env, cwd=str(ROOT_DIR))
        sys.exit(result.returncode)
    finally:
        print("Stopping PostgreSQL 16 server...")
        server_proc.terminate()
        server_proc.wait()
        print("PostgreSQL server stopped.")

if __name__ == "__main__":
    main()
