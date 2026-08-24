import pytest
from datetime import timedelta
import threading
from django.utils import timezone
from apps.alerts.models import AlertRule
from apps.alerts.tasks import evaluate_alert_rules
from apps.incidents.models import Incident, IncidentEvent
from apps.executions.models import Execution
from apps.projects.models import Project
from apps.jobs.models import Job
from apps.teams.models import Team
from django.contrib.auth import get_user_model


@pytest.fixture
def setup_data(db):
    User = get_user_model()
    user = User.objects.create(email="analytics2@example.com")
    user.set_password("password")
    user.save()

    team = Team.objects.create(name="Analytics Team 2", slug="analytics2", owner=user)
    project = Project.objects.create(team=team, name="Analytics Project 2")
    job1 = Job.objects.create(project=project, name="Job 1", task_identifier="task_1")
    job2 = Job.objects.create(project=project, name="Job 2", task_identifier="task_2")

    return user, team, project, job1, job2


@pytest.mark.django_db
def test_evaluator_creates_incident_on_failure_rate(setup_data):
    user, team, project, job1, job2 = setup_data

    rule = AlertRule.objects.create(
        project=project,
        job=job1,
        metric=AlertRule.MetricType.FAILURE_RATE,
        threshold=5.0,
        window_minutes=15,
        severity=AlertRule.Severity.CRITICAL,
    )

    now = timezone.now()
    # Create 1 success, 1 failure => 50% failure rate
    Execution.objects.create(
        job=job1,
        external_id="1",
        status=Execution.Status.SUCCESS,
        started_at=now - timedelta(minutes=5),
        duration_ms=100,
        last_event_at=now,
    )
    Execution.objects.create(
        job=job1,
        external_id="2",
        status=Execution.Status.FAILED,
        started_at=now - timedelta(minutes=4),
        duration_ms=100,
        last_event_at=now,
    )

    evaluate_alert_rules()

    incident = Incident.objects.filter(alert_rule=rule).first()
    assert incident is not None
    assert incident.status == Incident.Status.OPEN
    assert incident.severity == Incident.Severity.CRITICAL
    assert incident.project == project
    assert incident.job == job1
    assert incident.trigger_metadata["metric_value"] == 50.0

    events = incident.events.all()
    assert events.count() == 1
    assert events[0].event_type == IncidentEvent.EventType.CREATED


@pytest.mark.django_db
def test_evaluator_deduplicates_active_incidents(setup_data):
    user, team, project, job1, job2 = setup_data

    AlertRule.objects.create(
        project=project,
        job=job1,
        metric=AlertRule.MetricType.FAILURE_RATE,
        threshold=5.0,
    )

    now = timezone.now()
    Execution.objects.create(
        job=job1,
        external_id="3",
        status=Execution.Status.FAILED,
        started_at=now - timedelta(minutes=4),
        duration_ms=100,
        last_event_at=now,
    )

    evaluate_alert_rules()
    assert Incident.objects.count() == 1

    # Run evaluator again, should not create a second incident
    evaluate_alert_rules()
    assert Incident.objects.count() == 1


@pytest.mark.django_db
def test_evaluator_auto_resolves(setup_data):
    user, team, project, job1, job2 = setup_data

    rule = AlertRule.objects.create(
        project=project,
        job=job1,
        metric=AlertRule.MetricType.FAILURE_RATE,
        threshold=10.0,
    )

    # Force an open incident manually
    incident = Incident.objects.create(
        project=project,
        job=job1,
        alert_rule=rule,
        status=Incident.Status.OPEN,
    )

    # Add a successful execution so total_executions > 0 and failure rate becomes 0.0%
    now = timezone.now()
    Execution.objects.create(
        job=job1,
        external_id="resolve1",
        status=Execution.Status.SUCCESS,
        started_at=now,
        duration_ms=10,
        last_event_at=now,
    )

    evaluate_alert_rules()
    incident.refresh_from_db()

    assert incident.status == Incident.Status.RESOLVED
    assert incident.resolution_type == Incident.ResolutionType.AUTOMATIC

    events = incident.events.filter(event_type=IncidentEvent.EventType.AUTO_RESOLVED)
    assert events.exists()


@pytest.mark.django_db
def test_project_level_alert_rule(setup_data):
    user, team, project, job1, job2 = setup_data

    rule = AlertRule.objects.create(
        project=project,
        job=None,  # Project-level
        metric=AlertRule.MetricType.FAILURE_RATE,
        threshold=5.0,
    )

    now = timezone.now()
    Execution.objects.create(
        job=job1,
        external_id="4",
        status=Execution.Status.SUCCESS,
        started_at=now,
        duration_ms=100,
        last_event_at=now,
    )
    Execution.objects.create(
        job=job2,
        external_id="5",
        status=Execution.Status.FAILED,
        started_at=now,
        duration_ms=100,
        last_event_at=now,
    )

    # 1 success, 1 failure across the project = 50% failure rate
    evaluate_alert_rules()
    incident = Incident.objects.get(alert_rule=rule)
    assert incident.project == project
    assert incident.job is None
    assert incident.trigger_metadata["metric_value"] == 50.0


@pytest.mark.django_db
def test_evaluator_creates_incident_on_p95_duration(setup_data):
    user, team, project, job1, job2 = setup_data

    rule = AlertRule.objects.create(
        project=project,
        job=job1,
        metric=AlertRule.MetricType.P95_DURATION,
        threshold=5000.0,
    )

    now = timezone.now()
    # P95 requires at least 2 executions to compute in analytics.py
    Execution.objects.create(
        job=job1,
        external_id="6",
        status=Execution.Status.SUCCESS,
        started_at=now - timedelta(minutes=5),
        duration_ms=6000,
        last_event_at=now,
    )
    Execution.objects.create(
        job=job1,
        external_id="6b",
        status=Execution.Status.SUCCESS,
        started_at=now - timedelta(minutes=4),
        duration_ms=6000,
        last_event_at=now,
    )

    evaluate_alert_rules()

    incident = Incident.objects.filter(alert_rule=rule).first()
    assert incident is not None
    assert incident.trigger_metadata["metric_value"] == 6000.0


@pytest.mark.django_db
def test_evaluator_creates_incident_on_retry_rate(setup_data):
    user, team, project, job1, job2 = setup_data

    rule = AlertRule.objects.create(
        project=project,
        job=job1,
        metric=AlertRule.MetricType.RETRY_RATE,
        threshold=50.0,
    )

    now = timezone.now()
    Execution.objects.create(
        job=job1,
        external_id="7",
        status=Execution.Status.SUCCESS,
        started_at=now - timedelta(minutes=5),
        duration_ms=100,
        last_event_at=now,
    )
    Execution.objects.create(
        job=job1,
        external_id="8",
        status=Execution.Status.RETRY,
        retry_count=1,
        started_at=now - timedelta(minutes=4),
        duration_ms=100,
        last_event_at=now,
    )

    evaluate_alert_rules()

    incident = Incident.objects.filter(alert_rule=rule).first()
    assert incident is not None
    assert incident.trigger_metadata["metric_value"] == 50.0


@pytest.mark.django_db(transaction=True)
def test_concurrent_deduplication(setup_data):
    user, team, project, job1, job2 = setup_data

    # Create a rule
    rule = AlertRule.objects.create(
        project=project,
        job=job1,
        metric=AlertRule.MetricType.FAILURE_RATE,
        threshold=5.0,
        window_minutes=15,
        severity=Incident.Severity.CRITICAL,
    )

    now = timezone.now()
    Execution.objects.create(
        job=job1,
        external_id="conc1",
        status=Execution.Status.FAILED,
        started_at=now,
        duration_ms=10,
        last_event_at=now,
    )

    threads = []

    # We will invoke the task from multiple threads
    def run_evaluator():
        from django.db import connection

        try:
            evaluate_alert_rules()
        finally:
            connection.close()

    for _ in range(5):
        t = threading.Thread(target=run_evaluator)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Should only create 1 incident despite 5 parallel threads
    assert Incident.objects.filter(alert_rule=rule).count() == 1


@pytest.mark.django_db(transaction=True)
def test_evaluator_creates_incident_on_retry_rate_success_status(setup_data):
    """
    Proves that an execution with status=SUCCESS but retry_count > 0
    contributes to the RETRY_RATE calculation.
    """
    user, team, project, job1, job2 = setup_data

    rule = AlertRule.objects.create(
        project=project,
        job=job1,
        metric=AlertRule.MetricType.RETRY_RATE,
        threshold=50.0,
        window_minutes=15,
        severity=Incident.Severity.CRITICAL,
    )

    now = timezone.now()
    # Create an execution that succeeded but has retried
    Execution.objects.create(
        job=job1,
        external_id="retry1",
        status=Execution.Status.SUCCESS,
        retry_count=1,
        started_at=now,
        duration_ms=10,
        last_event_at=now,
    )

    evaluate_alert_rules()

    incident = Incident.objects.filter(alert_rule=rule).first()
    assert incident is not None
    assert incident.status == Incident.Status.OPEN


@pytest.mark.django_db(transaction=True)
def test_evaluator_creates_incident_on_retry_rate_50_percent(setup_data):
    """
    Proves that 2 executions (1 retried, 1 not retried) equals exactly 50% retry rate,
    so an AlertRule at 50% threshold correctly triggers.
    """
    user, team, project, job1, job2 = setup_data

    rule = AlertRule.objects.create(
        project=project,
        job=job1,
        metric=AlertRule.MetricType.RETRY_RATE,
        threshold=50.0,
        window_minutes=15,
        severity=Incident.Severity.CRITICAL,
    )

    now = timezone.now()

    # 1 execution that didn't retry
    Execution.objects.create(
        job=job1,
        external_id="clean1",
        status=Execution.Status.SUCCESS,
        retry_count=0,
        started_at=now,
        duration_ms=10,
        last_event_at=now,
    )

    # 1 execution that did retry
    Execution.objects.create(
        job=job1,
        external_id="retry1",
        status=Execution.Status.SUCCESS,
        retry_count=1,
        started_at=now,
        duration_ms=10,
        last_event_at=now,
    )

    evaluate_alert_rules()

    incident = Incident.objects.filter(alert_rule=rule).first()
    assert incident is not None
    assert incident.trigger_metadata["metric_value"] == 50.0
    assert incident.status == Incident.Status.OPEN


@pytest.mark.django_db(transaction=True)
def test_concurrent_auto_resolve_vs_manual_resolve(setup_data):
    """
    Regression test for evaluator auto-resolution racing with manual actions.
    Since both use the same services with select_for_update, the last action wins cleanly
    and state transitions don't corrupt.
    """
    user, team, project, job1, job2 = setup_data
    from apps.incidents.services import resolve_incident

    rule = AlertRule.objects.create(
        project=project,
        job=job1,
        metric=AlertRule.MetricType.FAILURE_RATE,
        threshold=5.0,
        window_minutes=15,
        severity=Incident.Severity.CRITICAL,
    )

    now = timezone.now()
    Execution.objects.create(
        job=job1,
        external_id="conc1",
        status=Execution.Status.FAILED,
        started_at=now,
        duration_ms=10,
        last_event_at=now,
    )

    # First pass creates incident
    evaluate_alert_rules()
    incident = Incident.objects.get(alert_rule=rule)
    assert incident.status == Incident.Status.OPEN

    # Now add success so it will auto-resolve next pass
    Execution.objects.create(
        job=job1,
        external_id="conc2",
        status=Execution.Status.SUCCESS,
        started_at=now,
        duration_ms=10,
        last_event_at=now,
    )

    def run_evaluator():
        from django.db import connection

        try:
            evaluate_alert_rules()
        finally:
            connection.close()

    def run_manual_resolve():
        from django.db import connection

        try:
            resolve_incident(incident.id, user)
        except Exception:
            pass
        finally:
            connection.close()

    t1 = threading.Thread(target=run_evaluator)
    t2 = threading.Thread(target=run_manual_resolve)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    incident.refresh_from_db()
    # It must be resolved
    assert incident.status == Incident.Status.RESOLVED
