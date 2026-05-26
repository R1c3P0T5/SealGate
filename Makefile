.PHONY: dev prod server worker full update build push logs down

# Development — uses override.yml automatically (hot-reload)
dev:
	docker compose --profile server up

# Development — all services including worker
dev-full:
	docker compose --profile full up

# Production — all services on one machine
prod:
	docker compose -f docker-compose.yml --profile full up -d

# Server only — backend + frontend (no worker)
server:
	docker compose -f docker-compose.yml --profile server up -d

# Worker only — jetson worker (run on Jetson or Linux with camera)
worker:
	docker compose -f docker-compose.yml --profile worker up -d

# Pull latest images and restart (run this on Jetson after a GitHub push)
update:
	docker compose pull && docker compose up -d

# Build all images locally
build:
	docker compose -f docker-compose.yml build

# Push images to registry
push:
	docker compose push

# Follow logs for all running services
logs:
	docker compose logs -f

# Stop and remove containers
down:
	docker compose down
