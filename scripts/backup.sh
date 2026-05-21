#!/usr/bin/env bash
#
# Capital — database backup. Dumps PostgreSQL to data/backups/ (off the data
# volume) as a timestamped, gzipped SQL file, and prunes old dumps.
#
# IMPORTANT: this dump does NOT contain .env / CAPITAL_SECRET_KEY. Back those
# up separately and securely — without the secret key a restored database
# cannot decrypt the stored Binance/LLM API keys.
#
# Usage:  scripts/backup.sh   (or `make backup`)
#
set -euo pipefail

cd "$(dirname "$0")/.."

info() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m xx\033[0m %s\n' "$1" >&2; exit 1; }

[ -f .env ] || die ".env not found — copy .env.example and configure it first."
# shellcheck disable=SC1091
set -a; . ./.env; set +a

PG_USER="${POSTGRES_USER:-capital}"
PG_DB="${POSTGRES_DB:-capital}"
BACKUP_DIR="data/backups"
RETAIN="${CAPITAL_BACKUP_RETAIN:-14}"  # number of dumps to keep

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$BACKUP_DIR/capital-$STAMP.sql.gz"

info "Dumping database '$PG_DB'"
# --clean --if-exists makes the dump safe to restore into a populated database.
docker compose exec -T postgres \
  pg_dump --clean --if-exists -U "$PG_USER" "$PG_DB" | gzip > "$TARGET"
[ -s "$TARGET" ] || die "Backup is empty — is the postgres service running?"
info "Wrote $TARGET ($(du -h "$TARGET" | cut -f1))"

info "Pruning old backups (keeping the newest $RETAIN)"
# shellcheck disable=SC2012
ls -1t "$BACKUP_DIR"/capital-*.sql.gz 2>/dev/null \
  | tail -n +"$((RETAIN + 1))" | xargs -r rm -f

cat <<'EOF'

  Reminder: this dump does NOT include .env / CAPITAL_SECRET_KEY.
  Back those up separately — without the secret key a restored database
  cannot decrypt the stored Binance/LLM API keys.
EOF
