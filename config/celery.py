"""Celery configuration."""

import logging
import os

from celery import Celery

logger = logging.getLogger("config.celery")

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

app = Celery("background_job_tracker")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Self-monitoring / Dogfooding: Initialize Background Job Tracker SDK
bjt_api_key = os.environ.get("BACKGROUND_JOB_TRACKER_API_KEY") or os.environ.get("BJT_SDK_API_KEY")
if bjt_api_key:
    try:
        from background_job_tracker import Tracker
        from background_job_tracker.integrations.celery import CeleryIntegration

        bjt_base_url = os.environ.get("BACKGROUND_JOB_TRACKER_BASE_URL", "http://localhost:8000")
        tracker = Tracker(api_key=bjt_api_key, base_url=bjt_base_url)
        CeleryIntegration(app=app, tracker=tracker)
        logger.info("Successfully initialized Background Job Tracker SDK for self-monitoring.")
    except Exception as exc:
        logger.warning("Failed to initialize Background Job Tracker SDK: %s", exc)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to test Celery is working."""
    print(f"Request: {self.request!r}")

