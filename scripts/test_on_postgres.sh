#!/bin/bash
set -euo pipefail

# scripts/test_on_postgres.sh
# Starts a throwaway PostgreSQL server or uses DATABASE_URL/docker to run the full backend test suite on Postgres.

echo "Running full backend test suite on PostgreSQL..."
python scripts/run_tests_on_postgres.py "$@"
