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

Here’s our **comprehensive Makefile + Docker Compose + Django + haunt_ops CLI documentation**, formatted in **Markdown** for direct inclusion in your `README.md`.

---

# 🛠️ Makefile + Docker + Django Command Reference

This project supports environment-specific Docker Compose setups (`dev`, `test`, `prod`) with unified commands through `make`. Use the `ENV` variable to target a specific environment.

---

## 🚀 Startup Commands

### Start Environment

```bash
make up-env ENV=dev
make up-env ENV=test
make up-env ENV=prod
```

### Stop Environment

```bash
make down-env ENV=dev
make down-env ENV=test
make down-env ENV=prod
```

### Restart Environment

```bash
make down-env ENV=dev && make up-env ENV=dev
```

---

## 🪵 Logs & Shell Access

### View Logs

```bash
make logs-env ENV=dev
```

### Open Shell in `web` Container

```bash
make shell-env ENV=dev
```

---

## ⚙️ Initialization

### Initial Setup

This creates the DB schema, collects static files, and optionally creates a superuser.

```bash
make init ENV=dev
make init ENV=test
make init ENV=prod
```

> ⚠️ Set credentials in your `.env.dev`, `.env.test`, or `.env.prod`:
>
> ```env
> DJANGO_SUPERUSER_EMAIL=admin@example.com
> DJANGO_SUPERUSER_PASSWORD=ChangeMeNow
> ```

---

## 🐍 Django Commands

Run any Django command inside the web container:

```bash
make django cmd="createsuperuser" ENV=dev
make django cmd="migrate" ENV=test
make django cmd="shell" ENV=prod
```

Example:

```bash
make django cmd="check" ENV=dev
make django cmd="loaddata fixtures/something.json" ENV=test
```

List all available commands:

```bash
make django cmd="help" ENV=dev
```

---

## 👻 haunt_ops Commands

These are custom Django management commands under `haunt_ops/management/commands`.

### 📥 Bulk Loaders

```bash
make django cmd="bulk_load_events_from_ivolunteer" ENV=dev
make django cmd="bulk_load_users_from_ivolunteer" ENV=dev
make django cmd="bulk_load_groups_from_config" ENV=dev
```

### 🧼 Cleanup & Reset

```bash
make django cmd="clear_haunt_data" ENV=dev
make django cmd="rename_images_to_db_names" ENV=dev
```

### 🕷️ Selenium Queries

```bash
make django cmd="run_selenium_events_query" ENV=dev
make django cmd="run_selenium_users_query" ENV=dev
make django cmd="run_selenium_groups_query" ENV=dev
make django cmd="run_selenium_passage_ticket_sales_query" ENV=dev
make django cmd="run_selenium_update_signin_query" ENV=dev
make django cmd="run_selenium_event_participation_query" ENV=dev
```

### 👤 User Utilities

```bash
make django cmd="update_user_profile_pic" ENV=dev
```

---

## 🧱 Docker Utilities

### Build Containers

```bash
make build
```

### Prune All Docker Data (⚠️ Destructive)

```bash
make prune
```

---

## 📂 Media Preparation

Sync media folders and start the stack:

```bash
make up-media
```

---

## 📦 Environment-Specific `.env` Files

Use per-environment env files to avoid hardcoding secrets.

| File        | Purpose                       |
| ----------- | ----------------------------- |
| `.env`      | Shared defaults               |
| `.env.dev`  | Development-specific settings |
| `.env.test` | Test settings                 |
| `.env.prod` | Production config             |

Your `docker-compose.*.yml` files should include:

```yaml
env_file:
  - .env
  - .env.dev  # or .env.test / .env.prod
```

---

## ⚙️ Django Settings Loader

Make sure your `manage.py`, `wsgi.py`, and `asgi.py` use:

```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"thia.settings.{os.environ.get('DJANGO_ENV', 'dev')}")
```

Then export `DJANGO_ENV` when running:

```bash
export DJANGO_ENV=dev
make up-env ENV=dev
```


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
- [ ]

- [ ] Breakup selenium code and create shared libraries for common functions
- [ ] signup for email/sms provider
- [ ] email API implemented
- [ ] SMS API implemented
- [ ] Add support for multiple environments. At least dev,test, and prod environments.
- [ ] Add Docker support for easier deployment
- [ ] migrate code to Linux mini computer
- [ ] Add Selenium automation to create test events
- [ ] Add automated testing
- [ ] Add CI/CD
- [ ] Add react support
