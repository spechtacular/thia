.PHONY: up up-media up-env down down-env restart logs logs-env build shell shell-env init migrate prune django

# Default environment (if ENV= is not passed)
ENV ?= test


# -----------------------------
#   Base (legacy) commands
# -----------------------------

up:
	@echo "🔼 Starting TEST containers (default)..."
	docker-compose up --build -d

down:
	@echo "Stopping containers..."
	docker-compose down --volumes --remove-orphans

logs:
	@echo "Logging containers..."
	docker-compose logs -f

shell:
	docker-compose exec web /bin/bash


# -----------------------------
#   ENVIRONMENT-AWARE COMMANDS
# -----------------------------

up-env:
	@echo "🔼 Starting $(ENV) environment..."
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml up --build -d

down-env:
	@echo "⛔ Stopping $(ENV) environment..."
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml down --volumes --remove-orphans

logs-env:
	@echo "📜 Logs for $(ENV) environment..."
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml logs -f

shell-env:
	@echo "💻 Shell into $(ENV) environment web container..."
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml exec web /bin/bash


# -----------------------------
#   MEDIA VERSION
# -----------------------------

up-media:
	@echo "🔼 Preparing media and starting containers..."
	./scripts/prepare_media.sh
	docker-compose up --build -d


# -----------------------------
#   INIT (ENV-AWARE)
# -----------------------------

# Run full Django initialization for selected environment
# Usage: make init ENV=dev
init:
	@echo "⚙️ Initializing Django for $(ENV) environment..."
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml exec web python manage.py migrate --noinput
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml exec web python manage.py collectstatic --noinput
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml exec web python manage.py shell -c "\
from django.contrib.auth import get_user_model; \
import os; \
User = get_user_model(); \
email = os.environ.get('SUPERUSER_ACCOUNT'); \
password = os.environ.get('SUPERUSER_PASSWORD'); \
assert email and password, 'Missing superuser credentials'; \
User.objects.filter(is_superuser=True).exists() or \
User.objects.create_superuser(email=email, password=password)"


# -----------------------------
#   MIGRATE / DJANGO CMDS
# -----------------------------

migrate:
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml exec web python manage.py migrate

# Usage: make django cmd="showmigrations" ENV=prod
django:
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml exec web python manage.py $(cmd)


# -----------------------------
#   SYSTEM CLEANUP
# -----------------------------
prune:
	docker system prune -af --volumes
	@echo "🧹 Docker system pruned."
