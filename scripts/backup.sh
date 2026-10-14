#!/bin/bash
set -euo pipefail

# scripts/backup.sh
# Performs a pg_dump backup of the renewals PostgreSQL database.
# Daily retention: retains the latest 30 backups.

BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-renewals_user}"
DB_NAME="${DB_NAME:-renewals_prod}"
PGPASSWORD="${PGPASSWORD:-renewals_secret}"
export PGPASSWORD

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.dump"

echo "Creating PostgreSQL backup of ${DB_NAME} to ${BACKUP_FILE}..."
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -F c -b -v -f "$BACKUP_FILE" "$DB_NAME"

echo "Backup created successfully: ${BACKUP_FILE}"

# Retention policy: keep 30 daily backups
echo "Applying retention policy: keeping latest 30 backups..."
find "$BACKUP_DIR" -name "${DB_NAME}_*.dump" -type f | sort -r | tail -n +31 | xargs -r rm -f

echo "Retention cleanup complete."
