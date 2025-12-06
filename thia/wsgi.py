"""
WSGI config for thia project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
from dotenv import load_dotenv
from django.core.wsgi import get_wsgi_application

# Load environment
# Dynamically pick the .env file based on THIA_ENV
env_name = os.getenv('THIA_ENV', 'dev')  # Default to 'dev'
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), f'.env.{env_name}')
load_dotenv(env_path)

# Set DJANGO_SETTINGS_MODULE from the loaded .env file
os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.getenv('DJANGO_SETTINGS_MODULE', 'thia.settings.dev'))


# ✅ This is what Gunicorn expects to find
application = get_wsgi_application()

