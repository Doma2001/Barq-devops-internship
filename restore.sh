#!/usr/bin/env bash
set -euo pipefail
# Restores a PostgreSQL backup (produced by backup.sh) into the running
# "postgres" container. Usage: ./restore.sh backups/barq_tasks_<timestamp>.sql

PROJECT="barq-assessment"
DB_USER="barq_app"
DB_NAME="barq_tasks"

if [ $# -ne 1 ]; then
  echo "Usage: $0 <path-to-backup-file>" >&2
  exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERROR: backup file not found: ${BACKUP_FILE}" >&2
  exit 1
fi

echo "Restoring ${BACKUP_FILE} into database '${DB_NAME}' ..."

docker compose -p "$PROJECT" exec -T postgres \
  psql -U "$DB_USER" -d "$DB_NAME" \
  < "$BACKUP_FILE"

echo "Restore complete."
