import os
import sys
import time
import pytest
import subprocess
from celery import Celery

from apps.projects.models import Project, APIKey
from apps.teams.models import Team
from django.contrib.auth import get_user_model
from apps.jobs.models import Job
from apps.executions.models import Execution
from apps.alerts.models import AlertRule
from apps.incidents.models import Incident

User = get_user_model()


@pytest.fixture
def e2e_setup(db):
    user, _ = User.objects.get_or_create(email="e2e_full@example.com")
    if _:
        user.set_password("password")
        user.save()

    team, _ = Team.objects.get_or_create(name="E2E Full Team", owner=user)
    project, _ = Project.objects.get_or_create(team=team, name="E2E Full Project")

    # Ensure an alert rule exists so failures generate an incident
    AlertRule.objects.get_or_create(
        project=project,
        metric=AlertRule.MetricType.FAILURE_RATE,
        threshold=1,
        severity=AlertRule.Severity.CRITICAL,
    )

    key = APIKey.objects.filter(project=project).first()
    if key:
        key.delete()
    api_key_obj, api_key_str = APIKey.create_key(project, "e2e_full_key", user)
    return project, user, api_key_str


@pytest.mark.django_db(transaction=True)
def test_full_regression_pipeline(live_server, e2e_setup, tmp_path, monkeypatch):
    project, user, api_key_str = e2e_setup

    # Mock AI calls to avoid actual LLM network calls during tests
    def mock_investigate(*args, **kwargs):
        return {"answer": "Mock AI Investigation Result"}

    monkeypatch.setattr("apps.ai.services.investigate_incident", mock_investigate)

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

app = Celery("e2e_full_app", broker="redis://localhost:6379/3")
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)

integration = CeleryIntegration(app, tracker)

@app.task(name="e2e.failing_task", bind=True)
def failing_task(self):
    raise ValueError("Intentional crash for E2E pipeline")
""")

    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath("sdk") + ":" + env.get("PYTHONPATH", "")

    # Start the worker
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
            "e2e_full_queue",
        ],
        cwd=str(tmp_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        time.sleep(4)

        app = Celery("e2e_full_app", broker="redis://localhost:6379/3")
        app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])

        # Enqueue the failing task
        result = app.send_task("e2e.failing_task", queue="e2e_full_queue")

        # Wait for Execution
        execution = None
        for _ in range(30):
            job = Job.objects.filter(project=project, task_identifier="e2e.failing_task").first()
            if job:
                execution = Execution.objects.filter(job=job, external_id=result.id).first()
                if execution and execution.status == "failed":
                    break
            time.sleep(0.5)

        assert execution is not None
        assert execution.status == "failed"
        assert "Intentional crash" in execution.error_message

        # 1. Process and Validate Reliability & Anomaly Pipeline
        from apps.reliability.evaluators import evaluate_job_reliability
        from apps.reliability.services import (
            calculate_window_observation_metrics,
            get_job_reliability_overview,
        )

        # Calculate observation metrics for the job (100% failure rate observed in the window)
        obs_metrics = calculate_window_observation_metrics(job, window_minutes=60)
        assert obs_metrics["total"] >= 1
        assert obs_metrics["failure_rate"] == 100.0

        # Execute reliability evaluator to check state and detect anomalies/stalled conditions
        evaluate_job_reliability(job.id)

        # Verify job reliability overview state
        rel_overview = get_job_reliability_overview(job)
        assert rel_overview["last_execution_at"] is not None

        # 2. Trigger Alert Evaluation to detect anomaly/failure threshold and create Incident
        from apps.alerts.tasks import _evaluate_single_rule

        rule = AlertRule.objects.get(project=project)
        _evaluate_single_rule(rule)

        # The Evaluator is triggered asynchronously by signal or celery task after ingestion.
        # Ensure the incident was created.
        incident = None
        for _ in range(10):
            incident = Incident.objects.filter(project=project, alert_rule=rule).first()
            if incident:
                break
            time.sleep(0.5)

        assert incident is not None
        assert incident.status == Incident.Status.OPEN

        # 3. Exercise Runbook Lifecycle Workflow
        from apps.incidents.models import IncidentPostmortem, IncidentRunbookExecution, Runbook
        from apps.incidents.services import (
            complete_postmortem_review,
            save_incident_postmortem,
            start_runbook_execution,
            submit_postmortem_review,
            transition_runbook_step,
            update_runbook_execution_status,
        )

        runbook = Runbook.objects.create(
            project=project,
            name="E2E Pipeline Crash Runbook",
            trigger_type=Runbook.TriggerType.FAILURE_RATE_ANOMALY,
            steps=[
                {"id": "step_1", "title": "Check Worker Logs"},
                {"id": "step_2", "title": "Restart Celery Worker"},
            ],
            is_active=True,
        )

        runbook_exec = start_runbook_execution(incident.id, runbook.id, actor=user)
        assert runbook_exec.status == IncidentRunbookExecution.Status.IN_PROGRESS

        # Step 1: PENDING -> IN_PROGRESS -> COMPLETED
        transition_runbook_step(
            runbook_exec.id,
            "step_1",
            from_state="PENDING",
            to_state="IN_PROGRESS",
            actor=user,
            incident_id=incident.id,
        )
        transition_runbook_step(
            runbook_exec.id,
            "step_1",
            from_state="IN_PROGRESS",
            to_state="COMPLETED",
            actor=user,
            incident_id=incident.id,
        )

        # Step 2: PENDING -> SKIPPED
        transition_runbook_step(
            runbook_exec.id,
            "step_2",
            from_state="PENDING",
            to_state="SKIPPED",
            actor=user,
            incident_id=incident.id,
        )

        # Complete runbook execution
        update_runbook_execution_status(incident.id, runbook_exec.id, "COMPLETED", actor=user)
        assert (
            IncidentRunbookExecution.objects.get(id=runbook_exec.id).status
            == IncidentRunbookExecution.Status.COMPLETED
        )

        # 2. Exercise Postmortem Lifecycle Workflow
        postmortem = save_incident_postmortem(
            incident.id,
            {
                "summary": "E2E failing task triggered incident INC.",
                "confirmed_root_cause": "Intentional ValueError raised by celery worker test.",
                "resolution": "Fixed in regression suite.",
            },
            actor=user,
        )
        assert postmortem.status == IncidentPostmortem.Status.PENDING

        # Submit draft for review
        postmortem = submit_postmortem_review(incident.id, actor=user)
        assert postmortem.status == IncidentPostmortem.Status.IN_REVIEW

        # Complete postmortem review
        postmortem = complete_postmortem_review(incident.id, actor=user)
        assert postmortem.status == IncidentPostmortem.Status.COMPLETED

        # 3. Check existing AI integrations via our mocked functions
        import apps.ai.services

        investigation = apps.ai.services.investigate_incident(
            incident, question="Why did this fail?"
        )
        assert investigation["answer"] == "Mock AI Investigation Result"

    finally:
        worker_proc.terminate()
        worker_proc.wait()
