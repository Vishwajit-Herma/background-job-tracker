from unittest import mock
from background_job_tracker.integrations.celery import CeleryIntegration


class DummyRequest:
    def __init__(self, id):
        self.id = id
        self.hostname = "worker-1"
        self.retries = 0
        self.delivery_info = {"routing_key": "celery"}


class DummyTask:
    def __init__(self, name):
        self.name = name
        self.request = DummyRequest("ext_id_1")


def test_celery_integration():
    tracker = mock.Mock()
    app = mock.Mock()
    app.tasks = {"task.1": mock.Mock(), "task.2": mock.Mock(), "celery.chord": mock.Mock()}

    integration = CeleryIntegration(app, tracker)

    task = DummyTask("demo_task")

    # Prerun
    integration.on_task_prerun(sender=task, task_id="ext_id_1", task=task)
    assert hasattr(task.request, "bjt_started_at")
    assert tracker.enqueue_event.call_count == 1
    event = tracker.enqueue_event.call_args[0][0]
    assert event["status"] == "running"
    assert event["external_id"] == "ext_id_1"
    assert event["task_identifier"] == "demo_task"
    assert event["worker"] == "worker-1"
    assert event["queue"] == "celery"

    # Success
    integration.on_task_success(sender=task, task_id="ext_id_1", result="ok")
    assert tracker.enqueue_event.call_count == 2
    event2 = tracker.enqueue_event.call_args[0][0]
    assert event2["status"] == "success"
    assert event2["event_id"] != event["event_id"]  # Must generate unique event_ids
    assert "duration_ms" in event2

    # Worker Ready
    integration.on_worker_ready()
    tracker.sync_tasks.assert_called_once_with(["task.1", "task.2"])

    assert hasattr(tracker, "set_task_provider")


def test_celery_integration_failure():
    tracker = mock.Mock()
    integration = CeleryIntegration(mock.Mock(), tracker)
    task = DummyTask("demo_task")

    class DummyEinfo:
        exception = ValueError("Test error")
        traceback = "Traceback (most recent call last):\n..."

    integration.on_task_failure(sender=task, task_id="ext_id_1", einfo=DummyEinfo())

    assert tracker.enqueue_event.call_count == 1
    event = tracker.enqueue_event.call_args[0][0]
    assert event["status"] == "failed"
    assert event["error_type"] == "ValueError"
    assert event["error_message"] == "Test error"
    assert "Traceback" in event["traceback"]


def test_celery_integration_retry():
    tracker = mock.Mock()
    integration = CeleryIntegration(mock.Mock(), tracker)
    task = DummyTask("demo_task")

    class DummyEinfo:
        exception = ValueError("Retry error")
        traceback = "..."

    # First prerun
    integration.on_task_prerun(sender=task, task_id="ext_id_1", task=task)
    event_run1 = tracker.enqueue_event.call_args[0][0]

    # Retry
    integration.on_task_retry(sender=task, task_id="ext_id_1", einfo=DummyEinfo())
    event_retry = tracker.enqueue_event.call_args[0][0]

    # Second prerun (Celery increments retry count)
    task.request.retries = 1
    integration.on_task_prerun(sender=task, task_id="ext_id_1", task=task)
    event_run2 = tracker.enqueue_event.call_args[0][0]

    assert event_run1["external_id"] == "ext_id_1"
    assert event_retry["external_id"] == "ext_id_1"
    assert event_run2["external_id"] == "ext_id_1"

    # Event IDs must be unique
    event_ids = {event_run1["event_id"], event_retry["event_id"], event_run2["event_id"]}
    assert len(event_ids) == 3

    assert event_retry["status"] == "retry"
    assert event_run1["retry_count"] == 0
    assert event_retry["retry_count"] == 0
    assert event_run2["retry_count"] == 1
