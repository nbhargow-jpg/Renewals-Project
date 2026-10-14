#!/usr/bin/env bash
# deploy/backup_db.sh
# Daily PostgreSQL backup script with 30-day retention
#
# Cron Example:
# Run daily at 02:00 AM:
# 0 2 * * * /opt/renewals/deploy/backup_db.sh >> /var/log/renewals_backup.log 2>&1
#
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/renewals/backups}"
RETENTION_DAYS=30
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ENV_FILE="${ENV_FILE:-/opt/renewals/.env}"

mkdir -p "$BACKUP_DIR"

if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

DB_NAME="${POSTGRES_DB:-renewals}"
DB_USER="${POSTGRES_USER:-renewals_user}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"

BACKUP_FILE="${BACKUP_DIR}/renewals_backup_${TIMESTAMP}.sql.gz"

echo "[$(date -Is)] Starting PostgreSQL backup for '${DB_NAME}'..."

export PGPASSWORD="${POSTGRES_PASSWORD:-}"
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --no-owner --clean | gzip > "$BACKUP_FILE"

echo "[$(date -Is)] Backup saved to: ${BACKUP_FILE} ($(du -sh "${BACKUP_FILE}" | cut -f1))"

echo "[$(date -Is)] Pruning backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -type f -name "renewals_backup_*.sql.gz" -mtime +${RETENTION_DAYS} -exec rm -f {} \;

echo "[$(date -Is)] Backup routine completed."
