"""
ASGI config for thia project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from dotenv import load_dotenv

env_name = os.getenv('THIA_ENV', 'dev')
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), f'.env.{env_name}')
load_dotenv(env_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.getenv('DJANGO_SETTINGS_MODULE', 'thia.settings.dev'))


