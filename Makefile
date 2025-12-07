.PHONY: \
  up up-media up-env up-env-media \
  down down-env restart restart-env restart-env-media \
  logs logs-env shell shell-env \
  init migrate django \
  prune build buildx buildx-prod autotag login \
  check-env load-env

# -----------------------------
#   Configuration
# -----------------------------

ENV ?= $(shell grep DEFAULT_ENV .env.build | cut -d '=' -f2)
ENV_FILE := .env.$(ENV)
IMAGE_NAMESPACE ?= $(shell grep IMAGE_NAMESPACE .env.build | cut -d '=' -f2)
IMAGE ?= $(IMAGE_NAMESPACE):$(ENV)-latest

# -----------------------------
#   Environment Utilities
# -----------------------------

load-env:
	@echo "🔧 Loading build env from .env.build..."
	@export $(shell xargs < .env.build)

check-env:
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "❌ Missing environment file: $(ENV_FILE)"; \
		exit 1; \
	fi
	@echo "🔧 Loading environment from $(ENV_FILE)..."
	@set -o allexport; . $(ENV_FILE); set +o allexport

# -----------------------------
#   Core Docker Compose Commands
# -----------------------------

up: check-env
	@echo "🔼 Starting TEST containers (default)..."
	@set -o allexport; . .env.test; set +o allexport; \
	docker-compose up --build -d

up-env: check-env
	@echo "🔼 Starting $(ENV) environment..."
	@set -o allexport; . $(ENV_FILE); set +o allexport; \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml up --build -d

up-env-media: check-env
	@echo "🔼 Preparing media and starting $(ENV) environment..."
	./scripts/prepare_media.sh
	@set -o allexport; . $(ENV_FILE); set +o allexport; \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml -f docker-compose.media.yml up --build -d

down: check-env
	@echo "⛔ Stopping default (test) environment..."
	@set -o allexport; . .env.test; set +o allexport; \
	docker-compose down --volumes --remove-orphans

down-env: check-env
	@echo "⛔ Stopping $(ENV) environment..."
	@set -o allexport; . $(ENV_FILE); set +o allexport; \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml down --volumes --remove-orphans

restart: check-env
	@echo "🔁 Restarting $(ENV) environment..."
	@set -o allexport; . $(ENV_FILE); set +o allexport; \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml down --volumes --remove-orphans && \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml up --build -d

restart-env:
	@echo "🔁 Restarting $(ENV) environment..."
	$(MAKE) down-env ENV=$(ENV)
	$(MAKE) up-env ENV=$(ENV)

restart-env-media: check-env
	@echo "🔁 Restarting $(ENV) environment with media..."
	@set -o allexport; . $(ENV_FILE); set +o allexport; \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml -f docker-compose.media.yml down --volumes --remove-orphans && \
	./scripts/prepare_media.sh && \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml -f docker-compose.media.yml up --build -d

# -----------------------------
#   Logging and Shell Access
# -----------------------------

logs: check-env
	@echo "📜 Logging default environment..."
	@set -o allexport; . .env.test; set +o allexport; \
	docker-compose logs -f

logs-env: check-env
	@echo "📜 Logs for $(ENV) environment..."
	@set -o allexport; . $(ENV_FILE); set +o allexport; \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml logs -f

shell: check-env
	@echo "💻 Shell into default web container..."
	@set -o allexport; . .env.test; set +o allexport; \
	docker-compose exec web /bin/bash

shell-env: check-env
	@echo "💻 Shell into $(ENV) environment web container..."
	@set -o allexport; . $(ENV_FILE); set +o allexport; \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml exec web /bin/bash

# -----------------------------
#   Django Operations
# -----------------------------

init: check-env
	@echo "⚙️ Initializing Django for $(ENV)..."
	@set -o allexport; . $(ENV_FILE); set +o allexport; \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml exec web python manage.py migrate --noinput && \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml exec web python manage.py collectstatic --noinput && \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml exec web python manage.py shell -c "\
from django.contrib.auth import get_user_model; \
import os; \
User = get_user_model(); \
email = os.environ.get('DJANGO_SUPERUSER_EMAIL'); \
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD'); \
assert email and password, 'Missing superuser credentials'; \
User.objects.filter(is_superuser=True).exists() or \
User.objects.create_superuser(email=email, password=password)"

migrate: check-env
	@echo "📦 Running migrations for $(ENV)..."
	@set -o allexport; . $(ENV_FILE); set +o allexport; \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml exec web python manage.py migrate

# Example: make django cmd="run_selenium_users_query" ENV=dev
django: check-env
	@echo "⚙️ Running Django command in $(ENV)..."
	@set -o allexport; . $(ENV_FILE); set +o allexport; \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml exec web python manage.py $(cmd)

# -----------------------------
#   Build / Deploy
# -----------------------------

build: check-env
	@echo "🔨 Building $(ENV) environment images..."
	@set -o allexport; . $(ENV_FILE); set +o allexport; \
	docker-compose -f docker-compose.yml -f docker-compose.$(ENV).yml build

buildx-arm64: load-env
	@echo "🐳 Building ARM64 image: $(IMAGE)"
	docker buildx build \
		--platform linux/arm64 \
		--push \
		-t $(IMAGE) .

buildx-amd64: load-env
	@echo "🐳 Building AMD64 image: $(IMAGE)"
	docker buildx build \
		--platform linux/amd64 \
		--push \
		-t $(IMAGE) .


autotag:
	$(eval DATE_TAG := prod-$(shell date +%Y.%m.%d))
	@echo "🏷️  Generated production tag: $(IMAGE_NAMESPACE):$(DATE_TAG)"


buildx-prod: autotag
	$(eval DATE_TAG := prod-$(shell date +%Y.%m.%d))
	$(eval IMAGE := $(IMAGE_NAMESPACE):$(DATE_TAG))
	@echo "🚀 Building production image with tag: $(IMAGE)"
	docker buildx build \
		--platform linux/amd64,linux/arm64 \
		--push \
		-t $(IMAGE) .

buildx-clean:
	docker buildx prune -f

login: load-env
	@echo "🔐 Logging into Docker Hub..."
	@echo "$${DOCKERHUB_PASSWORD}" | docker login -u "$${DOCKERHUB_USERNAME}" --password-stdin

# -----------------------------
#   Cleanup
# -----------------------------

prune:
	@echo "🧹 Pruning Docker system..."
	docker system prune -af --volumes
