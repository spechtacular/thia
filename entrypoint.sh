#!/bin/sh
set -e

echo "🔁 Running migrations..."
python manage.py migrate --noinput

echo "🧹 Collecting static files..."
python manage.py collectstatic --noinput

echo "🚀 Starting Gunicorn..."
exec gunicorn thia.wsgi:application --bind 0.0.0.0:8000

