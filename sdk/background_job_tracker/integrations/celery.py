"""
Celery Integration for Background Job Tracker SDK.

This module provides signal handlers that automatically capture the lifecycle
of Celery tasks (prerun, success, failure, retry, revoked) and transmit telemetry
to the Background Job Tracker SaaS backend.
"""

import time
import socket
import logging
import uuid
from datetime import datetime, UTC

from celery.signals import (
    task_prerun,
    task_postrun,
    task_success,
    task_failure,
    task_retry,
    task_revoked,
    worker_ready,
)

logger = logging.getLogger("background_job_tracker.celery")


class CeleryIntegration:
    """
    Integrates with Celery using signal connections to capture job executions.

    This class automatically discovers tasks when a Celery worker starts up
    and registers signal handlers for the task execution lifecycle.
    """

    def __init__(self, app, tracker):
        """
        Initialize the Celery integration.

        Args:
            app (celery.Celery): The Celery application instance.
            tracker (Tracker): The Background Job Tracker client instance.
        """
        self.app = app
        self.tracker = tracker
        self._connected = False
        self.connect_signals()

    def connect_signals(self):
        """
        Connect to Celery signals idempotently.

        The dispatch_uid prevents duplicate signal connections if this method
        is called multiple times.
        """
        if self._connected:
            return

        # Ensure idempotent registration using dispatch_uid
        task_prerun.connect(self.on_task_prerun, weak=False, dispatch_uid="bjt_task_prerun")
        task_postrun.connect(self.on_task_postrun, weak=False, dispatch_uid="bjt_task_postrun")
        task_success.connect(self.on_task_success, weak=False, dispatch_uid="bjt_task_success")
        task_failure.connect(self.on_task_failure, weak=False, dispatch_uid="bjt_task_failure")
        task_retry.connect(self.on_task_retry, weak=False, dispatch_uid="bjt_task_retry")
        task_revoked.connect(self.on_task_revoked, weak=False, dispatch_uid="bjt_task_revoked")
        worker_ready.connect(self.on_worker_ready, weak=False, dispatch_uid="bjt_worker_ready")

        self._connected = True

    def _extract_request(self, sender, kwargs):
        """
        Extract the Celery request context from signal kwargs.
        """
        task = kwargs.get("task") or sender
        if hasattr(task, "request") and getattr(task.request, "id", None):
            return task.request

        request = kwargs.get("request")
        if request and getattr(request, "id", None):
            return request

        return None

    def _extract_task_name(self, sender, kwargs):
        """
        Extract the task name (identifier) from signal kwargs.
        """
        task = kwargs.get("task") or sender
        if hasattr(task, "name"):
            return task.name

        request = kwargs.get("request")
        if request and getattr(request, "task", None):
            return request.task

        return "unknown"

    def _get_worker_name(self, request=None):
        """
        Determine the worker node executing the task.
        """
        if request and getattr(request, "hostname", None):
            return request.hostname
        return socket.gethostname()

    def _get_queue_name(self, request):
        """
        Determine the queue routing key from the task request.
        """
        if request and getattr(request, "delivery_info", None):
            return request.delivery_info.get("routing_key", "")
        return ""

    def _build_base_event(self, request, task_name):
        """
        Build the foundational telemetry payload shared by all task events.
        """
        now_utc = datetime.now(UTC)
        return {
            "event_id": uuid.uuid4().hex,
            "external_id": request.id,
            "task_identifier": task_name,
            "event_timestamp": now_utc.isoformat(),
            "worker": self._get_worker_name(request),
            "queue": self._get_queue_name(request),
            "retry_count": getattr(request, "retries", 0),
        }

    def _add_duration(self, event, request):
        """
        Calculate the local execution duration since task_prerun.
        """
        if hasattr(request, "bjt_started_at"):
            duration_ms = int((time.monotonic() - request.bjt_started_at) * 1000)
            event["duration_ms"] = max(0, duration_ms)

        if hasattr(request, "bjt_started_at_iso"):
            event["started_at"] = request.bjt_started_at_iso

        event["finished_at"] = event["event_timestamp"]

    def on_task_prerun(self, sender=None, **kwargs):
        """
        Celery signal handler for when a task is about to begin execution.
        """
        try:
            request = self._extract_request(sender, kwargs)
            if not request:
                return

            task_name = self._extract_task_name(sender, kwargs)

            # Local monotonic time for precision duration
            request.bjt_started_at = time.monotonic()

            event = self._build_base_event(request, task_name)
            event["status"] = "running"
            event["started_at"] = event["event_timestamp"]

            # Keep track of the absolute start time to attach it to terminal events
            request.bjt_started_at_iso = event["started_at"]

            self.tracker.enqueue_event(event)
        except Exception as e:
            logger.error(f"Error in Celery on_task_prerun telemetry: {e}")

    def on_task_success(self, sender=None, **kwargs):
        """
        Celery signal handler for when a task successfully completes.
        """
        try:
            request = self._extract_request(sender, kwargs)
            if not request:
                return

            task_name = self._extract_task_name(sender, kwargs)
            event = self._build_base_event(request, task_name)
            event["status"] = "success"

            self._add_duration(event, request)

            self.tracker.enqueue_event(event)
        except Exception as e:
            logger.error(f"Error in Celery on_task_success telemetry: {e}")

    def on_task_failure(self, sender=None, **kwargs):
        """
        Celery signal handler for when a task raises an unhandled exception.
        """
        try:
            request = self._extract_request(sender, kwargs)
            if not request:
                return

            task_name = self._extract_task_name(sender, kwargs)
            event = self._build_base_event(request, task_name)
            event["status"] = "failed"

            einfo = kwargs.get("einfo")
            if einfo:
                event["error_type"] = type(einfo.exception).__name__ if einfo.exception else ""
                event["error_message"] = str(einfo.exception) if einfo.exception else ""
                event["traceback"] = einfo.traceback or ""

            self._add_duration(event, request)

            self.tracker.enqueue_event(event)
        except Exception as e:
            logger.error(f"Error in Celery on_task_failure telemetry: {e}")

    def on_task_retry(self, sender=None, **kwargs):
        """
        Celery signal handler for when a task explicitly schedules a retry.
        """
        try:
            request = self._extract_request(sender, kwargs)
            if not request:
                return

            task_name = self._extract_task_name(sender, kwargs)
            event = self._build_base_event(request, task_name)
            event["status"] = "retry"

            einfo = kwargs.get("einfo")
            if einfo:
                event["error_type"] = type(einfo.exception).__name__ if einfo.exception else ""
                event["error_message"] = str(einfo.exception) if einfo.exception else ""
                event["traceback"] = einfo.traceback or ""

            self._add_duration(event, request)

            self.tracker.enqueue_event(event)
        except Exception as e:
            logger.error(f"Error in Celery on_task_retry telemetry: {e}")

    def on_task_revoked(self, sender=None, **kwargs):
        """
        Celery signal handler for when a task is revoked (cancelled) before or during execution.
        """
        try:
            request = self._extract_request(sender, kwargs)
            if not request:
                return

            task_name = self._extract_task_name(sender, kwargs)
            event = self._build_base_event(request, task_name)
            event["status"] = "cancelled"

            self._add_duration(event, request)

            self.tracker.enqueue_event(event)
        except Exception as e:
            logger.error(f"Error in Celery on_task_revoked telemetry: {e}")

    def on_task_postrun(self, sender=None, **kwargs):
        """
        Celery signal handler that fires after a task completes (regardless of success/failure).
        Used here to clean up injected timing variables.
        """
        try:
            request = self._extract_request(sender, kwargs)
            if request and hasattr(request, "bjt_started_at"):
                delattr(request, "bjt_started_at")
        except Exception:
            pass

    def _get_filtered_tasks(self):
        """
        Return all application tasks, filtering out built-in Celery framework tasks.
        """
        if not self.app:
            return []

        tasks = []
        for task_name in self.app.tasks:
            if not task_name.startswith("celery."):
                tasks.append(task_name)
        return tasks

    def on_worker_ready(self, sender=None, **kwargs):
        """
        Celery signal handler that fires once the worker is fully initialized.
        Initiates the first batch of task discovery and registers the periodic sync callback.
        """
        try:
            if self.app:
                # Discovered task names
                tasks = self._get_filtered_tasks()
                self.tracker.sync_tasks(tasks)

                # Register for periodic task discovery
                if hasattr(self.tracker, "set_task_provider"):
                    self.tracker.set_task_provider(self._get_filtered_tasks)
        except Exception as e:
            logger.error(f"Error in Celery on_worker_ready telemetry: {e}")
