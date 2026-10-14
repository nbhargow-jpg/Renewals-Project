#!/usr/bin/env bash
# deploy/deploy.sh
# Production update script for Mobileum Horizon on RHEL VM
set -euo pipefail

APP_DIR="/opt/renewals"
cd "$APP_DIR"

echo "=== Pulling latest changes from git ==="
git pull origin main

echo "=== Updating Python virtual environment dependencies ==="
source "$APP_DIR/venv/bin/activate"
pip install -r requirements.txt

echo "=== Running Alembic database migrations ==="
alembic upgrade head

echo "=== Building frontend production bundle ==="
if [ -d "$APP_DIR/frontend" ]; then
    cd "$APP_DIR/frontend"
    npm ci --silent
    npm run build
    cd "$APP_DIR"
fi

echo "=== Restarting renewals systemd service ==="
sudo systemctl restart renewals.service

echo "=== Checking service health ==="
sleep 2
curl -fsS http://127.0.0.1:8000/api/health || {
    echo "Health check failed after service restart!"
    exit 1
}

echo "=== Deployment finished successfully ==="
