.PHONY: up up-media up-env down down-env restart logs-env build shell-env init-dev init-test migrate prune django
# examples:
# make up-env ENV=dev
# make down-env ENV=prod


# Default compose args
up:
	@echo "🔼 Starting test containers without media/videos..."
	docker-compose up --build -d

ENV ?= test

up-env:
	@echo "Starting $(ENV) environment..."
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml up --build -d

down-env:
	@echo "Stopping $(ENV) environment..."
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml down --volumes

logs-env:
	@echo "Logging $(ENV) environment..."
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml logs -f

shell-env:
	@echo "Shell $(ENV) environment..."
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml exec web /bin/bash


down:
	@echo "Stopping containers..."
	docker-compose down --volumes --remove-orphans


# Start containers and prepare media
up-media:
	@echo "🔼 Preparing media and starting containers..."
	./scripts/prepare_media.sh
	docker-compose up --build

# Restart stack cleanly
restart: down up

# Tail logs from all services
logs:
	@echo "Logging containers..."
	docker-compose logs -f

# Rebuild containers only
build:
	@echo "Building containers..."
	docker-compose build

# Open shell in the web container
shell:
	docker-compose exec web /bin/bash

# Run initial setup (migrations, static files, superuser check)
init-dev:
	@echo "initializing Dev environment..."
	docker-compose exec web python manage.py migrate --noinput
	docker-compose exec web python manage.py collectstatic --noinput
	docker-compose exec web python manage.py shell -c "\
from django.contrib.auth import get_user_model; \
User = get_user_model(); \
User.objects.filter(is_superuser=True).exists() or \
User.objects.create_superuser(email='zack@boo.com', password='NotHalloween')"

init-test:
	@echo "initializing init environment..."
	docker-compose exec web python manage.py migrate --noinput
	docker-compose exec web python manage.py collectstatic --noinput
	docker-compose exec web python manage.py shell -c "\
from django.contrib.auth import get_user_model; \
User = get_user_model(); \
User.objects.filter(is_superuser=True).exists() or \
User.objects.create_superuser(email='zack@boo.com', password='NotHalloween')"

# Apply migrations manually
migrate:
	docker-compose exec web python manage.py migrate

# Clean up Docker system objects and volumes
prune:
	docker system prune -af --volumes

# Run any Django management command: `make django cmd="createsuperuser"`
django:
	docker-compose exec web python manage.py $(cmd)

