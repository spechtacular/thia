#!/bin/bash
# Run a Django management command in the correct virtualenv
# Works on both macOS and Debian

set -euo pipefail

# Detect platform
if [[ "$(uname)" == "Darwin" ]]; then
    PROJECT_DIR="/Users/tedspecht/haunt-test/thia"
else
    PROJECT_DIR="/home/zack/scareware/thia"
fi

VENV_DIR="$PROJECT_DIR/.venv"
ENV_FILE="$PROJECT_DIR/.env"
LOG_DIR="$PROJECT_DIR/logs"
DJANGO_CMD="python manage.py"

mkdir -p "$LOG_DIR"

# Activate the virtual environment
source "$VENV_DIR/bin/activate"

# --- Load environment variables from .env safely ---
if [[ -f "$ENV_FILE" ]]; then
    set -a                   # export all sourced vars automatically
    source "$ENV_FILE"
    set +a
else
    echo "[$(date)] ⚠️  Warning: .env file not found at $ENV_FILE" >> "$LOG_DIR/cron_django.log"
fi

# Move to project directory
cd "$PROJECT_DIR"

# --- List of Django management commands to run ---
COMMANDS=(
  "run_selenium_users_query"
  "run_selenium_event_participation_query"
  "run_selenium_passage_ticket_sales_query"
)


# --- Loop and execute each command sequentially ---
for cmd in "${COMMANDS[@]}"; do
    echo "[$(date)] ▶️  Running: $DJANGO_CMD $cmd" >> "$LOG_DIR/cron_django.log"
    if $DJANGO_CMD $cmd >> "$LOG_DIR/cron_django.log" 2>&1; then
        echo "[$(date)] ✅ Finished: $cmd" >> "$LOG_DIR/cron_django.log"
    else
        echo "[$(date)] ❌ Failed: $cmd" >> "$LOG_DIR/cron_django.log"
    fi
    echo "------------------------------------------------------" >> "$LOG_DIR/cron_django.log"
done

