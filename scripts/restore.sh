#!/usr/bin/env bash
#
# Capital — database restore. Loads a gzipped pg_dump back into PostgreSQL.
# The dump is taken with --clean, so it drops and recreates objects in place.
#
# Usage:  scripts/restore.sh [backup-file]
#         With no argument, the most recent dump in data/backups/ is used.
#
set -euo pipefail

cd "$(dirname "$0")/.."

info() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m !!\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m xx\033[0m %s\n' "$1" >&2; exit 1; }

[ -f .env ] || die ".env not found — copy .env.example and configure it first."
# shellcheck disable=SC1091
set -a; . ./.env; set +a

PG_USER="${POSTGRES_USER:-capital}"
PG_DB="${POSTGRES_DB:-capital}"

# shellcheck disable=SC2012
BACKUP="${1:-$(ls -1t data/backups/capital-*.sql.gz 2>/dev/null | head -1 || true)}"
[ -n "$BACKUP" ] || die "No backup file given and none found in data/backups/."
[ -f "$BACKUP" ] || die "Backup file not found: $BACKUP"

warn "This OVERWRITES the current '$PG_DB' database with:"
warn "  $BACKUP"
printf 'Type "restore" to continue: '
read -r answer
[ "$answer" = "restore" ] || die "Aborted."

info "Restoring into '$PG_DB'"
gunzip -c "$BACKUP" | docker compose exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$PG_DB"

info "Restore complete."
echo "  Verify the engine starts cleanly and that .env / CAPITAL_SECRET_KEY"
echo "  match this backup — otherwise stored API keys will not decrypt."
