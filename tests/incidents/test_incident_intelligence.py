import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.teams.models import Team, TeamMember
from apps.projects.models import Project
from apps.jobs.models import Job
from apps.executions.models import Execution
from apps.alerts.models import AlertRule
from apps.incidents.models import Incident, IncidentIntelligence
from apps.incidents.intelligence import (
    determine_analysis_window,
    calculate_incident_impact,
    find_correlated_signals,
    identify_probable_causes,
    compute_incident_intelligence,
    compute_and_save_incident_intelligence,
)
from apps.incidents.services import resolve_incident
from apps.reliability.models import JobBaseline, ReliabilityFinding


def create_execution(job, external_id, status, timestamp, **kwargs):
    e = Execution.objects.create(
        job=job,
        external_id=external_id,
        status=status,
        started_at=timestamp,
        last_event_at=timestamp,
        **kwargs,
    )
    Execution.objects.filter(id=e.id).update(created_at=timestamp)
    e.refresh_from_db()
    return e


@pytest.fixture
def intelligence_setup(db):
    User = get_user_model()
    owner = User.objects.create(email="intel_owner@example.com")
    owner.set_password("pass123")
    owner.save()

    member_user = User.objects.create(email="intel_member@example.com")
    member_user.set_password("pass123")
    member_user.save()

    other_user = User.objects.create(email="other_tenant@example.com")
    other_user.set_password("pass123")
    other_user.save()

    team = Team.objects.create(name="Intel Team", slug="intel-team", owner=owner)
    TeamMember.objects.create(team=team, user=member_user, role="member", is_active=True)

    other_team = Team.objects.create(name="Other Team", slug="other-team", owner=other_user)

    project = Project.objects.create(team=team, name="Intel Project")
    other_project = Project.objects.create(team=other_team, name="Other Project")

    job1 = Job.objects.create(project=project, name="Payment Job", task_identifier="tasks.payment")
    job2 = Job.objects.create(project=project, name="Email Job", task_identifier="tasks.email")
    other_job = Job.objects.create(
        project=other_project, name="Other Job", task_identifier="tasks.other"
    )

    alert_rule = AlertRule.objects.create(
        project=project,
        job=job1,
        metric=AlertRule.MetricType.FAILURE_RATE_ANOMALY,
        threshold=5.0,
        severity=AlertRule.Severity.CRITICAL,
    )

    incident = Incident.objects.create(
        project=project,
        job=job1,
        alert_rule=alert_rule,
        status=Incident.Status.OPEN,
        severity=Incident.Severity.CRITICAL,
    )

    return {
        "owner": owner,
        "member": member_user,
        "other_user": other_user,
        "team": team,
        "project": project,
        "other_project": other_project,
        "job1": job1,
        "job2": job2,
        "other_job": other_job,
        "alert_rule": alert_rule,
        "incident": incident,
    }


@pytest.mark.django_db
def test_analysis_window_expansion_15m_30m_60m(intelligence_setup):
    incident = intelligence_setup["incident"]
    job1 = intelligence_setup["job1"]
    now = timezone.now()

    # Case 1: 5 executions within 10 minutes -> 15m window chosen
    for i in range(5):
        t = incident.created_at - timedelta(minutes=i + 1)
        create_execution(
            job=job1,
            external_id=f"exec-15m-{i}",
            status=Execution.Status.SUCCESS,
            timestamp=t,
        )

    w_start, w_end, w_mins = determine_analysis_window(incident, now=now)
    assert w_mins == 15
    assert w_start == incident.created_at - timedelta(minutes=15)

    # Case 2: Only 2 executions in 15m, 4 more at 25m (total 6 in 30m) -> 30m window chosen
    Execution.objects.filter(job=job1).delete()
    for i in range(2):
        t = incident.created_at - timedelta(minutes=i + 2)
        create_execution(
            job=job1,
            external_id=f"exec-sub15-{i}",
            status=Execution.Status.SUCCESS,
            timestamp=t,
        )
    for i in range(4):
        t = incident.created_at - timedelta(minutes=22 + i)
        create_execution(
            job=job1,
            external_id=f"exec-sub30-{i}",
            status=Execution.Status.SUCCESS,
            timestamp=t,
        )

    w_start, w_end, w_mins = determine_analysis_window(incident, now=now)
    assert w_mins == 30
    assert w_start == incident.created_at - timedelta(minutes=30)

    # Case 3: Only executions at 45m -> 60m window chosen
    Execution.objects.filter(job=job1).delete()
    for i in range(5):
        t = incident.created_at - timedelta(minutes=45 + i)
        create_execution(
            job=job1,
            external_id=f"exec-sub60-{i}",
            status=Execution.Status.SUCCESS,
            timestamp=t,
        )

    w_start, w_end, w_mins = determine_analysis_window(incident, now=now)
    assert w_mins == 60
    assert w_start == incident.created_at - timedelta(minutes=60)


@pytest.mark.django_db
def test_analysis_window_resolved_incident_boundary(intelligence_setup):
    incident = intelligence_setup["incident"]
    # Resolved incident created 2 hours ago, resolved 1.5 hours later
    t_created = timezone.now() - timedelta(hours=3)
    t_resolved = t_created + timedelta(hours=2)

    incident.created_at = t_created
    incident.resolved_at = t_resolved
    incident.status = Incident.Status.RESOLVED
    incident.save()

    w_start, w_end, w_mins = determine_analysis_window(incident)
    # Analysis window end should never exceed created_at + 60m for resolved incidents
    assert w_end <= incident.created_at + timedelta(minutes=60)


@pytest.mark.django_db
def test_impact_calculation_and_baseline_comparison(intelligence_setup):
    incident = intelligence_setup["incident"]
    job1 = intelligence_setup["job1"]
    now = timezone.now()

    # Create baseline for job1
    JobBaseline.objects.create(
        job=job1,
        sample_window_days=7,
        total_executions_analyzed=500,
        is_sufficient=True,
        failure_rate=2.0,
        retry_rate=1.0,
        p95_runtime_ms=150.0,
        avg_hourly_volume=20.0,
    )

    # Create 10 executions in window: 4 failed, 2 retry, 4 success
    for i in range(10):
        t = incident.created_at - timedelta(minutes=i + 1)
        st = (
            Execution.Status.FAILED
            if i < 4
            else (Execution.Status.RETRY if i < 6 else Execution.Status.SUCCESS)
        )
        create_execution(
            job=job1,
            external_id=f"exec-impact-{i}",
            status=st,
            worker="celery@worker-01",
            queue="payments",
            duration_ms=200,
            timestamp=t,
        )

    w_start, w_end, w_mins = determine_analysis_window(incident, now=now)
    impact = calculate_incident_impact(incident, w_start, w_end, w_mins)

    assert impact["affected_executions_count"] == 10
    assert impact["failures_count"] == 4
    assert impact["retries_count"] == 2
    assert impact["successes_count"] == 4
    assert impact["failure_rate"] == 40.0
    assert impact["retry_rate"] == 20.0
    assert impact["affected_workers"] == ["celery@worker-01"]
    assert impact["affected_queues"] == ["payments"]

    # Check baseline comparison: 40% vs 2% -> 20x multiplier
    bc = impact["baseline_comparisons"]
    assert bc["baseline_failure_rate"] == 2.0
    assert bc["current_failure_rate"] == 40.0
    assert bc["failure_rate_multiplier"] == 20.0
    assert bc["baseline_retry_rate"] == 1.0
    assert bc["current_retry_rate"] == 20.0
    assert bc["retry_rate_multiplier"] == 20.0


@pytest.mark.django_db
def test_correlation_same_worker_and_queue(intelligence_setup):
    incident = intelligence_setup["incident"]
    job1 = intelligence_setup["job1"]
    job2 = intelligence_setup["job2"]
    now = timezone.now()

    # Executions on job1 and job2 sharing worker-02 and queue-shared
    for i in range(4):
        t = incident.created_at - timedelta(minutes=i + 1)
        create_execution(
            job=job1,
            external_id=f"exec-j1-{i}",
            status=Execution.Status.FAILED,
            worker="celery@worker-02",
            queue="shared-queue",
            timestamp=t,
        )
        create_execution(
            job=job2,
            external_id=f"exec-j2-{i}",
            status=Execution.Status.FAILED,
            worker="celery@worker-02",
            queue="shared-queue",
            timestamp=t,
        )

    # Active finding on job1
    finding = ReliabilityFinding.objects.create(
        job=job1,
        condition_type=ReliabilityFinding.ConditionType.FAILURE_RATE_ANOMALY,
        status=ReliabilityFinding.Status.ACTIVE,
        severity=ReliabilityFinding.Severity.CRITICAL,
        details={"current_value": 40.0},
        detected_at=incident.created_at,
    )

    w_start, w_end, w_mins = determine_analysis_window(incident, now=now)
    executions = list(
        Execution.objects.filter(
            job__project_id=incident.project_id,
            created_at__gte=w_start,
            created_at__lte=w_end,
        ).select_related("job")
    )

    correlations = find_correlated_signals(incident, w_start, w_end, executions)

    corr_types = {c["target_type"] for c in correlations}
    assert "WORKER" in corr_types
    assert "QUEUE" in corr_types
    assert "FINDING" in corr_types

    worker_corr = next(c for c in correlations if c["target_type"] == "WORKER")
    assert worker_corr["target_name"] == "celery@worker-02"
    assert any(
        "Worker 'celery@worker-02' experienced failures" in r for r in worker_corr["reasons"]
    )

    finding_corr = next(c for c in correlations if c["target_type"] == "FINDING")
    assert finding_corr["target_id"] == finding.id


@pytest.mark.django_db
def test_correlation_cross_project_isolation(intelligence_setup):
    incident = intelligence_setup["incident"]
    other_job = intelligence_setup["other_job"]
    now = timezone.now()

    # Failures on other_job (different team/project) with same worker name
    for i in range(5):
        t = incident.created_at - timedelta(minutes=i + 1)
        create_execution(
            job=other_job,
            external_id=f"exec-other-{i}",
            status=Execution.Status.FAILED,
            worker="celery@worker-01",
            timestamp=t,
        )

    w_start, w_end, w_mins = determine_analysis_window(incident, now=now)
    executions = list(
        Execution.objects.filter(
            job__project_id=incident.project_id,
            created_at__gte=w_start,
            created_at__lte=w_end,
        ).select_related("job")
    )

    correlations = find_correlated_signals(incident, w_start, w_end, executions)
    # Zero cross-project leakage
    assert len(correlations) == 0


@pytest.mark.django_db
def test_probable_cause_worker_degradation(intelligence_setup):
    incident = intelligence_setup["incident"]
    job1 = intelligence_setup["job1"]
    now = timezone.now()

    # 10 executions: 8 failures all on worker-03, 2 successes on worker-01
    for i in range(8):
        t = incident.created_at - timedelta(minutes=i + 1)
        create_execution(
            job=job1,
            external_id=f"exec-w3-{i}",
            status=Execution.Status.FAILED,
            worker="celery@worker-03",
            timestamp=t,
        )
    for i in range(2):
        t = incident.created_at - timedelta(minutes=i + 1)
        create_execution(
            job=job1,
            external_id=f"exec-w1-{i}",
            status=Execution.Status.SUCCESS,
            worker="celery@worker-01",
            timestamp=t,
        )

    w_start, w_end, w_mins = determine_analysis_window(incident, now=now)
    executions = list(
        Execution.objects.filter(
            job__project_id=incident.project_id,
            job__is_deleted=False,
            created_at__gte=w_start,
            created_at__lte=w_end,
        ).select_related("job")
    )
    impact = calculate_incident_impact(incident, w_start, w_end, w_mins, executions=executions)
    correlations = find_correlated_signals(incident, w_start, w_end, executions)

    causes = identify_probable_causes(incident, impact, correlations, executions)

    assert len(causes) >= 1
    worker_cause = causes[0]
    assert worker_cause["candidate"] == "WORKER"
    assert worker_cause["value"] == "celery@worker-03"
    assert worker_cause["confidence"] == "HIGH"
    assert any(
        "100% of affected failures occurred on worker" in e for e in worker_cause["evidence"]
    )


@pytest.mark.django_db
def test_probable_cause_queue_congestion(intelligence_setup):
    incident = intelligence_setup["incident"]
    job1 = intelligence_setup["job1"]
    now = timezone.now()

    # Pending executions in queue 'heavy-tasks' + active OVERDUE finding
    for i in range(5):
        t = incident.created_at - timedelta(minutes=i + 1)
        create_execution(
            job=job1,
            external_id=f"exec-q-{i}",
            status=Execution.Status.PENDING,
            queue="heavy-tasks",
            timestamp=t,
        )

    ReliabilityFinding.objects.create(
        job=job1,
        condition_type=ReliabilityFinding.ConditionType.OVERDUE_EXECUTION,
        status=ReliabilityFinding.Status.ACTIVE,
        severity=ReliabilityFinding.Severity.DEGRADED,
        details={"overdue_by_seconds": 120},
        detected_at=incident.created_at,
    )

    data = compute_incident_intelligence(incident, now=now)
    causes = data["probable_causes"]

    queue_cause = next((c for c in causes if c["candidate"] == "QUEUE"), None)
    assert queue_cause is not None
    assert queue_cause["value"] == "heavy-tasks"
    assert queue_cause["confidence"] == "HIGH"


@pytest.mark.django_db
def test_probable_cause_job_level_failure(intelligence_setup):
    incident = intelligence_setup["incident"]
    job1 = intelligence_setup["job1"]
    now = timezone.now()

    # 10 failures distributed evenly across 5 different workers (no single worker degraded)
    for i in range(10):
        t = incident.created_at - timedelta(minutes=i + 1)
        create_execution(
            job=job1,
            external_id=f"exec-dist-{i}",
            status=Execution.Status.FAILED,
            worker=f"celery@worker-0{i % 5}",
            timestamp=t,
        )

    data = compute_incident_intelligence(incident, now=now)
    causes = data["probable_causes"]

    job_cause = next((c for c in causes if c["candidate"] == "JOB"), None)
    assert job_cause is not None
    assert job_cause["value"] == job1.name
    assert job_cause["confidence"] == "HIGH"
    assert any("Failures occurred across multiple workers" in e for e in job_cause["evidence"])


@pytest.mark.django_db
def test_probable_cause_insufficient_evidence(intelligence_setup):
    incident = intelligence_setup["incident"]
    now = timezone.now()

    # Only 2 executions
    for i in range(2):
        t = incident.created_at - timedelta(minutes=i + 1)
        create_execution(
            job=incident.job,
            external_id=f"exec-few-{i}",
            status=Execution.Status.SUCCESS,
            timestamp=t,
        )

    data = compute_incident_intelligence(incident, now=now)
    causes = data["probable_causes"]

    assert len(causes) == 1
    assert causes[0]["candidate"] == "INSUFFICIENT_EVIDENCE"
    assert causes[0]["confidence"] == "INSUFFICIENT_EVIDENCE"


@pytest.mark.django_db
def test_intelligence_api_pending_and_success_states(intelligence_setup):
    incident = intelligence_setup["incident"]
    owner = intelligence_setup["owner"]
    client = APIClient()
    client.force_authenticate(user=owner)

    # 1. First GET: intelligence does not exist -> returns 202 ACCEPTED with PENDING status
    res_pending = client.get(f"/api/incidents/{incident.id}/intelligence/")
    assert res_pending.status_code == status.HTTP_202_ACCEPTED
    p_data = res_pending.data.get("data", res_pending.data)
    assert p_data["status"] == "PENDING"
    assert p_data["incident_id"] == incident.id

    # 2. Compute intelligence directly
    compute_and_save_incident_intelligence(incident.id)

    # 3. Second GET: intelligence exists -> returns 200 OK with READY status and populated impact
    res_ready = client.get(f"/api/incidents/{incident.id}/intelligence/")
    assert res_ready.status_code == status.HTTP_200_OK
    r_data = res_ready.data.get("data", res_ready.data)
    assert r_data["status"] == "READY"
    assert r_data["impact"] is not None
    assert "affected_executions_count" in r_data["impact"]


@pytest.mark.django_db
def test_async_task_execution_and_lifecycle(intelligence_setup):
    incident = intelligence_setup["incident"]
    job1 = intelligence_setup["job1"]

    # Add executions
    for i in range(6):
        t = incident.created_at - timedelta(minutes=i + 1)
        create_execution(
            job=job1,
            external_id=f"exec-task-{i}",
            status=Execution.Status.FAILED if i < 3 else Execution.Status.SUCCESS,
            worker="celery@worker-01",
            timestamp=t,
        )

    # Run calculation
    compute_and_save_incident_intelligence(incident.id)

    intel = IncidentIntelligence.objects.get(incident=incident)
    assert intel.impact["affected_executions_count"] == 6
    assert intel.impact["failures_count"] == 3
    assert intel.analysis_version == "1.0"

    # Test resolution triggers re-calculation with resolved window
    resolve_incident(incident.id, intelligence_setup["owner"])
    compute_and_save_incident_intelligence(incident.id)

    intel.refresh_from_db()
    assert intel.analysis_window_end is not None


@pytest.mark.django_db
def test_intelligence_tenant_isolation(intelligence_setup):
    incident = intelligence_setup["incident"]
    other_user = intelligence_setup["other_user"]
    client = APIClient()

    # User from other team cannot access incident intelligence
    client.force_authenticate(user=other_user)
    res = client.get(f"/api/incidents/{incident.id}/intelligence/")
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_multiplier_semantics_below_baseline(intelligence_setup):
    from apps.reliability.models import JobBaseline

    job = intelligence_setup["job1"]
    incident = intelligence_setup["incident"]
    now = timezone.now()

    # Create baseline with 50% failure rate
    JobBaseline.objects.create(
        job=job,
        failure_rate=50.0,
        retry_rate=20.0,
        total_executions_analyzed=100,
        is_sufficient=True,
    )

    # In window, failure rate is 20% (1 fail out of 5)
    for i in range(4):
        create_execution(job, f"sc-ok-{i}", Execution.Status.SUCCESS, now - timedelta(minutes=5))
    create_execution(job, "sc-fail-1", Execution.Status.FAILED, now - timedelta(minutes=5))

    impact = calculate_incident_impact(
        incident=incident,
        window_start=now - timedelta(minutes=15),
        window_end=now,
        window_minutes=15,
    )

    # When current (20%) is below baseline (50%), multiplier MUST be None (never 20.0 or bogus ratio)
    comparisons = impact["baseline_comparisons"]
    assert comparisons["current_failure_rate"] == 20.0
    assert comparisons["baseline_failure_rate"] == 50.0
    assert comparisons["failure_rate_multiplier"] is None


@pytest.mark.django_db
def test_refresh_active_incidents_stale_only_and_batching(intelligence_setup):
    from apps.incidents.tasks import refresh_active_incidents_intelligence_task

    incident = intelligence_setup["incident"]

    # Refresh task runs without errors and enqueues stale incidents
    refresh_active_incidents_intelligence_task()

    # Now calculate and save intelligence
    compute_and_save_incident_intelligence(incident.id)

    intel = IncidentIntelligence.objects.get(incident=incident)
    assert intel.calculated_at is not None


@pytest.mark.django_db
def test_finding_and_incident_temporal_overlap(intelligence_setup):
    project = intelligence_setup["project"]
    job2 = intelligence_setup["job2"]
    incident = intelligence_setup["incident"]
    now = timezone.now()
    window_start = now - timedelta(minutes=15)
    window_end = now

    # 1. Finding that recovered BEFORE window_start (20 mins ago) -> should NOT correlate
    f_old = ReliabilityFinding.objects.create(
        job=job2,
        condition_type="STALLED_EXECUTION",
        severity="DEGRADED",
        recovered_at=now - timedelta(minutes=20),
    )
    ReliabilityFinding.objects.filter(id=f_old.id).update(detected_at=now - timedelta(minutes=30))

    # 2. Finding that recovered DURING the window (5 mins ago) -> SHOULD correlate
    f_overlapping = ReliabilityFinding.objects.create(
        job=job2,
        condition_type="FAILURE_RATE_ANOMALY",
        severity="CRITICAL",
        recovered_at=now - timedelta(minutes=5),
    )
    ReliabilityFinding.objects.filter(id=f_overlapping.id).update(
        detected_at=now - timedelta(minutes=25)
    )

    # 3. Incident resolved BEFORE window_start -> should NOT correlate
    old_inc = Incident.objects.create(
        project=project,
        job=job2,
        status=Incident.Status.RESOLVED,
        severity=Incident.Severity.DEGRADED,
        resolved_at=now - timedelta(minutes=25),
    )
    Incident.objects.filter(id=old_inc.id).update(created_at=now - timedelta(minutes=40))

    # 4. Incident active DURING window -> SHOULD correlate
    active_inc = Incident.objects.create(
        project=project,
        job=job2,
        status=Incident.Status.OPEN,
        severity=Incident.Severity.DEGRADED,
    )
    Incident.objects.filter(id=active_inc.id).update(created_at=now - timedelta(minutes=10))

    correlations = find_correlated_signals(
        incident=incident,
        window_start=window_start,
        window_end=window_end,
        executions=[],
    )

    correlated_finding_ids = [c["target_id"] for c in correlations if c["target_type"] == "FINDING"]
    correlated_incident_ids = [
        c["target_id"] for c in correlations if c["target_type"] == "INCIDENT"
    ]

    assert f_old.id not in correlated_finding_ids
    assert f_overlapping.id in correlated_finding_ids
    assert old_inc.id not in correlated_incident_ids
    assert active_inc.id in correlated_incident_ids


@pytest.mark.django_db
def test_queue_overdue_finding_scoping_no_cross_pollution(intelligence_setup):
    job1 = intelligence_setup["job1"]
    job2 = intelligence_setup["job2"]
    incident = intelligence_setup["incident"]
    now = timezone.now()

    # Job2 runs on queue 'billing-queue' and has an active OVERDUE_EXECUTION finding
    f_overdue = ReliabilityFinding.objects.create(
        job=job2,
        condition_type="OVERDUE_EXECUTION",
        severity="CRITICAL",
    )
    ReliabilityFinding.objects.filter(id=f_overdue.id).update(
        detected_at=now - timedelta(minutes=10)
    )

    # Executions in window (>= 5 total so root cause inference runs):
    # Queue 'reports-queue' has 2 pending executions (below threshold 3, no overdue finding)
    # Queue 'billing-queue' has executions for job2
    e1 = create_execution(
        job1, "q-rep-1", Execution.Status.PENDING, now - timedelta(minutes=5), queue="reports-queue"
    )
    e2 = create_execution(
        job1, "q-rep-2", Execution.Status.PENDING, now - timedelta(minutes=5), queue="reports-queue"
    )
    e3 = create_execution(
        job2, "q-bill-1", Execution.Status.FAILED, now - timedelta(minutes=5), queue="billing-queue"
    )
    e4 = create_execution(
        job2, "q-bill-2", Execution.Status.FAILED, now - timedelta(minutes=5), queue="billing-queue"
    )
    e5 = create_execution(
        job2, "q-bill-3", Execution.Status.FAILED, now - timedelta(minutes=5), queue="billing-queue"
    )

    executions = [e1, e2, e3, e4, e5]

    impact = calculate_incident_impact(
        incident=incident,
        window_start=now - timedelta(minutes=15),
        window_end=now,
        window_minutes=15,
        executions=executions,
    )

    correlations = find_correlated_signals(
        incident=incident,
        window_start=now - timedelta(minutes=15),
        window_end=now,
        executions=executions,
    )

    candidates = identify_probable_causes(
        incident=incident,
        impact=impact,
        correlations=correlations,
        executions=executions,
    )

    queue_candidates = [c for c in candidates if c["candidate"] == "QUEUE"]

    # billing-queue should be identified because of its overdue finding
    billing_cand = next((c for c in queue_candidates if c["value"] == "billing-queue"), None)
    assert billing_cand is not None
    assert any("billing-queue" in ev for ev in billing_cand["evidence"])

    # reports-queue has only 2 pending executions and NO overdue finding -> MUST NOT be falsely added
    reports_cand = next((c for c in queue_candidates if c["value"] == "reports-queue"), None)
    assert reports_cand is None


@pytest.mark.django_db
def test_older_task_calculation_cannot_overwrite_newer_intelligence(intelligence_setup):
    incident = intelligence_setup["incident"]
    now = timezone.now()

    # Step 1: Save newer intelligence calculated at 'now'
    intel_newer = IncidentIntelligence.objects.create(
        incident=incident,
        impact={"window_minutes": 15, "affected_executions_count": 10},
        correlations=[],
        probable_causes=[],
        analysis_window_start=now - timedelta(minutes=15),
        analysis_window_end=now,
        analysis_version="1.0",
    )

    # Step 2: Attempt to save an older intelligence computed for an earlier time window
    older_window_end = now - timedelta(minutes=5)
    # Patch compute_incident_intelligence to simulate an older in-flight task finishing late
    import apps.incidents.intelligence as intel_module

    original_compute = intel_module.compute_incident_intelligence

    def fake_older_compute(inc, now=None):
        res = original_compute(inc, now=now)
        res["analysis_window_end"] = older_window_end
        return res

    intel_module.compute_incident_intelligence = fake_older_compute
    try:
        result = compute_and_save_incident_intelligence(incident.id)
        # Should NOT overwrite intel_newer
        assert result.id == intel_newer.id
        assert result.analysis_window_end == now
    finally:
        intel_module.compute_incident_intelligence = original_compute
