#!/bin/bash

# Activate virtualenv
source /Users/tedspecht/haunt-test/thia/.venv/bin/activate

# source environment variables
source /Users/tedspecht/haunt-test/thia/.env


# Move to project directory
cd /Users/tedspecht/haunt-test/thia/

# Run Django command and log output
python manage.py run_selenium_event_participation_query --log DEBUG >> /Users/tedspecht/haunt-test/thia/logs/ivolunteer_users_cron.log 2>&1

