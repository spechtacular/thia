# 🛠️ Makefile Usage

This document explains how to use all available `make` targets to build, deploy, and manage the `thia` project across different environments.

---

## 📚 Table of Contents

- [⚙️ Core Docker Compose Commands](#️-core-docker-compose-commands)
- [📜 Logging and Shell Access](#-logging-and-shell-access)
- [🐍 Django Operations](#-django-operations)
- [🔧 Environment Management](#-environment-management)
- [🏗️ Build & Deployment](#️-build--deployment)
- [🧹 Cleanup](#-cleanup)
- [🌍 ENV Usage Pattern](#-env-usage-pattern)

---

## ⚙️ Core Docker Compose Commands

| Command                 | Description                                                       |
|------------------------|-------------------------------------------------------------------|
| `make up`              | Start default (test) environment containers.                      |
| `make up-env ENV=dev`  | Start specified environment containers.                           |
| `make up-env-media ENV=dev` | Start environment and mount media folders (uses media compose file). |
| `make down`            | Stop and remove default (test) environment.                       |
| `make down-env ENV=dev`| Stop and remove specified environment.                            |
| `make restart ENV=dev` | Restart the given environment using full down + up.              |
| `make restart-env ENV=dev` | Stop and restart specified environment.                         |
| `make restart-env-media ENV=dev` | Restart environment and re-prepare media.                |

---

## 📜 Logging and Shell Access

| Command                        | Description                                            |
|-------------------------------|--------------------------------------------------------|
| `make logs`                   | Tail logs for default environment.                     |
| `make logs-env ENV=prod`      | Tail logs for specific environment.                    |
| `make shell`                  | Open shell in default web container.                   |
| `make shell-env ENV=dev`      | Open shell in web container for specific environment.  |

---

## 🐍 Django Operations

| Command                                             | Description                                          |
|----------------------------------------------------|------------------------------------------------------|
| `make init ENV=dev`                                | Run migrations, collectstatic, and create superuser. |
| `make migrate ENV=prod`                            | Apply migrations to specified environment.           |
| `make django cmd="..." ENV=dev`                    | Run arbitrary Django management command.             |
| Example: `make django cmd="check" ENV=dev`         | Runs `python manage.py check` inside container.      |
| Example: `make django cmd="run_selenium_users_query" ENV=dev` | Custom Selenium scraping logic.            |

---

## 🔧 Environment Management

| Command         | Description                                                  |
|----------------|--------------------------------------------------------------|
| `make check-env` | Check for the existence of the appropriate `.env` file.     |
| `make load-env`  | Load variables from `.env.build` into the current shell.    |

---

## 🏗️ Build & Deployment

| Command                  | Description                                                  |
|--------------------------|--------------------------------------------------------------|
| `make build ENV=dev`     | Build Docker images for the given environment.               |
| `make buildx`            | *(Deprecated)* Use platform-specific build targets below.    |
| `make buildx-arm64`      | Build and push image for ARM64 platform.                     |
| `make buildx-amd64`      | Build and push image for AMD64 platform.                     |
| `make buildx-prod`       | Build and push multi-platform production image with autotag. |
| `make buildx-clean`      | Clean up Buildx builder cache and intermediate images.       |
| `make autotag`           | Generate image tag using current date (e.g., `prod-2025.12.04`). |
| `make login`             | Log into Docker Hub using credentials from `.env.build`.     |

---

## 🧹 Cleanup

| Command   | Description                                                                 |
|-----------|-----------------------------------------------------------------------------|
| `make prune` | Force prune Docker system (containers, images, volumes).               |
| `make clean` | ⚠️ DANGER: Stops and removes **all** containers, volumes, and networks for all environments. Prompts for confirmation. |

---

## 🌍 ENV Usage Pattern

Most commands support passing the `ENV` variable to target a specific environment.

```bash
make up-env ENV=dev
make shell-env ENV=test
make migrate ENV=prod
make django cmd="run_selenium_users_query" ENV=dev
