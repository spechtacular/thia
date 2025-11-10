#!/bin/bash

set -e

# Run makemigrations only if there are changes
echo "Checking for model changes..."
python manage.py makemigrations --check --dry-run > /dev/null 2>&1

if [ $? -eq 1 ]; then
    echo "🔧 New model changes detected — making migrations..."
    python manage.py makemigrations
else
    echo "✅ No new model changes."
fi

# Always apply migrations (safe to re-run)
echo "🚀 Applying migrations..."
python manage.py migrate --noinput

# Start the server
echo "🔄 Starting Django development server..."
exec gunicorn thia.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120

