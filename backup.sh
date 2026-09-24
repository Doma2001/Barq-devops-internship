#!/usr/bin/env bash
set -euo pipefail
# Dumps the PostgreSQL database inside the running "postgres" container to a
# timestamped .sql file on the host, using pg_dump (plain SQL format so it's
# human-readable and diffable).

PROJECT="barq-assessment"
DB_USER="barq_app"
DB_NAME="barq_tasks"
BACKUP_DIR="backups"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${BACKUP_DIR}/barq_tasks_${TIMESTAMP}.sql"

mkdir -p "$BACKUP_DIR"

echo "Backing up database '${DB_NAME}' to ${BACKUP_FILE} ..."

docker compose -p "$PROJECT" exec -T postgres \
  pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists \
  > "$BACKUP_FILE"

if [ ! -s "$BACKUP_FILE" ]; then
  echo "ERROR: backup file is empty — something went wrong." >&2
  exit 1
fi

echo "Backup complete: ${BACKUP_FILE} ($(wc -l < "$BACKUP_FILE") lines)"
