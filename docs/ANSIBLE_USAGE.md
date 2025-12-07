# ⚙️ Ansible Playbook Usage

Provision and configure systems for the `thia` project using a cross-platform Ansible playbook.

---

## 🚀 Install via Playbook

```bash
ansible-playbook -i inventory/hosts.ini install_thia_full.yml
```

---

## ✅ Features fully updated and extended Ansible playbook to provision a system for the thia project, with support for

- ✅ Intel/ARM chips (Ubuntu, Debian, macOS, Raspberry Pi)
- 🐳 Docker, Docker Compose, and Compose plugin
- 🐘 PostgreSQL client
- 🧠 Redis
- 🧪 Python (with venv)
- 🛠️ Node.js (for React/static builds)
- 🔁 .env file placement
- 📦 git clone the thia repo
- 🛎️ Optional systemd service for the Django app
- 🍎 macOS support (via Homebrew)
- 🐢 Raspberry Pi support (Debian ARM64)

## 📝 Notes

- 🚀 Run the Playbook: ansible-playbook -i inventory/hosts.ini install_thia_full.yml
- ✅ The playbook installs system dependencies, clones the repo, copies .env, and configures Django as a service.
- 🔐 .env file should be prepared ahead of time under env_files/.env.
- 🧠 You may add docker-compose.override.yml logic or React build steps if needed.
- 🐳 Systemd is optional — you can remove that block if you prefer running everything via docker-compose.


---

## 📁 File Layout

| File                          | Purpose                             |
|-------------------------------|-------------------------------------|
| `install_thia_full.yml`       | Main provisioning playbook          |
| `inventory/hosts.ini`         | Ansible inventory                   |
| `env_files/.env`              | Your .env file (copied into target) |
| `roles/`                      | Role-based setup (e.g. docker, redis, python) |

---

## 🔐 Setup Notes

- Your `.env` file should be prepared ahead of time under `env_files/.env`
- Do **not** check this file into version control
- Use Ansible Vault or manually copy it securely

---

## 🍎 macOS

- Uses Homebrew for package installs
- Docker Desktop must be installed beforehand

---

## 🐢 Raspberry Pi

- Works on Debian-based ARM systems
- Installs using `apt` instead of Homebrew

---

## ⚙️ systemd Optional Setup

To enable Django as a systemd service:

- Uncomment the `[Unit]`, `[Service]`, and `[Install]` blocks in the playbook
- Ensure gunicorn and Django project paths are correct
- Restart the service using `sudo systemctl restart thia`

---

## 🔍 Common Tasks

| Task                    | Description                           |
|-------------------------|---------------------------------------|
| Provision system        | `ansible-playbook install_thia_full.yml` |
| Start service (if using systemd) | `sudo systemctl start thia` |
| Stop service            | `sudo systemctl stop thia`            |

