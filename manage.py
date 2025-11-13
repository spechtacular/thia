#!/usr/bin/env python
"""
    Django's command-line utility for administrative tasks.
"""
import os
import sys
from dotenv import load_dotenv


# Default to .env.dev if no ENV is set
env_name = os.getenv('THIA_ENV', 'dev')
env_path = os.path.join(os.path.dirname(__file__), f'.env.{env_name}')
load_dotenv(env_path)


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.environ.get("DJANGO_SETTINGS_MODULE", "thia.settings.dev"))
    #os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.environ.get("DJANGO_SETTINGS_MODULE", "thia.settings.prod"))
    #os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.environ.get("DJANGO_SETTINGS_MODULE", "thia.settings.test"))

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
