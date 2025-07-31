"""
This file contains the configuration for the HauntOps application.
It defines the default auto field type and the name of the application."""
from django.apps import AppConfig


class HauntOpsConfig(AppConfig):
    """
    Configuration class for the HauntOps application.   
    It sets the default auto field type and the name of the application.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'haunt_ops'
