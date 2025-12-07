# 🎃 The Haunt In Atascadero (thia)

_A Django-powered automation platform for managing volunteer participation, event data, and ticket sales for Haunt events using Selenium, Docker, and multi-environment orchestration._

---

## 🚀 Overview

The `thia` project automates interactions with the [iVolunteer](https://www.ivolunteer.com) and [Passage](https://www.passage.com) platforms to:

- Extract volunteer and event data via Selenium
- Maintain a local PostgreSQL database
- Scrape reports and import XLS/CSV formats
- Manage user profile images and assignments
- Support multi-env (dev, test, prod) Docker deployments

---

## 📁 Project Layout

| Path               | Description                             |
|--------------------|-----------------------------------------|
| `thia/`            | Django project and settings             |
| `haunt_ops/`       | Custom Django management commands       |
| `utils/`           | Helper scripts (e.g., image labeling)   |
| `scripts/`         | Bash automation (e.g., media prep)      |
| `docker/`          | Docker build and override logic         |
| `docs/`            | CLI, Docker, Ansible, and Makefile docs |
| `.env.*`           | Per-environment configuration           |
| `Makefile`         | CLI commands for dev and deployment     |

---

## ⚙️ Setup & Quickstart

1. **Clone the repo**
   ```bash
   git clone https://github.com/YOUR_USERNAME/thia.git
   cd thia
   ```

2. **Copy environment files**
   ```bash
   cp .env.dev.example .env.dev
   cp .env.build.example .env.build
   ```

3. **Start development environment**
   ```bash
   make up-env ENV=dev
   ```

4. **Initialize the database**
   ```bash
   make init ENV=dev
   ```

5. **Shell into the web container (optional)**
   ```bash
   make shell-env ENV=dev
   ```

---

## 🧠 Project Operations

All project commands are wrapped in the `Makefile`, and detailed CLI documentation is broken out into dedicated files for clarity:

| Document | Purpose |
|----------|---------|
| 📘 [CLI Cheatsheet](./docs/CLI_CHEATSHEET.md) — quick reference for all commands |
| 🛠️ [Makefile Usage](./docs/MAKEFILE_USAGE.md) — all Makefile targets explained |
| 🐳 [Docker Usage](./docs/DOCKER_USAGE.md) — builds, tagging, multi-arch support |
| ⚙️ [Ansible Usage](./docs/ANSIBLE_USAGE.md) — provisioning a host with Ansible |

> Use `make help` to print the full list of available CLI options.

---

## 🌍 Environment Configuration

| File           | Purpose |
|----------------|---------|
| `.env.dev`     | Local development settings |
| `.env.test`    | CI or isolated test env    |
| `.env.prod`    | Production environment      |
| `.env.build`   | Docker image config/tagging |

Example ENV usage:

```bash
make up-env ENV=prod
make django cmd="check" ENV=test
```

---

## 🛠 Media Handling

You can mount videos into your local container using:

```bash
make up-env-media ENV=dev
```

This uses:
- `docker-compose.media.yml`
- `scripts/prepare_media.sh`

Symlinked videos are mounted under `/app/media` and served via nginx.

---

## 🧪 Django Management Commands

Custom commands for data ingestion and scraping:

```bash
python manage.py run_selenium_users_query
python manage.py bulk_load_users_from_ivolunteer --csv replaced_users.csv
python manage.py update_user_profile_pic
```

See the full list in the [CLI Cheatsheet](./docs/CLI_CHEATSHEET.md).

---

## 🐳 Docker Builds

Build images for any environment:

```bash
make build ENV=dev
```

Multi-platform (arm64 + amd64) builds:

```bash
make buildx
```

Production tagging:

```bash
make autotag && make buildx-prod
```

See [Docker Usage](./docs/DOCKER_USAGE.md) for full details.

---

## ⚙️ Ansible Deployment

You can provision a new machine using:

```bash
ansible-playbook -i inventory/hosts.ini install_thia_full.yml
```

This will:
- Install Docker, Redis, Python, etc.
- Clone the repo and copy .env files
- Optionally register Django as a systemd service

See [Ansible Usage](./docs/ANSIBLE_USAGE.md) for full details.

---

## ✅ Security Practices

- `.env.dev`, `.env.prod`, `.env.test` are never committed
- Secrets like `THIA_DB_PASSWORD` and `DJANGO_SUPERUSER_PASSWORD` must stay local
- `.env.build` is safe to commit (contains image tags, not secrets)

---

## 🧹 Cleanup & Maintenance

- Remove all Docker images/volumes:
  ```bash
  make prune
  ```

- Tail logs:
  ```bash
  make logs-env ENV=dev
  ```

- Restart everything:
  ```bash
  make restart-env-media ENV=dev
  ```

---

## 📦 Volume & Port Strategy

Each environment maps to its own:

- Docker volume (e.g., `postgres_data_dev`)
- Host port (e.g., `8001`, `8002`, `8003`)
- Docker network (e.g., `thia_net_dev`)

This allows dev, test, and prod to coexist on the same machine.

---

## ✅ Roadmap

- [x] Docker + Makefile + Ansible automation
- [x] Profile picture matching by filename
- [x] Image labeling for volunteers
- [x] CI/CD ready architecture
- [x] Media folder mount support
- [ ] Add user portal
- [ ] Implement mobile-friendly API
- [ ] Add automated tests and coverage
- [ ] Evaluate external email/SMS providers
- [ ] Refactor selenium logic into libraries

---

## 👻 Maintainer

**Ted Specht** — _“Zack the Skeleton”_
📬 [zack@boo.com](mailto:zack@boo.com)

---

> ✨ **Pro tip:** Use `make help` to view all available build, deploy, and debug options.
