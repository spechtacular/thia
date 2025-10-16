#!/bin/bash

PROJECT_DIR="/Users/tedspecht/haunt-test/thia"       # e.g. /Users/you/haunt-test/thia
VENV_DIR="${PROJECT_DIR}/.venv"                      # e.g. /Users/you/haunt-test/thia/.venv
MANAGE_PY="${PROJECT_DIR}/manage.py"
LOG_DIR="${PROJECT_DIR}/logs/"                       # create this dir
DJANGO_SETTINGS_MODULE="thia.settings"               # change if needed
# If you use .env, uncomment:
set -a; source "${PROJECT_DIR}/.env"; set +a
 
# Activate virtualenv
source /Users/tedspecht/haunt-test/thia/.venv/bin/activate

# source environment variables
source /Users/tedspecht/haunt-test/thia/.env


# Move to project directory
cd /Users/tedspecht/haunt-test/thia/

# log file 
CMD=$1
LOG_FILE="${LOG_DIR}/${CMD}.log" 

# Activate venv
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"


export DJANGO_SETTINGS_MODULE

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <management_command> [args...]"
  exit 2
fi

CMD="$1"; shift || true
STAMP_UTC="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
LOG_FILE="${LOG_DIR}/${CMD}.log"
LOCK_PATH="${PROJECT_DIR}/.locks/${CMD}.lockdir"

# simple cross-platform lock using mkdir (works on macOS & Linux)
if ! mkdir "$LOCK_PATH" 2>/dev/null; then
  echo "[$STAMP_UTC] ${CMD}: already running; exiting." >> "$LOG_FILE"
  exit 0
fi
trap 'rmdir "$LOCK_PATH"' EXIT

{
  echo "==== [$STAMP_UTC] START ${CMD} $* ===="
  if python "$MANAGE_PY" "$CMD" "$@"; then
    echo "==== [$STAMP_UTC] SUCCESS ${CMD} ===="
  else
    rc=$?
    echo "==== [$STAMP_UTC] FAILED ${CMD} (rc=$rc) ===="
    exit $rc
  fi
} >> "$LOG_FILE" 2>&1


# Run Django command and log output
python manage.py run_selenium_event_participation_query --log DEBUG >> /Users/tedspecht/haunt-test/thia/logs/ivolunteer_users_cron.log 2>&1

