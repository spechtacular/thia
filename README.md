# The Haunt In Atascadero (thia) Test Project

- Secret project values are stored in a **.env** file in the project root directory, this file is not in the repo for security reasons.
- **requirements.txt** : file contains the pip modules to be installed for the Django  project.
- **.venv folder contains python configuration, it is created by the script **setup_venv.py**.
- **setup_venv.py** : script will create a local file named **.venv** in the project root directory to be used for a local development environment.
- This is the sequence of events used to clear and reload the local Django postgresql database. An internet connection is required to connect to the ivolunteer website.
   1. **clear_haunt_data.py** clears all project tables except for admin and test accounts, there is a --dry-run option to run the script without deleting any project data from postgresql.
      1. python manage.py clear_haunt_data
   2. After clearing the local project database a Django admin account must be created. This account is required to run the Django project base commands:
      1. In the project root directory type "python manage.py createsuperuser"
      2. We use the DJANGO_SUPERUSER_EMAIL name in .env  as the username along with the password is stored in the .env file as DJANGO_SUPERUSER_PASSWORD.
   3. User and Event Data must be queried from ivolunteer site and store in the local postgresql database tables.
      1. **run_selenium_groups_query.py** : this loads group labels from a project config file instead of scraping the iVolunteer web page. There are options to use a custom configuration file and a dry-run.
         1. python manage.py run_selenium_groups_query
      2. **run_selenium_events_query.py** : scrapes all iVolunteer event labels and stores them in the postgresql events table.
         1. python manage.py run_selenium_events_query
      3. **run_selenium_users_query.py** : runs the iVolunteer DB users XLS formatted report.
         1. python manage.py run_selenium_users_query
      4. **bulk_load_users_from_ivolunteer.py** : inserts report data from the converted csv file into the postgresql app_user table.
         1. python manage.py bulk_load_users_from_ivolunteer --csv replaced_users.csv
      5. **update_user_profile_pic.py** : matches volunteer images to database users and create the users profile image url. This script only processes one user at a time, it is faster to create a bash script using this Django script to load multiple image links.
         1. All of the user image files must follow these requirements:
            1. The image file name should be in the following format "first_last_pic.ext"
            2. There must be an underscore between the first and last name.
            3. there must be an underscore after the last name before the word pic.
            4. The first name and last name must match the names used in the database, some people give formal first names etc.
            5. The file extension must be png, jpg, or jpeg.
         2. The script to label the user images is in the utils folder:
            1. **label_people_pics.py** adds the name used int he image file name to the actual image.
      6. **run_selenium_event_participation_query.py** : runs the event participation iVoulnteer database report.
         1. python manage.py run_selenium_event_participation_query
      7. **bulk_load_events_from_ivolunteer.py** : inserts new report data from the converted csv report file into the postgresql event_volunteers table.
         1. python manage.py bulk_load_events_from_ivolunteer --csv path/to/users.csv
      8. **run_selenium_passage_ticket_sales_query.py : runs the ticket sales report on the Passage web site.
         1. python manage.py run_selenium_passage_ticket_sales_query --headed
- This is the sequence used to update the existing Django postgresql database contents. An internet connection is required to connect to the ivolunteer website.
   1. **run_selenium_users_query.py** : runs the iVolunteer DB users XLS formatted report.
      1. python manage.py run_selenium_users_query
   2. **bulk_load_users_from_ivolunteer.py** : inserts or updates new report data from the converted csv file into the postgresql app_user table.
      1. python manage.py bulk_load_users_from_ivolunteer --csv path/to/users.csv
   3. **update_user_profile_pic.py** : matches volunteer images to database users and create the users profile image url. This script only processes one user at a time, it is faster to create a bash script using this Django script to load multiple image links.
         1. All of the user image files must follow these requirements:
            1. The image file name should be in the following format "first_last_pic.ext"
            2. There must be an underscore between the first and last name.
            3. there must be an underscore after the last name before the word pic.
            4. The first name and last name must match the names used in the database, some people give formal first names etc.
            5. The file extension must be png, jpg, or jpeg.
         2. The script to label the user images is in the utils folder:
            1. **label_people_pics.py** adds the name used int he image file name to the actual image.
   4. **run_selenium_event_participation_query.py** : runs the event participation iVoulnteer database report.
      1. python manage.py run_selenium_event_participation_query
   5. **bulk_load_events_from_ivolunteer.py** : inserts or updates new report data from the converted csv report file into the postgresql event_volunteers table.
      1. python manage.py bulk_load_events_from_ivolunteer --csv path/to/replaced_users.csv

🛠️ Makefile Commands

The following commands are available via the Makefile to manage environments, Docker, and Django inside the project.

🔧 Environment Utilities
Command Description
make help Show this help message
make load-env Load .env.build into shell for Docker builds
make check-env Validate and load .env.`ENV` environment file

🐳 Docker Compose
Command Description
make up Start default (test) environment
make up-env Start specified environment (e.g. ENV=dev)
make up-env-media Start environment with media volumes
make down Stop and remove default environment
make down-env Stop and remove specified environment
make restart Full restart of specified environment
make restart-env Restart specified environment (simplified)
make restart-env-media Restart environment with media volume

📜 Logging & Shell Access
Command Description
make logs Tail logs for default (test) environment
make logs-env Tail logs for specified environment
make shell Shell into default web container
make shell-env Shell into specified environment's web container
⚙️ Django Management
Command Description
make init Run migrations, collectstatic, and create superuser
make migrate Run Django migrations in specified environment
make django cmd=... Run arbitrary Django command (e.g. cmd="check")
🏗️ Build & Deployment
Command Description
make build Build Docker images for specified environment
make buildx Multi-platform build and push via Docker Buildx
make autotag Auto-generate production tag based on current date
make buildx-prod Build and push production image with generated tag
make login Log into Docker Hub using credentials in .env.build
🧹 Cleanup
Command Description
make prune Clean all Docker resources and volumes
🌍 Environment Control

Use the ENV variable to specify which environment to target:

make up-env ENV=dev
make shell-env ENV=prod
make django cmd="check" ENV=dev

## 📦 Environment-Specific `.env*` Files

Use per-environment env files to avoid hardcoding secrets.

| File        | Purpose                       |
| ----------- | ----------------------------- |
| `.env`      | Shared defaults               |
| `.env.dev`  | Development-specific settings |
| `.env.test` | Test settings                 |
| `.env.prod` | Production config             |

📄 .env.* Environment Files

Each environment (e.g., dev, test, prod) has its own .env file that defines critical environment-specific settings. These files are automatically loaded based on the ENV value passed to make.

🧪 Example Files

.env.dev

.env.test

.env.prod

.env.build (used only for Docker builds and tagging)

🔐 Common Variables in .env.dev, .env.test, .env.prod
Variable Description
THIA_ENV Name of the current environment (dev, test, prod)
DEBUG Django debug flag (True or False)
DJANGO_SETTINGS_MODULE Python path to Django settings module
GUNICORN_WORKERS Number of Gunicorn workers
POSTGRES_DB Name of the PostgreSQL database
POSTGRES_USER PostgreSQL username
THIA_DB_PASSWORD PostgreSQL password (should not be checked into Git)
POSTGRES_HOST Host address (commonly 127.0.0.1 or container name)
POSTGRES_PORT Host port PostgreSQL maps to (must be unique per env)
REDIS_PORT Redis container port (must be unique per env)
WEB_PORT Django app port exposed on the host (e.g., 8001)
NGINX_HTTP_PORT Nginx HTTP port on the host
NGINX_HTTPS_PORT Nginx HTTPS port on the host
DB_VOLUME Docker volume name for PostgreSQL data persistence
STATIC_VOLUME Docker volume name for collected static files
ENV_FILE Filename of the env file (e.g., .env.dev)
NETWORK_NAME Docker network name specific to the environment
PGDATA_DIR Local path for persistent Postgres data
DJANGO_SUPERUSER_EMAIL Superuser email for automatic creation
DJANGO_SUPERUSER_PASSWORD Superuser password

🔧 Variables in .env.build

This file is used for Docker multi-platform builds and contains:

Variable Description
DEFAULT_ENV Default environment used for builds (e.g., prod)
IMAGE_NAMESPACE Docker image name or namespace (e.g., user/app)
IMAGE Full image tag (e.g., user/app:prod-latest)

✅ .env.build can be committed to Git, but do not commit .env.prod or sensitive .env files.

🐳 Docker Compose Configuration Files

These YAML files orchestrate different environments with isolated containers, ports, volumes, and networks.

🧱 Base Compose File: docker-compose.yml

Contains shared service definitions (e.g., web, db, redis, celery, nginx)

Used across all environments

Defines general defaults like ports, dependencies, volumes, and networks

Includes the entrypoint.sh script for bootstrapping migrations and static files

🧪 docker-compose.dev.yml

Overrides base config for development

Custom containers: web_dev, nginx_dev, etc.

Custom host ports to avoid conflicts

Mounts project code directly (for hot reloading if needed)

Binds PostgreSQL data volume to $(PGDATA_DIR)

ports:

- "8001:8000"  # Django
- "8081:80"    # Nginx HTTP
- "4441:443"   # Nginx HTTPS

🧪 docker-compose.test.yml

Used for local or CI testing

Uses isolated volume postgres_data_test

Binds Redis to a unique host port (e.g., 6380)

Custom host ports for web and nginx

🚀 docker-compose.prod.yml

Used for production-like deployments

Uses different port bindings (e.g., 8003, 8083, etc.)

Production-ready container separation

Should use Docker volumes for persistent PostgreSQL data

🎥 docker-compose.media.yml

Optional layer that mounts large local media folders into web and nginx

Used only with development environments

Requires prepare_media.sh to resolve symlinks into ./docker_media/videos

Example usage:

make up-env-media ENV=dev

🧠 Compose Strategy

You can run multiple environments on the same machine (MacBook, dev host) because:

All services are namespaced by container name or network

Host ports are unique across environments

Separate Docker networks are defined per environment (e.g. thia_net_dev, thia_net_test)

📁 Compose Volume Summary

## Volume Name Purpose

- postgres_data_dev Persistent Postgres data (dev env)
- postgres_data_test Isolated Postgres data (test env)
- static_volume_dev Collected static files (dev env)
- media_volume Media folder shared with web/nginx
- docker_media/videos are Symlink-resolved media from scp source

---
📘 See the full [CLI Cheatsheet](./docs/CLI_CHEATSHEET.md) for all make, Docker, and Django commands.

---

## fully updated and extended Ansible playbook to provision a system for the thia project, with support for

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

## Roadmap / TODO

- [x] remove duplicate profile_view page in views.py
- [x] format logout, login, reset_password pages
- [x] Resolve Django makemigration issues
- [x] Implement list volunteers by event
- [x] Implement list volunteers by group
- [x] Add Safety Training checkbox
- [x] Add actor costume_size field
- [x] Add room_actor_training checkbox
- [x] Add line_actor_training checkbox
- [x] Add user profile image upload to profile page
- [x] Verify the date_of_birth field is valid before conversion in bulk loader scripts
- [x] Add individual checkin fields to event_volunteers page
- [x] rendered Date formats are inconsistent, event_date differs from date_of_birth
- [x] event_volunteer_id is used in link from event_volunteers_list page to event_prep page.
- [x] fix event-volunteers page display of volunteer data
- [x] fix tickets_purchased updates
- [ ] Add support for media file access
- [x] write scripts to modify camera video as needed
- [ ] Add separate portal for user access
- [ ] Implement an API for mobile apps or customers to download data.
- [ ] Evaluate meetup for code reuse in the ScareWare app
- [ ] Evaluate email service providers and determine if we want to self host or pay for a provider.
- [ ] Breakup selenium code and create shared libraries for common functions
- [ ] signup for email/sms provider
- [ ] email API implemented
- [ ] SMS API implemented
- [ ] Add support for multiple environments. At least dev,test, and prod environments.
- [ ] Add Docker support for easier deployment
- [ ] Use Makefile to start docker-compose tasks for multiple environments.
- [ ] migrate code to Linux mini computer
- [ ] Add ansible playbook to automate deployment of the project.
- [ ] Add Selenium automation to create test events
- [ ] Add automated testing
- [ ] Add CI/CD
- [ ] Add react support
