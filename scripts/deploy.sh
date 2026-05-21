#!/usr/bin/env bash
#
# Capital — production deploy. Pulls main, rebuilds the images, applies
# database migrations, restarts the stack and verifies the engine is healthy.
#
# Usage:  scripts/deploy.sh   (or `make deploy`)
#
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

info() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m xx\033[0m %s\n' "$1" >&2; exit 1; }

# --- Preconditions -------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "Docker is not installed."
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required."
[ -f .env ] || die ".env not found — copy .env.example and configure it first."

# --- 1. Pull -------------------------------------------------------------
info "Pulling latest main"
git pull --ff-only origin main

# --- 2. Build ------------------------------------------------------------
info "Building images"
"${COMPOSE[@]}" build

# --- 3. Migrate ----------------------------------------------------------
info "Applying database migrations"
"${COMPOSE[@]}" run --rm engine alembic upgrade head

# --- 4. Start ------------------------------------------------------------
info "Starting the stack"
"${COMPOSE[@]}" up -d

# --- 5. Health check -----------------------------------------------------
info "Waiting for the engine to become healthy"
for i in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T engine \
      python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
      >/dev/null 2>&1; then
    info "Engine is healthy."
    break
  fi
  if [ "$i" -eq 60 ]; then
    die "Engine did not become healthy — check '${COMPOSE[*]} logs engine'."
  fi
  sleep 2
done

# --- 6. Prune ------------------------------------------------------------
info "Pruning dangling images"
docker image prune -f >/dev/null

info "Deploy complete."
