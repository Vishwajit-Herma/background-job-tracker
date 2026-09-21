import os
import sys
import time
import pytest
import subprocess
from celery import Celery

from apps.projects.models import Project, APIKey
from apps.teams.models import Team
from django.contrib.auth import get_user_model
from apps.jobs.models import Job, TaskRegistry
from apps.executions.models import Execution, ExecutionEvent

User = get_user_model()


@pytest.fixture
def api_key_fixture(transactional_db):
    user, _ = User.objects.get_or_create(email="e2e@example.com")
    if _:
        user.set_password("password")
        user.save()

    team = Team.objects.filter(owner=user).first()
    if not team:
        team = Team.objects.create(name="E2E Team", slug="e2e-team-real", owner=user)

    project, _ = Project.objects.get_or_create(team=team, name="E2E Project")

    # Try to find existing key or create new one
    key = APIKey.objects.filter(project=project).first()
    if key:
        # API keys cannot be read after creation in Keel usually,
        # but for testing we can just generate a new one
        key.delete()

    api_key_obj, api_key_str = APIKey.create_key(project, "e2e_key", user)
    return project, api_key_str


@pytest.mark.django_db(transaction=True)
def test_real_worker_e2e(live_server, api_key_fixture, tmp_path, monkeypatch):
    project, api_key_str = api_key_fixture

    worker_script = tmp_path / "worker.py"
    worker_script.write_text(f"""
import os
import time
from celery import Celery
from background_job_tracker.client import Tracker
from background_job_tracker.integrations.celery import CeleryIntegration

tracker = Tracker(
    api_key="{api_key_str}",
    base_url="{live_server.url}",
    batch_size=1,
    flush_interval=0.1,
    task_discovery_interval=1.0,
)

app = Celery("e2e_app", broker="redis://localhost:6379/1")
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)

integration = CeleryIntegration(app, tracker)

@app.task(name="e2e.real_task", bind=True)
def real_task(self):
    time.sleep(0.1)
    return "done"
""")

    env = os.environ.copy()
    env["PYTHONPATH"] = env.get("PYTHONPATH", "")
    env.pop("DJANGO_SETTINGS_MODULE", None)
    env.pop("CELERY_BROKER_URL", None)
    env.pop("CELERY_RESULT_BACKEND", None)
    env.pop("BJT_SDK_API_KEY", None)
    env["BACKGROUND_JOB_TRACKER_BASE_URL"] = live_server.url
    env["BACKGROUND_JOB_TRACKER_API_KEY"] = api_key_str

    # Start the worker (using solo pool to simplify test setup)
    with (tmp_path / "worker1_log.txt").open("w") as worker_log:
        worker_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "worker.app",
                "worker",
                "-l",
                "info",
                "-P",
                "solo",
                "-Q",
                "e2e_queue_1",
            ],
            cwd=str(tmp_path),
            env=env,
            stdout=worker_log,
            stderr=subprocess.STDOUT,
        )

    try:
        # Give worker time to start and sync tasks
        time.sleep(5)

        # Verify periodic discovery synced tasks
        assert TaskRegistry.objects.filter(
            project=project, task_identifier="e2e.real_task"
        ).exists()

        # Now enqueue a task from the test process
        monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
        monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)

        app = Celery("e2e_real_app_1", broker="redis://localhost:6379/1")
        app.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            task_always_eager=False,
        )
        app.control.purge()
        result = app.send_task("e2e.real_task", queue="e2e_queue_1")

        # Wait for task to finish and telemetry to be sent
        execution = None
        for _i in range(30):
            job = Job.objects.filter(project=project, task_identifier="e2e.real_task").first()
            if job:
                execution = Execution.objects.filter(job=job, external_id=result.id).first()
                if execution:
                    break
            time.sleep(0.5)

        # Check jobs and executions
        assert job is not None
        assert execution is not None
        assert execution.status == "success"

        events = ExecutionEvent.objects.filter(execution=execution)
        assert events.count() >= 2
        statuses = [e.status for e in events]
        assert "running" in statuses
        assert "success" in statuses

    finally:
        worker_proc.terminate()
        try:
            worker_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker_proc.kill()
            worker_proc.wait(timeout=5)


@pytest.mark.django_db(transaction=True)
def test_real_worker_prefork_e2e(live_server, api_key_fixture, tmp_path, monkeypatch):
    project, api_key_str = api_key_fixture

    worker_script = tmp_path / "worker.py"
    worker_script.write_text(f"""
import os
import time
from celery import Celery
from background_job_tracker.client import Tracker
from background_job_tracker.integrations.celery import CeleryIntegration

tracker = Tracker(
    api_key="{api_key_str}",
    base_url="{live_server.url}",
    batch_size=1,
    flush_interval=0.1,
    task_discovery_interval=1.0,
)

app = Celery("e2e_prefork_app", broker="redis://localhost:6379/2")
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)

integration = CeleryIntegration(app, tracker)

@app.task(name="e2e.real_prefork_task", bind=True)
def real_prefork_task(self):
    time.sleep(0.1)
    return "done"
""")

    env = os.environ.copy()
    env["PYTHONPATH"] = env.get("PYTHONPATH", "")
    env.pop("DJANGO_SETTINGS_MODULE", None)
    env.pop("CELERY_BROKER_URL", None)
    env.pop("CELERY_RESULT_BACKEND", None)
    env.pop("BJT_SDK_API_KEY", None)
    env["BACKGROUND_JOB_TRACKER_BASE_URL"] = live_server.url
    env["BACKGROUND_JOB_TRACKER_API_KEY"] = api_key_str

    # Start the worker with PREFORK pool, deliberately validating fork-safety of the SDK
    with (tmp_path / "worker2_log.txt").open("w") as worker_log:
        worker_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "worker.app",
                "worker",
                "-l",
                "info",
                "--concurrency=2",
                "-Q",
                "e2e_queue_2",
            ],
            cwd=str(tmp_path),
            env=env,
            stdout=worker_log,
            stderr=subprocess.STDOUT,
        )

    try:
        # Give worker time to start and sync tasks
        time.sleep(5)

        # Verify periodic discovery synced tasks
        assert TaskRegistry.objects.filter(
            project=project, task_identifier="e2e.real_prefork_task"
        ).exists()

        monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
        monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)

        # Enqueue a task
        app = Celery("e2e_prefork_app", broker="redis://localhost:6379/2")
        app.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            task_always_eager=False,
        )
        app.control.purge()
        result = app.send_task("e2e.real_prefork_task", queue="e2e_queue_2")

        # Wait for task to finish and telemetry to be sent
        execution = None
        for _ in range(30):  # Wait up to 15 seconds
            job = Job.objects.filter(
                project=project, task_identifier="e2e.real_prefork_task"
            ).first()
            if job:
                execution = Execution.objects.filter(job=job, external_id=result.id).first()
                if execution:
                    break
            time.sleep(0.5)

        # Check jobs and executions
        assert job is not None
        assert execution is not None
        assert execution.status == "success"

        events = ExecutionEvent.objects.filter(execution=execution)
        assert events.count() >= 2
        statuses = [e.status for e in events]
        assert "running" in statuses
        assert "success" in statuses

    finally:
        worker_proc.terminate()
        try:
            worker_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker_proc.kill()
            worker_proc.wait(timeout=5)
