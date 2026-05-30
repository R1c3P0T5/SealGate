COMPOSE_DEV := docker compose -p sealgate-dev
COMPOSE_PROD := docker compose -f docker-compose.yml
PROFILE ?= full

.PHONY: dev-setup dev-reset dev dev-full prod server worker update build push logs down

# Prepare local env files and deterministic development seed data.
dev-setup:
	python3 scripts/dev_setup.py

# Reset local Compose volumes, then recreate env files and development seed data.
dev-reset:
	python3 scripts/dev_setup.py --reset

# Development — backend + frontend with override.yml hot reload.
dev:
	$(COMPOSE_DEV) --profile server up backend frontend

# Development — backend + frontend + worker with override.yml hot reload.
dev-full:
	$(COMPOSE_DEV) --profile full up backend frontend worker

# Production — all services on one machine
prod:
	$(COMPOSE_PROD) --profile full up -d --force-recreate

# Server only — backend + frontend (no worker)
server:
	$(COMPOSE_PROD) --profile server up -d --force-recreate

# Worker only — jetson worker (run on Jetson or Linux with camera)
worker:
	$(COMPOSE_PROD) --profile worker up -d --force-recreate

# Pull latest production images and recreate containers.
# Override PROFILE for a subset, for example: make update PROFILE=worker
update:
	$(COMPOSE_PROD) --profile $(PROFILE) pull
	$(COMPOSE_PROD) --profile $(PROFILE) up -d --force-recreate

# Build all images locally
build:
	$(COMPOSE_PROD) build

# Push images to registry
push:
	$(COMPOSE_PROD) push

# Follow logs for all running services
logs:
	$(COMPOSE_PROD) logs -f

# Stop and remove containers
down:
	$(COMPOSE_PROD) down
