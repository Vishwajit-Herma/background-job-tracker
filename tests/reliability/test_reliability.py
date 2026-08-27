import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.teams.models import Team, TeamMember
from apps.projects.models import Project
from apps.jobs.models import Job
from apps.executions.models import Execution
from apps.alerts.models import AlertRule
from apps.incidents.models import Incident
from apps.reliability.models import JobExpectation, ReliabilityFinding
from apps.reliability.services import calculate_job_baseline, get_job_reliability_overview
from apps.reliability.evaluators import evaluate_all_jobs_reliability


@pytest.fixture
def test_setup(db):
    User = get_user_model()
    owner = User.objects.create(email="reliability_owner@example.com")
    owner.set_password("pass123")
    owner.save()

    member_user = User.objects.create(email="reliability_member@example.com")
    member_user.set_password("pass123")
    member_user.save()

    other_user = User.objects.create(email="other_user@example.com")
    other_user.set_password("pass123")
    other_user.save()

    team = Team.objects.create(name="Reliability Team", slug="rel-team", owner=owner)
    TeamMember.objects.create(team=team, user=member_user, role="member", is_active=True)

    Team.objects.create(name="Other Team", slug="other-team", owner=other_user)

    project = Project.objects.create(team=team, name="Reliability Project")
    job = Job.objects.create(
        project=project, name="Email Sync Task", task_identifier="tasks.email_sync"
    )

    return {
        "owner": owner,
        "member_user": member_user,
        "other_user": other_user,
        "team": team,
        "project": project,
        "job": job,
    }


@pytest.mark.django_db
def test_baseline_generation(test_setup):
    job = test_setup["job"]
    base_time = timezone.now() - timedelta(days=2)

    for i in range(5):
        t = base_time + timedelta(seconds=i * 60)
        Execution.objects.create(
            job=job,
            external_id=f"baseline_exec_{i}",
            status=Execution.Status.SUCCESS,
            started_at=t,
            finished_at=t + timedelta(milliseconds=(i + 1) * 100),
            duration_ms=(i + 1) * 100,
            last_event_at=t + timedelta(milliseconds=(i + 1) * 100),
            created_at=t,
        )

    baseline = calculate_job_baseline(job, sample_window_days=7)

    assert baseline.is_sufficient is True
    assert baseline.total_executions_analyzed == 5
    assert baseline.median_interval_seconds == 60.0
    assert baseline.p50_runtime_ms == 300.0
    assert baseline.p95_runtime_ms == 480.0


@pytest.mark.django_db
def test_insufficient_baseline_data(test_setup):
    job = test_setup["job"]
    now = timezone.now()

    Execution.objects.create(
        job=job,
        external_id="exec_single",
        status=Execution.Status.SUCCESS,
        started_at=now,
        finished_at=now + timedelta(seconds=1),
        duration_ms=1000,
        last_event_at=now,
        created_at=now,
    )

    baseline = calculate_job_baseline(job, sample_window_days=7)
    assert baseline.is_sufficient is False
    assert baseline.median_interval_seconds is None


@pytest.mark.django_db
def test_missed_execution_detection_and_boundaries(test_setup):
    job = test_setup["job"]
    now = timezone.now()

    JobExpectation.objects.create(
        job=job,
        expected_interval_seconds=300,
        grace_period_seconds=60,
    )

    # 1. Last run was 250s ago (within expected interval of 300s) -> No missed finding
    exec1 = Execution.objects.create(
        job=job,
        external_id="exec_on_time",
        status=Execution.Status.SUCCESS,
        started_at=now - timedelta(seconds=250),
        last_event_at=now - timedelta(seconds=250),
        created_at=now - timedelta(seconds=250),
    )

    evaluate_all_jobs_reliability()
    assert ReliabilityFinding.objects.filter(job=job, status="ACTIVE").count() == 0

    # 2. Update execution time to 400s ago (exceeds interval 300s + grace 60s = 360s)
    exec1.started_at = now - timedelta(seconds=400)
    exec1.created_at = now - timedelta(seconds=400)
    exec1.last_event_at = now - timedelta(seconds=400)
    exec1.save()

    evaluate_all_jobs_reliability()
    active_finding = ReliabilityFinding.objects.filter(job=job, status="ACTIVE").first()
    assert active_finding is not None
    assert active_finding.condition_type == ReliabilityFinding.ConditionType.MISSED_EXECUTION
    assert active_finding.details["overdue_by_seconds"] == 40


@pytest.mark.django_db
def test_missed_execution_recovery(test_setup):
    job = test_setup["job"]
    now = timezone.now()

    JobExpectation.objects.create(
        job=job,
        expected_interval_seconds=60,
        grace_period_seconds=0,
    )

    # Execution 200s ago -> triggers missed
    Execution.objects.create(
        job=job,
        external_id="old_exec",
        status=Execution.Status.SUCCESS,
        started_at=now - timedelta(seconds=200),
        last_event_at=now - timedelta(seconds=200),
        created_at=now - timedelta(seconds=200),
    )

    evaluate_all_jobs_reliability()
    assert ReliabilityFinding.objects.filter(job=job, status="ACTIVE").count() == 1

    # New execution occurs right now
    Execution.objects.create(
        job=job,
        external_id="new_exec",
        status=Execution.Status.RUNNING,
        started_at=now,
        last_event_at=now,
        created_at=now,
    )

    evaluate_all_jobs_reliability()
    assert ReliabilityFinding.objects.filter(job=job, status="ACTIVE").count() == 0
    recovered_finding = ReliabilityFinding.objects.filter(job=job, status="RECOVERED").first()
    assert recovered_finding is not None
    assert recovered_finding.recovered_at is not None


@pytest.mark.django_db
def test_stalled_and_overdue_execution_detection(test_setup):
    job = test_setup["job"]
    now = timezone.now()

    JobExpectation.objects.create(
        job=job,
        max_runtime_seconds=60,
        max_queue_delay_seconds=30,
    )

    # Running execution running for 120s (exceeds max_runtime of 60s)
    running_exec = Execution.objects.create(
        job=job,
        external_id="stalled_exec",
        status=Execution.Status.RUNNING,
        started_at=now - timedelta(seconds=120),
        last_event_at=now - timedelta(seconds=120),
        created_at=now - timedelta(seconds=130),
    )

    # Pending execution queued for 80s (exceeds max_queue_delay of 30s)
    pending_exec = Execution.objects.create(
        job=job,
        external_id="overdue_exec",
        status=Execution.Status.PENDING,
        last_event_at=now - timedelta(seconds=80),
        created_at=now - timedelta(seconds=80),
    )

    evaluate_all_jobs_reliability()

    stalled_finding = ReliabilityFinding.objects.filter(
        job=job, condition_type="STALLED_EXECUTION", status="ACTIVE"
    ).first()
    assert stalled_finding is not None
    assert stalled_finding.execution_id == running_exec.id

    overdue_finding = ReliabilityFinding.objects.filter(
        job=job, condition_type="OVERDUE_EXECUTION", status="ACTIVE"
    ).first()
    assert overdue_finding is not None
    assert overdue_finding.execution_id == pending_exec.id

    # Finished execution should not trigger stalled or overdue
    running_exec.status = Execution.Status.SUCCESS
    running_exec.finished_at = now
    running_exec.duration_ms = 120000
    running_exec.save()

    pending_exec.status = Execution.Status.RUNNING
    pending_exec.started_at = now
    pending_exec.save()

    evaluate_all_jobs_reliability()

    assert ReliabilityFinding.objects.filter(job=job, status="ACTIVE").count() == 0
    assert ReliabilityFinding.objects.filter(job=job, status="RECOVERED").count() == 2


@pytest.mark.django_db
def test_disabled_archived_job_exclusion(test_setup):
    job = test_setup["job"]
    now = timezone.now()

    JobExpectation.objects.create(
        job=job,
        expected_interval_seconds=60,
        is_enabled=False,
    )

    Execution.objects.create(
        job=job,
        external_id="exec_disabled",
        status=Execution.Status.SUCCESS,
        started_at=now - timedelta(seconds=300),
        last_event_at=now - timedelta(seconds=300),
        created_at=now - timedelta(seconds=300),
    )

    evaluate_all_jobs_reliability()
    assert ReliabilityFinding.objects.filter(job=job).count() == 0


@pytest.mark.django_db
def test_duplicate_evaluator_execution_idempotency(test_setup):
    job = test_setup["job"]
    now = timezone.now()

    JobExpectation.objects.create(
        job=job,
        expected_interval_seconds=60,
        grace_period_seconds=0,
    )

    Execution.objects.create(
        job=job,
        external_id="exec_repeated",
        status=Execution.Status.SUCCESS,
        started_at=now - timedelta(seconds=200),
        last_event_at=now - timedelta(seconds=200),
        created_at=now - timedelta(seconds=200),
    )

    # Run evaluator 5 times consecutively
    for _ in range(5):
        evaluate_all_jobs_reliability()

    assert ReliabilityFinding.objects.filter(job=job, status="ACTIVE").count() == 1


@pytest.mark.django_db
def test_alert_rule_and_incident_integration(test_setup):
    job = test_setup["job"]
    project = test_setup["project"]
    now = timezone.now()

    JobExpectation.objects.create(
        job=job,
        expected_interval_seconds=60,
    )

    AlertRule.objects.create(
        project=project,
        job=job,
        metric=AlertRule.MetricType.MISSED_EXECUTION,
        threshold=0,
        severity=AlertRule.Severity.CRITICAL,
    )

    Execution.objects.create(
        job=job,
        external_id="exec_alert_test",
        status=Execution.Status.SUCCESS,
        started_at=now - timedelta(seconds=300),
        last_event_at=now - timedelta(seconds=300),
        created_at=now - timedelta(seconds=300),
    )

    evaluate_all_jobs_reliability()

    finding = ReliabilityFinding.objects.filter(job=job, status="ACTIVE").first()
    assert finding is not None
    assert finding.incident is not None
    assert finding.incident.status == Incident.Status.OPEN
    assert finding.incident.severity == Incident.Severity.CRITICAL

    # Recover
    Execution.objects.create(
        job=job,
        external_id="exec_recovery",
        status=Execution.Status.RUNNING,
        started_at=now,
        last_event_at=now,
        created_at=now,
    )

    evaluate_all_jobs_reliability()

    finding.refresh_from_db()
    assert finding.status == ReliabilityFinding.Status.RECOVERED
    assert finding.incident.status == Incident.Status.RESOLVED


@pytest.mark.django_db
def test_reliability_api_endpoints_and_tenant_isolation(test_setup):
    owner = test_setup["owner"]
    member = test_setup["member_user"]
    other_user = test_setup["other_user"]
    job = test_setup["job"]
    project = test_setup["project"]

    client = APIClient()

    # 1. Member can read job overview
    client.force_authenticate(user=member)
    res = client.get(f"/api/reliability/jobs/{job.id}/")
    assert res.status_code == 200
    data = res.data.get("data", res.data)
    assert data["job_id"] == job.id
    assert data["current_state"] == "HEALTHY"

    # 2. Member cannot modify expectation (requires admin/owner)
    res = client.put(
        f"/api/reliability/jobs/{job.id}/expectation/",
        {
            "expected_interval_seconds": 3600,
            "max_runtime_seconds": 300,
        },
    )
    assert res.status_code == 403

    # 3. Owner can update expectation
    client.force_authenticate(user=owner)
    res = client.put(
        f"/api/reliability/jobs/{job.id}/expectation/",
        {
            "expected_interval_seconds": 3600,
            "max_runtime_seconds": 300,
            "is_enabled": True,
        },
    )
    assert res.status_code == 200
    data = res.data.get("data", res.data)
    assert data["expected_interval_seconds"] == 3600

    # 3. GET expectation via Job Reliability Overview
    res = client.get(f"/api/reliability/jobs/{job.id}/")
    assert res.status_code == 200
    data = res.data.get("data", res.data)
    assert data["expected_interval_seconds"] == 3600
    assert data["expectation_source"] == "CONFIGURED"
    assert "next_expected_at" in data
    assert "missed_after_at" in data

    # 4. Other user from another team gets 403 / 404 forbidden
    client.force_authenticate(user=other_user)
    res = client.get(f"/api/reliability/jobs/{job.id}/")
    assert res.status_code in [403, 404]

    # 5. Project overview endpoint
    client.force_authenticate(user=owner)
    res = client.get(f"/api/reliability/projects/{project.id}/")
    assert res.status_code == 200
    data = res.data.get("data", res.data)
    assert data["project_id"] == project.id
    assert data["total_jobs"] == 1
    assert data["healthy_jobs_count"] == 1
    assert data["jobs"][0]["expectation_source"] == "CONFIGURED"
    assert "missed_after_at" in data["jobs"][0]

    # 6. Manual baseline recalculation endpoint (asynchronous 202 Accepted)
    res = client.post(
        f"/api/reliability/jobs/{job.id}/recalculate-baseline/", {"sample_window_days": 14}
    )
    assert res.status_code == 202
    data = res.data.get("data", res.data)
    assert data["status"] == "accepted"
    assert data["sample_window_days"] == 14

    # 7. Findings list endpoint
    ReliabilityFinding.objects.create(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.MISSED_EXECUTION,
        status=ReliabilityFinding.Status.ACTIVE,
        details={"overdue_by_seconds": 120},
    )
    res = client.get("/api/reliability/findings/?status=ACTIVE")
    assert res.status_code == 200
    data = res.data.get("data", res.data)
    assert len(data) >= 1


@pytest.mark.django_db
def test_finding_without_matching_alert_rule_creates_no_incident(test_setup):
    from apps.reliability.evaluators import evaluate_job_reliability
    from apps.incidents.models import Incident

    job = test_setup["job"]
    project = test_setup["project"]

    # Configure expectation
    JobExpectation.objects.create(
        job=job,
        expected_interval_seconds=60,
        grace_period_seconds=0,
    )

    now = timezone.now()
    Execution.objects.create(
        job=job,
        external_id="exec_no_rule",
        status=Execution.Status.SUCCESS,
        started_at=now - timedelta(seconds=200),
        last_event_at=now - timedelta(seconds=200),
        created_at=now - timedelta(seconds=200),
    )

    # Evaluate reliability without creating any AlertRule
    evaluate_job_reliability(job.id)

    # Verify active finding is created
    finding = ReliabilityFinding.objects.filter(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.MISSED_EXECUTION,
        status=ReliabilityFinding.Status.ACTIVE,
    ).first()
    assert finding is not None
    assert finding.incident is None

    # Verify no Incident was created
    assert Incident.objects.filter(project=project, job=job).count() == 0


@pytest.mark.django_db
def test_serializer_and_model_validation(test_setup):
    from django.core.exceptions import ValidationError
    from apps.reliability.serializers import JobExpectationSerializer

    job = test_setup["job"]

    # 1. Model clean validation on invalid interval
    invalid_exp = JobExpectation(job=job, expected_interval_seconds=0)
    with pytest.raises(ValidationError) as exc:
        invalid_exp.clean()
    assert "expected_interval_seconds" in exc.value.message_dict

    # 2. Serializer validation on invalid interval
    serializer = JobExpectationSerializer(
        data={"expected_interval_seconds": 0, "max_runtime_seconds": -5}
    )
    assert not serializer.is_valid()
    assert "expected_interval_seconds" in serializer.errors
    assert "max_runtime_seconds" in serializer.errors

    # 3. Model clean validation on inactive job
    job.status = "inactive"
    job.save()
    with pytest.raises(ValidationError) as exc:
        invalid_exp.clean()
    assert "job" in exc.value.message_dict


@pytest.mark.django_db
def test_get_expectation_does_not_create_db_row(test_setup):
    client = APIClient()
    owner = test_setup["owner"]
    project = test_setup["project"]
    new_job = Job.objects.create(
        project=project,
        name="Job Without Expectation",
        task_identifier="tasks.job_without_exp",
    )

    client.force_authenticate(user=owner)
    # Check that no JobExpectation exists initially
    assert not JobExpectation.objects.filter(job=new_job).exists()

    # GET expectation endpoint
    res = client.get(f"/api/reliability/jobs/{new_job.id}/expectation/")
    assert res.status_code == 200
    data = res.data.get("data", res.data)
    assert data["id"] is None
    assert data["job"] == new_job.id

    # Verify no row was created
    assert not JobExpectation.objects.filter(job=new_job).exists()


@pytest.mark.django_db
def test_disabled_job_expectation_recovers_findings_and_resolves_incidents(test_setup):
    from apps.reliability.evaluators import evaluate_job_reliability
    from apps.incidents.models import Incident

    job = test_setup["job"]
    project = test_setup["project"]

    # Create active finding with incident
    incident = Incident.objects.create(
        project=project,
        job=job,
        severity="DEGRADED",
        trigger_metadata={"test": "true"},
    )
    finding = ReliabilityFinding.objects.create(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.MISSED_EXECUTION,
        status=ReliabilityFinding.Status.ACTIVE,
        incident=incident,
        details={"overdue_by_seconds": 300},
    )

    # Disable expectations
    expectation, _ = JobExpectation.objects.get_or_create(job=job)
    expectation.is_enabled = False
    expectation.save()

    # Evaluate reliability
    evaluate_job_reliability(job.id)

    finding.refresh_from_db()
    assert finding.status == ReliabilityFinding.Status.RECOVERED
    assert finding.recovered_at is not None
    assert finding.last_evaluated_at is not None

    incident.refresh_from_db()
    assert incident.status == Incident.Status.RESOLVED

    # Check overview state is DISABLED rather than MISSED
    overview = get_job_reliability_overview(job)
    assert overview["current_state"] == "DISABLED"
    assert overview["is_enabled"] is False

    client = APIClient()
    client.force_authenticate(user=test_setup["owner"])
    project_res = client.get(f"/api/reliability/projects/{job.project.id}/")
    assert project_res.status_code == 200
    p_data = project_res.data.get("data", project_res.data)
    assert p_data["jobs"][0]["current_state"] == "DISABLED"


@pytest.mark.django_db
def test_async_baseline_recalculation_validation(test_setup):
    client = APIClient()
    owner = test_setup["owner"]
    job = test_setup["job"]

    client.force_authenticate(user=owner)

    # Invalid sample_window_days (< 1)
    res = client.post(
        f"/api/reliability/jobs/{job.id}/recalculate-baseline/", {"sample_window_days": 0}
    )
    assert res.status_code == 400

    # Invalid sample_window_days (> 90)
    res = client.post(
        f"/api/reliability/jobs/{job.id}/recalculate-baseline/", {"sample_window_days": 100}
    )
    assert res.status_code == 400

    # Valid sample_window_days
    res = client.post(
        f"/api/reliability/jobs/{job.id}/recalculate-baseline/", {"sample_window_days": 30}
    )
    assert res.status_code == 202
    data = res.data.get("data", res.data)
    assert data["status"] == "accepted"


@pytest.mark.django_db
def test_project_reliability_no_n_plus_one(test_setup, django_assert_num_queries):
    client = APIClient()
    owner = test_setup["owner"]
    project = test_setup["project"]

    # Create 5 more jobs in the project
    for i in range(5):
        Job.objects.create(
            project=project,
            name=f"Batch Job {i}",
            task_identifier=f"tasks.batch_{i}",
        )

    client.force_authenticate(user=owner)

    # Query count should remain low and constant regardless of job count (no N+1 per job)
    with django_assert_num_queries(7):
        res = client.get(f"/api/reliability/projects/{project.id}/")
        assert res.status_code == 200
        data = res.data.get("data", res.data)
        assert data["total_jobs"] == 6


@pytest.mark.django_db(transaction=True)
def test_true_concurrent_evaluator_execution(test_setup):
    import concurrent.futures
    from apps.reliability.evaluators import evaluate_job_reliability
    from apps.alerts.models import AlertRule
    from apps.incidents.models import Incident

    job = test_setup["job"]
    project = test_setup["project"]

    # Configure expectation to trigger missed finding
    JobExpectation.objects.create(
        job=job,
        expected_interval_seconds=60,
        grace_period_seconds=0,
    )
    # Configure alert rule for MISSED_EXECUTION
    AlertRule.objects.create(
        project=project,
        job=job,
        metric=AlertRule.MetricType.MISSED_EXECUTION,
        threshold=1,
        severity="DEGRADED",
    )

    now = timezone.now()
    Execution.objects.create(
        job=job,
        external_id="exec_old_concurrent",
        status=Execution.Status.SUCCESS,
        started_at=now - timedelta(seconds=200),
        last_event_at=now - timedelta(seconds=200),
        created_at=now - timedelta(seconds=200),
    )

    # Concurrently execute evaluator from 5 parallel threads
    def run_eval():
        from django.db import connection

        try:
            evaluate_job_reliability(job.id)
            return True
        finally:
            connection.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_eval) for _ in range(5)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 5
    # Verify exact single active finding was created without duplicate violations
    active_findings = ReliabilityFinding.objects.filter(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.MISSED_EXECUTION,
        status=ReliabilityFinding.Status.ACTIVE,
    )
    assert active_findings.count() == 1

    # Verify exact single active incident was created
    active_incidents = Incident.objects.filter(
        project=project,
        job=job,
        status__in=[Incident.Status.OPEN, Incident.Status.ACKNOWLEDGED],
    )
    assert active_incidents.count() == 1
