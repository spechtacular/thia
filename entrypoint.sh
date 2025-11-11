#!/bin/bash

set -e

echo "📦 Waiting for DB to be ready..."
until nc -z db 5432; do
  echo "⏳ Waiting for PostgreSQL..."
  sleep 1
done

echo "🔁 Applying migrations..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo "🎯 Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if it doesn't exist
echo "🔐 Checking for superuser..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model
import os

User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    print("👑 Creating superuser...")
    User.objects.create_superuser(
        email=os.environ["SUPERUSER_ACCOUNT"],
        password=os.environ["SUPERUSER_PASSWORD"]
    )
else:
    print("✅ Superuser already exists.")
EOF

echo "🚀 Starting Gunicorn..."
exec gunicorn thia.wsgi:application --bind 0.0.0.0:8000 --workers 3
