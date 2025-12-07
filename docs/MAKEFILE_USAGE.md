# 📘 Makefile Usage Guide

This file documents the full capabilities of the Makefile used to manage environments, Docker, and Django operations for the `thia` project.

---

## 🔧 Environment Setup

| Target         | Description                                           |
|----------------|-------------------------------------------------------|
| `make load-env`       | Load `.env.build` into current shell            |
| `make check-env`      | Ensure `.env.<ENV>` file exists and is valid   |

---

## 🚀 Docker Compose Commands

| Target                | Description                                      |
|------------------------|--------------------------------------------------|
| `make up`             | Start test environment (`.env.test`)             |
| `make up-env ENV=dev`| Start environment with `.env.dev`                |
| `make up-env-media ENV=dev` | Start dev with mounted media volume      |
| `make down`           | Stop and remove default environment              |
| `make down-env ENV=prod` | Stop specified environment                   |
| `make restart-env ENV=dev` | Restart given environment                 |
| `make restart-env-media ENV=dev` | Restart dev with media prep        |

---

## 🐍 Django Targets

| Target                 | Description                                    |
|------------------------|------------------------------------------------|
| `make init ENV=dev`   | Migrate, collectstatic, create superuser       |
| `make migrate ENV=prod`| Run Django DB migrations                      |
| `make django cmd="..." ENV=env` | Run any Django management command   |

---

## 🛠 Build Commands

| Target            | Description                                        |
|-------------------|----------------------------------------------------|
| `make build ENV=dev` | Build Docker images for specific env            |
| `make buildx`     | Build multi-arch images with `buildx`              |
| `make autotag`    | Auto-generate production image tag                 |
| `make buildx-prod`| Build/push multi-arch prod image with tag          |
| `make login`      | Log into DockerHub (env vars required)            |

---

## 🧹 Cleanup

| Target     | Description                                |
|------------|--------------------------------------------|
| `make prune` | Remove all Docker containers/volumes/images |

---

## 🌍 ENV File Behavior

| Variable          | Description                                     |
|-------------------|-------------------------------------------------|
| `ENV`             | Target environment (e.g., dev, test, prod)      |
| `ENV_FILE`        | Automatically resolved to `.env.$(ENV)`         |

---

## 🏷️ Auto Tagging

When `make buildx-prod` is run, the image is tagged like so:

```
IMAGE=yournamespace:prod-2025.12.04
```

---

## 🔐 DockerHub Login

| Variable              | Description                  |
|------------------------|------------------------------|
| `DOCKERHUB_USERNAME`  | DockerHub account name       |
| `DOCKERHUB_PASSWORD`  | DockerHub account password   |

These must be exported or stored securely before running `make login`.

---

## ✅ Add Help Output

To view Makefile help:

```bash
make help
```

