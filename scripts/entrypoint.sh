#!/bin/sh
set -e

echo "=========================================="
echo " Starting Mobileum Horizon on Railway"
echo "=========================================="

# 1. Run Alembic database migrations
echo "==> Running database migrations (alembic upgrade head)..."
python -m alembic upgrade head || {
    echo "Warning: Alembic migration encountered an error or already up to date. Continuing startup..."
}

# 2. Check if initial seed is needed (when sample Excel files are present)
if [ -f "/app/data/Renewals Summary 3.xlsx" ]; then
    echo "==> Sample spreadsheet found. Running seed if database is empty..."
    python -m backend.seed || echo "Seed skipped or already populated."
fi

# 3. Railway dynamic port binding
PORT="${PORT:-8000}"
echo "==> Starting Uvicorn server on port ${PORT}..."
exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT}"
