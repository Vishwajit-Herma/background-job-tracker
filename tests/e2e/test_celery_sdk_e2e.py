import pytest
import time
from rest_framework.test import APIClient
from apps.projects.models import Project, APIKey
from apps.jobs.models import Job, TaskRegistry
from apps.executions.models import Execution, ExecutionEvent
from background_job_tracker.client import Tracker
from background_job_tracker.integrations.celery import CeleryIntegration
from celery import Celery


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def project(db):
    from apps.teams.models import Team
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create(email="test_e2e@example.com")
    team = Team.objects.create(name="E2E Team", owner=user)
    return Project.objects.create(team=team, name="E2E Project")


@pytest.fixture
def api_key(project):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.first()
    instance, raw_key = APIKey.create_key(project, "Test Key", user)
    return raw_key


@pytest.mark.django_db
def test_celery_sdk_e2e(api_client, project, api_key):
    # Setup Celery App
    app = Celery("e2e_app", broker="memory://")
    app.conf.task_always_eager = True
    app.conf.task_store_eager_result = True

    @app.task(name="e2e.demo_task", bind=True)
    def demo_task(self):
        time.sleep(0.05)
        return "success"

    @app.task(name="e2e.failing_task", bind=True)
    def failing_task(self):
        raise ValueError("Intentional failure")

    # Mock requests to use APIClient
    def mock_post(url, json, **kwargs):
        print(f"DEBUG mock_post url={url} json={json}")
        path = url.replace("http://testserver", "")
        response = api_client.post(path, json, format="json", HTTP_X_API_KEY=api_key)
        print(f"DEBUG mock_post response status={response.status_code}")

        class MockResponse:
            def __init__(self, status_code, text):
                self.status_code = status_code
                self.text = text

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise Exception(self.text)

        return MockResponse(response.status_code, str(response.data))

    # Test the API directly to verify authentication
    api_client.credentials(HTTP_X_API_KEY=api_key)
    resp = api_client.post("/api/jobs/sync/", {"tasks": ["test1"]}, format="json")
    print(f"DIRECT ENDPOINT TEST: {resp.status_code} {resp.data}")
    assert resp.status_code == 200, f"Auth failed! Response: {resp.data}"

    from unittest import mock
    from background_job_tracker.sender import BackgroundSender

    # Reset singleton to ensure clean state

    Tracker._instance = None

    with (
        mock.patch("requests.Session.post", side_effect=mock_post),
        mock.patch.object(BackgroundSender, "start"),
    ):
        tracker = Tracker(
            api_key=api_key,
            base_url="http://testserver",
            batch_size=1,
            flush_interval=0.1,
        )

        integration = CeleryIntegration(app, tracker)

        def drain_queue():
            import queue

            batch = []
            while True:
                try:
                    item = tracker.event_queue.get_nowait()
                    if item.get("_type") == "sync_tasks":
                        tracker.sender._sync_tasks(item["tasks"])
                    elif item.get("_type") == "_stop":
                        pass
                    else:
                        batch.append(item)
                except queue.Empty:
                    break
            if batch:
                tracker.sender._flush_batch(batch)

        # 1. Test Task Discovery
        integration.on_worker_ready()
        drain_queue()

        # Verify Task Registry sync worked
        assert TaskRegistry.objects.filter(
            project=project, task_identifier="e2e.demo_task"
        ).exists()
        assert TaskRegistry.objects.filter(
            project=project, task_identifier="e2e.failing_task"
        ).exists()

        # 2. Execute Demo Task
        result = demo_task.apply_async()
        drain_queue()

        # Assert Jobs and Executions were created automatically
        job = Job.objects.get(project=project, task_identifier="e2e.demo_task")
        assert job.status == "active"

        execution = Execution.objects.get(job=job, external_id=result.id)
        assert execution.status == "success"
        assert execution.duration_ms is not None
        assert execution.duration_ms >= 50

        # Assert Events are stored
        events = ExecutionEvent.objects.filter(execution=execution).order_by("event_timestamp")
        assert events.count() == 2
        assert events[0].status == "running"
        assert events[1].status == "success"

        # 3. Execute Failing Task
        import contextlib

        with contextlib.suppress(ValueError):
            failing_task.apply_async()

        drain_queue()

        fail_job = Job.objects.get(project=project, task_identifier="e2e.failing_task")
        fail_execution = Execution.objects.get(job=fail_job)
        assert fail_execution.status == "failed"
        assert fail_execution.error_type in ("ValueError", "ExceptionWithTraceback")
        assert "Intentional failure" in fail_execution.error_message
