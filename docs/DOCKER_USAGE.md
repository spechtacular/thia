# 🐳 Docker Usage Guide for the `thia` Project

This guide provides detailed documentation on how Docker and Docker Compose are used in the `thia` project, including image building, environment-specific configuration, multi-arch builds, and media volume handling.

---

## 📦 Docker Architecture

The `thia` project uses a layered Docker Compose setup with multiple `.env` and `docker-compose.*.yml` files to support:

- Isolated dev, test, and prod environments
- Multi-platform builds (x86_64 and ARM64)
- Optional media volume support
- Network isolation per environment
- Fast rebuilds using BuildKit

---

## 📁 Docker-Related Files Overview

| File                         | Purpose                                         |
|------------------------------|-------------------------------------------------|
| `Dockerfile`                | Base image for Django app, Python + Chromium    |
| `.env.dev` / `.env.test` / `.env.prod` | Env-specific variables                  |
| `.env.build`                | Variables used for image tagging/builds         |
| `docker-compose.yml`        | Base services shared across all environments     |
| `docker-compose.dev.yml`    | Dev-specific overrides                          |
| `docker-compose.test.yml`   | Test/CI setup                                   |
| `docker-compose.prod.yml`   | Production services + optimizations             |
| `docker-compose.media.yml`  | Mounts local media files (dev only)             |
| `scripts/prepare_media.sh`  | Resolves symlinks for media video copying       |

---

## 🔧 Local Docker Development

### ✅ Start Dev Environment

```bash
make up-env ENV=dev
```

Includes:
- Django app
- PostgreSQL
- Redis
- Nginx
- Volume bindings for local dev (`.env.dev`)

---

### 🧪 Start Test Environment

```bash
make up-env ENV=test
```

For CI or isolated testing. Avoids polluting local volumes.

---

### 🎥 Start Dev with Media Mounted

```bash
make up-env-media ENV=dev
```

Mounts your local `docker_media/videos` into the container, used for:
- Image previews
- Event replays
- Profile pic labeling

Ensure you run:

```bash
./scripts/prepare_media.sh
```

To convert symlinks into usable folders before starting containers.

---

## 🔁 Restarting Containers

```bash
make restart-env ENV=prod
```

or, to include media volumes:

```bash
make restart-env-media ENV=dev
```

These commands stop and rebuild the entire stack with fresh mounts.

---

## 🐳 Docker Compose Internals

Each environment uses different files and port bindings:

| Env   | Compose Files Used                                      |
|-------|----------------------------------------------------------|
| dev   | `docker-compose.yml + docker-compose.dev.yml`           |
| test  | `docker-compose.yml + docker-compose.test.yml`          |
| prod  | `docker-compose.yml + docker-compose.prod.yml`          |
| media | Add `docker-compose.media.yml` as a third override layer|

---

## 🛠 Building Images

### 🔨 Local Build (for a specific env)

```bash
make build ENV=dev
```

### 🐳 Multi-Platform Build & Push

```bash
make buildx
```

Uses platforms:
- `linux/amd64`
- `linux/arm64`

Pushes to DockerHub using the namespace and tag from `.env.build`.

---

## 🏷️ Production Auto-Tagging

Build and push production image with auto-generated tag (e.g., `prod-2025.12.04`):

```bash
make buildx-prod
```

Set your namespace in `.env.build`:

```env
IMAGE_NAMESPACE=spechtacular/thia
```

This results in a tag like:

```bash
spechtacular/thia:prod-2025.12.04
```

---

## 🔐 DockerHub Login

To push to DockerHub, log in using:

```bash
make login
```

This reads credentials from `.env.build`:

```env
DOCKERHUB_USERNAME=youruser
DOCKERHUB_PASSWORD=yourpassword
```

---

## 📦 Volumes Summary

| Volume Name         | Purpose                                  |
|---------------------|-------------------------------------------|
| `postgres_data_dev` | Persistent DB for dev                     |
| `postgres_data_test`| Isolated DB for testing                   |
| `static_volume_dev` | Collected static files (dev env)          |
| `media_volume`      | Shared media folder with web/nginx        |
| `docker_media/videos`| Local media mount (symlink resolved)     |

---

## 🌐 Ports Summary (Per Environment)

| Service | Dev     | Test    | Prod    |
|---------|---------|---------|---------|
| Web     | 8001    | 8002    | 8003    |
| DB      | 6544    | 6545    | 6546    |
| Redis   | 6381    | 6380    | 6379    |
| Nginx   | 8081/4441 | 8082/4442 | 8083/4443 |

---

## 🧠 Best Practices

- ✅ **Use separate `.env` files** for each environment
- ✅ **Don’t commit `.env.prod` or secrets**
- ✅ **Commit `.env.build`** to share image/tag structure
- ✅ **Always run `prepare_media.sh`** before using `media` services
- ✅ **Use multi-platform build (`buildx`)** for cross-arch deployments (Intel/ARM)

---

## 🧪 Troubleshooting

### 🔍 BuildKit / buildx errors

Make sure you are using a valid builder instance:

```bash
docker buildx ls
```

If needed:

```bash
docker buildx use default
docker buildx inspect --bootstrap
```

### 🧼 Clean All Docker Resources

```bash
make prune
```

This will remove:
- Containers
- Images
- Volumes
- Networks

---

## 📚 See Also

- [`CLI_CHEATSHEET.md`](./CLI_CHEATSHEET.md)
- [`MAKEFILE_USAGE.md`](./MAKEFILE_USAGE.md)
- [`ANSIBLE_USAGE.md`](./ANSIBLE_USAGE.md)

