# Capital — operational shortcuts. Production targets use the base compose
# file plus the production overrides (never the dev override).

COMPOSE = docker compose -f docker-compose.yml -f docker-compose.prod.yml

.PHONY: help deploy build up down restart logs ps backup restore

help:
	@echo "Capital — make targets:"
	@echo "  make deploy    Pull, build, migrate, restart, health-check"
	@echo "  make build     Build the production images"
	@echo "  make up        Start the stack (detached)"
	@echo "  make down      Stop the stack"
	@echo "  make restart   Restart the stack"
	@echo "  make logs      Follow logs"
	@echo "  make ps        Show running services"
	@echo "  make backup    Back up the PostgreSQL database"
	@echo "  make restore   Restore the database from a backup"

deploy:
	./scripts/deploy.sh

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

backup:
	./scripts/backup.sh

restore:
	./scripts/restore.sh
