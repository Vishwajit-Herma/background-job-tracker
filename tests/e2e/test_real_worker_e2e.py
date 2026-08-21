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
def api_key_fixture(db):
    user, _ = User.objects.get_or_create(email="e2e@example.com")
    if _:
        user.set_password("password")
        user.save()

    team = Team.objects.filter(owner=user).first()
    if not team:
        team = Team.objects.create(name="E2E Team", owner=user)

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
def test_real_worker_e2e(live_server, api_key_fixture, tmp_path):
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
    env["PYTHONPATH"] = os.path.abspath("sdk") + ":" + env.get("PYTHONPATH", "")

    # Start the worker (using solo pool to simplify test setup)
    worker_proc = subprocess.Popen(
        [sys.executable, "-m", "celery", "-A", "worker.app", "worker", "-l", "info", "-P", "solo"],
        cwd=str(tmp_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Give worker time to start and sync tasks
        time.sleep(5)

        # Verify periodic discovery synced tasks
        assert TaskRegistry.objects.filter(
            project=project, task_identifier="e2e.real_task"
        ).exists()

        # Now enqueue a task from the test process
        app = Celery("e2e_app", broker="redis://localhost:6379/1")
        app.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
        )
        result = app.send_task("e2e.real_task")

        # Wait for task to finish and telemetry to be sent
        time.sleep(3)

        # Check jobs and executions
        job = Job.objects.filter(project=project, task_identifier="e2e.real_task").first()
        assert job is not None

        execution = Execution.objects.filter(job=job, external_id=result.id).first()
        assert execution is not None
        assert execution.status == "success"

        events = ExecutionEvent.objects.filter(execution=execution)
        assert events.count() >= 2
        statuses = [e.status for e in events]
        assert "running" in statuses
        assert "success" in statuses

    finally:
        worker_proc.terminate()
        worker_proc.wait()


@pytest.mark.django_db(transaction=True)
def test_real_worker_prefork_e2e(live_server, api_key_fixture, tmp_path):
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

app = Celery("e2e_prefork_app", broker="redis://localhost:6379/1")
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
    env["PYTHONPATH"] = os.path.abspath("sdk") + ":" + env.get("PYTHONPATH", "")

    # Start the worker with PREFORK pool, deliberately validating fork-safety of the SDK
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
            "prefork",
        ],
        cwd=str(tmp_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Give worker time to start and sync tasks
        time.sleep(5)

        # Verify periodic discovery synced tasks
        assert TaskRegistry.objects.filter(
            project=project, task_identifier="e2e.real_prefork_task"
        ).exists()

        # Enqueue a task
        app = Celery("e2e_prefork_app", broker="redis://localhost:6379/1")
        app.conf.update(
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
        )
        result = app.send_task("e2e.real_prefork_task")

        # Wait for task to finish and telemetry to be sent
        time.sleep(3)

        # Check jobs and executions
        job = Job.objects.filter(project=project, task_identifier="e2e.real_prefork_task").first()
        assert job is not None

        execution = Execution.objects.filter(job=job, external_id=result.id).first()
        assert execution is not None
        assert execution.status == "success"

        events = ExecutionEvent.objects.filter(execution=execution)
        assert events.count() >= 2
        statuses = [e.status for e in events]
        assert "running" in statuses
        assert "success" in statuses

    finally:
        worker_proc.terminate()
        worker_proc.wait()
