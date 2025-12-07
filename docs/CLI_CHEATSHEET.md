# 🛠️ CLI Cheatsheet

This file documents all available `make` targets for managing the thia project.

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
| Example `make django cmd="bulk_load_events_from_ivolunteer" ENV=dev` | bulk load events from ivolunteer. |
| Example `make django cmd="bulk_load_groups_from_config" ENV=dev` | bulk load groups from ivolunteer. |
| Example `make django cmd="clear_haunt_data" ENV=dev` | clear user data from Postgresql. |
| Example `make django cmd="rename_images_to_db_names" ENV=dev` | rename image file names to match names in db. |
| Example `make django cmd="run_selenium_event_participation_query" ENV=dev` | scrape event participation from ivolunteer db. |
| Example `make django cmd="run_selenium_events_query" ENV=dev` | scrape events from ivolunteer db. |
| Example `make django cmd="run_selenium_groups_query" ENV=dev` | scrape groups from ivolunteer db. |
| Example `make django cmd="run_selenium_passage_ticket_sales_query" ENV=dev` | scrape ticket sales data from gopassage db. |
| Example `make django cmd="run_selenium_update_signin_query" ENV=dev` | test ivolunteer login. |
| Example `make django cmd="run_selenium_users_query" ENV=dev` | scrape user data from ivolunteer db. |
| Example `make django cmd="update_user_profile_pic" ENV=dev` | update user profile with user pic file name. |

|----------------------------------------------------|------------------------------------------------------|

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
| `make buildx`            | Deprecated in favor of platform-specific variants.           |
| `make buildx-arm64`      | Build and push image for ARM64 platform.                     |
| `make buildx-amd64`      | Build and push image for AMD64 platform.                     |
| `make buildx-prod`       | Build and push multi-platform production image with autotag. |
| `make buildx-clean`      | Clean up old Buildx cache and intermediate images.           |
| `make autotag`           | Generate image tag using current date (e.g., `prod-2025.12.04`). |
| `make login`             | Log into Docker Hub using credentials from `.env.build`.     |

---

## 🧹 Cleanup

| Command   | Description                                                                 |
|-----------|-----------------------------------------------------------------------------|
| `make prune` | Force prune Docker system (containers, images, volumes).               |
| `make clean` | DANGER: Stops and removes **all** containers, volumes, and networks for all environments. Prompts for confirmation. |

---

## 🌍 ENV Usage Pattern

Specify the target environment in most commands using `ENV`:

```bash
make up-env ENV=dev
make shell-env ENV=test
make migrate ENV=prod
make django cmd="run_selenium_users_query" ENV=dev
