#!/usr/bin/env bash
#
# Capital — single-command installer.
#
# Brings the whole stack up with Docker Compose: PostgreSQL, the trading
# engine (database migrations applied automatically) and the web dashboard.
#
# Usage:
#   scripts/install.sh           # development mode (hot reload)
#   scripts/install.sh prod      # production-style mode (built assets)
#
set -euo pipefail

# Always operate from the repository root, wherever the script is called from.
cd "$(dirname "$0")/.."

info()  { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
warn()  { printf '\033[1;33m !!\033[0m %s\n' "$1"; }
die()   { printf '\033[1;31m xx\033[0m %s\n' "$1" >&2; exit 1; }

MODE="${1:-dev}"
case "$MODE" in
  dev|prod) ;;
  *) die "Unknown mode '$MODE' — use 'dev' or 'prod'." ;;
esac

# --- 1. Prerequisites ----------------------------------------------------
info "Checking prerequisites"
command -v docker >/dev/null 2>&1 \
  || die "Docker is not installed — see https://docs.docker.com/get-docker/"
docker compose version >/dev/null 2>&1 \
  || die "Docker Compose v2 is required (the 'docker compose' subcommand)."
docker info >/dev/null 2>&1 \
  || die "The Docker daemon is not running — start Docker and retry."

# --- 2. Environment file -------------------------------------------------
if [ -f .env ]; then
  info ".env already exists — keeping your settings"
else
  info "Creating .env from .env.example"
  cp .env.example .env
  warn "Default credentials are for local/simulation use only."
  warn "Edit .env and change the secrets before any real deployment."
fi

# --- 3. Build & start ----------------------------------------------------
if [ "$MODE" = "prod" ]; then
  # Base compose only — skip the dev override (hot reload, Vite dev server).
  COMPOSE=(docker compose -f docker-compose.yml)
  info "Building and starting the stack (production mode)"
else
  # docker-compose.override.yml is merged automatically.
  COMPOSE=(docker compose)
  info "Building and starting the stack (development mode)"
fi
"${COMPOSE[@]}" up -d --build

# --- 4. Wait for the engine to become healthy ---------------------------
ENGINE_PORT="$( (grep -E '^ENGINE_PORT=' .env | cut -d= -f2) || true)"
ENGINE_PORT="${ENGINE_PORT:-8000}"
WEB_PORT="$( (grep -E '^WEB_PORT=' .env | cut -d= -f2) || true)"
WEB_PORT="${WEB_PORT:-5173}"

if command -v curl >/dev/null 2>&1; then
  info "Waiting for the engine to become healthy on port ${ENGINE_PORT}"
  for i in $(seq 1 60); do
    if curl -fsS "http://localhost:${ENGINE_PORT}/health" >/dev/null 2>&1; then
      info "Engine is healthy."
      break
    fi
    if [ "$i" -eq 60 ]; then
      die "Engine did not become healthy in time — check '${COMPOSE[*]} logs engine'."
    fi
    sleep 2
  done
else
  warn "curl not found — skipping the health check. Verify with '${COMPOSE[*]} ps'."
fi

# --- 5. Done -------------------------------------------------------------
cat <<EOF

  Capital is running.

    Dashboard    http://localhost:${WEB_PORT}
    API + docs   http://localhost:${ENGINE_PORT}/docs

  Log in with the admin credentials from .env
  (CAPITAL_ADMIN_USERNAME / CAPITAL_ADMIN_PASSWORD).

  Useful commands:
    ${COMPOSE[*]} logs -f       follow logs
    ${COMPOSE[*]} down          stop the stack
    ${COMPOSE[*]} down -v       stop and wipe the database

EOF
