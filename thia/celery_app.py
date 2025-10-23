import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thia.settings")

# Create Celery application
app = Celery("thia")

# Load settings from Django settings.py using CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")

# Optional: Example of a periodic task schedule (Celery Beat)
app.conf.beat_schedule = {
    "daily-cleanup-task": {
        "task": "haunt_ops.tasks.cleanup_old_sessions",
        "schedule": crontab(hour=3, minute=0),  # 3:00 AM daily
    },
}

