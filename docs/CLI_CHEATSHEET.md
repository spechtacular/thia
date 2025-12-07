# 🧰 CLI Cheatsheet

Quick reference for Docker, Makefile, and Django commands.

---

## ⚙️ Core Make Commands

| Command                           | Description                                 |
|----------------------------------|---------------------------------------------|
| `make up`                        | Start default (test) environment            |
| `make up-env ENV=dev`           | Start a specific environment                |
| `make up-env-media ENV=dev`     | Start env with mounted media                |
| `make down`                     | Stop test containers and remove volumes     |
| `make down-env ENV=prod`        | Stop a specific environment                 |
| `make restart-env ENV=dev`      | Restart a specific environment              |
| `make restart-env-media ENV=dev`| Restart dev + media (re-prepares videos)    |
| `make logs`                     | Tail logs for default environment           |
| `make logs-env ENV=test`        | Tail logs for specific environment          |
| `make shell`                    | Shell into default (test) web container     |
| `make shell-env ENV=prod`       | Shell into specified environment container  |

---

## 🛠️ Build & Docker

| Command                           | Description                                 |
|----------------------------------|---------------------------------------------|
| `make build ENV=dev`            | Build images for given environment          |
| `make buildx`                   | Multi-platform build & push (from .env.build)|
| `make buildx-prod`             | Prod multi-arch build with auto-tagging     |
| `make autotag`                 | Show auto-generated prod tag                |
| `make prune`                   | Delete all Docker containers/images/volumes |
| `docker login`                 | Manually login to Docker Hub                |

---

## 🐍 Django Management

| Command                                       | Description                        |
|----------------------------------------------|------------------------------------|
| `make init ENV=dev`                         | Migrate DB, collectstatic, create superuser |
| `make migrate ENV=prod`                     | Run migrations in selected env     |
| `make django cmd="shell" ENV=dev`           | Open Django shell                  |
| `make django cmd="createsuperuser" ENV=test`| Create a superuser interactively   |
| `make django cmd="run_selenium_users_query -v 3" ENV=dev` | Run a custom Django command |
| `make django cmd="collectstatic --noinput" ENV=prod`      | Collect static files manually     |

---

## 🎥 Media Handling

| Command                                  | Description                        |
|------------------------------------------|------------------------------------|
| `make up-env-media ENV=dev`             | Start environment with media mounted |
| `make restart-env-media ENV=dev`        | Restart and re-copy media          |
| `./scripts/prepare_media.sh`            | Manually resolve & copy media symlinks |

---

## 📦 Environment Files Overview

| File            | Purpose                               |
|------------------|----------------------------------------|
| `.env.dev`       | Dev environment config                |
| `.env.test`      | Test/CI/local config                  |
| `.env.prod`      | Production env vars                   |
| `.env.build`     | Docker build settings & tagging       |

To load any env manually:

```bash
set -o allexport; source .env.dev; set +o allexport
```

---

## 📄 Docker Compose Files

| File                      | Purpose                         |
|---------------------------|----------------------------------|
| `docker-compose.yml`      | Base config shared across envs   |
| `docker-compose.dev.yml`  | Dev-specific overrides           |
| `docker-compose.test.yml` | Test env (CI, isolated setup)    |
| `docker-compose.prod.yml` | Production deployment config     |
| `docker-compose.media.yml`| Optional media mounts (dev only) |

---

## 🔌 Quick Environment Port Reference

| Service | Dev     | Test    | Prod    |
|---------|---------|---------|---------|
| Web     | 8001    | 8002    | 8003    |
| DB      | 6544    | 6545    | 6546    |
| Redis   | 6381    | 6380    | 6379    |
| Nginx   | 8081/4441 | 8082/4442 | 8083/4443 |

