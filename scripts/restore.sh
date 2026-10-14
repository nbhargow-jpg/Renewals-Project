#!/bin/bash
set -euo pipefail

# scripts/restore.sh
# Restores a PostgreSQL backup file into a target database using pg_restore.

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <backup_file.dump> [target_db_name]"
    exit 1
fi

BACKUP_FILE="$1"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-renewals_user}"
DB_NAME="${2:-${DB_NAME:-renewals_prod}}"
PGPASSWORD="${PGPASSWORD:-renewals_secret}"
export PGPASSWORD

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file '$BACKUP_FILE' not found."
    exit 1
fi

echo "Restoring ${BACKUP_FILE} into ${DB_NAME} on ${DB_HOST}:${DB_PORT}..."
pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --clean --if-exists -v "$BACKUP_FILE"

echo "Restore completed successfully into ${DB_NAME}."
