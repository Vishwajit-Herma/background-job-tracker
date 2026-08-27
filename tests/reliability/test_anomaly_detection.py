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
from apps.reliability.models import JobBaseline, JobExpectation, ReliabilityFinding
from apps.reliability.services import (
    calculate_job_baseline,
    compute_adaptive_thresholds,
    get_job_reliability_overview,
)
from apps.reliability.evaluators import (
    evaluate_job_reliability,
)


@pytest.fixture
def anomaly_test_setup(db):
    User = get_user_model()
    owner = User.objects.create(email="anomaly_owner@example.com")
    owner.set_password("pass123")
    owner.save()

    member_user = User.objects.create(email="anomaly_member@example.com")
    member_user.set_password("pass123")
    member_user.save()

    other_user = User.objects.create(email="other_anomaly_user@example.com")
    other_user.set_password("pass123")
    other_user.save()

    team = Team.objects.create(name="Anomaly Team", slug="anomaly-team", owner=owner)
    TeamMember.objects.create(team=team, user=member_user, role="member", is_active=True)

    other_team = Team.objects.create(name="Other Team", slug="other-team", owner=other_user)

    project = Project.objects.create(team=team, name="Anomaly Project")
    job = Job.objects.create(
        project=project, name="Payment Processing", task_identifier="tasks.process_payment"
    )

    other_project = Project.objects.create(team=other_team, name="Other Project")
    other_job = Job.objects.create(
        project=other_project, name="Other Task", task_identifier="tasks.other"
    )

    return {
        "owner": owner,
        "member_user": member_user,
        "other_user": other_user,
        "team": team,
        "other_team": other_team,
        "project": project,
        "job": job,
        "other_job": other_job,
    }


@pytest.mark.django_db
def test_baseline_metrics_use_same_sample_window(anomaly_test_setup):
    job = anomaly_test_setup["job"]
    base_time = timezone.now() - timedelta(days=2)

    # 10 executions in 7-day window: 8 success (100ms), 2 failed (20% failure), 1 retried (10% retry)
    for i in range(10):
        t = base_time + timedelta(seconds=i * 60)
        status = Execution.Status.FAILED if i < 2 else Execution.Status.SUCCESS
        retry_count = 1 if i == 2 else 0
        Execution.objects.create(
            job=job,
            external_id=f"exec-baseline-{i}",
            status=status,
            retry_count=retry_count,
            duration_ms=100,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    baseline = calculate_job_baseline(job, sample_window_days=7)
    assert baseline.is_sufficient is True
    assert baseline.total_executions_analyzed == 10
    assert baseline.failure_rate == 20.0
    assert baseline.retry_rate == 10.0
    # 10 executions over 7 days (168 hours) -> 10 / 168 = 0.06
    assert baseline.avg_hourly_volume == 0.06
    assert baseline.p95_runtime_ms == 100.0


@pytest.mark.django_db
def test_normal_behavior_no_anomaly(anomaly_test_setup):
    job = anomaly_test_setup["job"]
    now = timezone.now()

    # Pre-create baseline: failure_rate=2.0%, retry_rate=2.0%, p95=100ms, avg_hourly_volume=10.0
    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=100,
        is_sufficient=True,
        failure_rate=2.0,
        retry_rate=2.0,
        p95_runtime_ms=100.0,
        avg_hourly_volume=10.0,
    )

    # Current 60-min window: 10 executions, all successful, 100ms duration
    for i in range(10):
        t = now - timedelta(minutes=5 * i + 1)
        Execution.objects.create(
            job=job,
            external_id=f"exec-normal-{i}",
            status=Execution.Status.SUCCESS,
            retry_count=0,
            duration_ms=100,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    evaluate_job_reliability(job.id)

    findings = ReliabilityFinding.objects.filter(
        job=job,
        status=ReliabilityFinding.Status.ACTIVE,
    )
    assert findings.count() == 0


@pytest.mark.django_db
def test_failure_rate_anomaly_detection_and_evidence(anomaly_test_setup):
    job = anomaly_test_setup["job"]
    now = timezone.now()

    # Baseline failure rate = 1.2%
    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=500,
        is_sufficient=True,
        failure_rate=1.2,
        retry_rate=0.5,
        p95_runtime_ms=100.0,
        avg_hourly_volume=20.0,
    )

    # Current window: 20 executions with 5 failures -> 25.0% failure rate (> 3x baseline and delta > 5%)
    for i in range(20):
        t = now - timedelta(minutes=2 * i + 1)
        status = Execution.Status.FAILED if i < 5 else Execution.Status.SUCCESS
        Execution.objects.create(
            job=job,
            external_id=f"exec-fr-{i}",
            status=status,
            duration_ms=100,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    evaluate_job_reliability(job.id)

    finding = ReliabilityFinding.objects.get(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.FAILURE_RATE_ANOMALY,
        status=ReliabilityFinding.Status.ACTIVE,
    )
    assert finding.severity == ReliabilityFinding.Severity.DEGRADED
    assert finding.details["metric_type"] == "FAILURE_RATE"
    assert finding.details["current_value"] == 25.0
    assert finding.details["baseline_value"] == 1.2
    assert finding.details["deviation_ratio"] >= 3.0
    assert finding.details["sample_count"] == 20
    assert finding.details["observation_window_minutes"] == 60


@pytest.mark.django_db
def test_rate_anomaly_guarded_against_small_delta(anomaly_test_setup):
    job = anomaly_test_setup["job"]
    now = timezone.now()

    # Baseline failure rate = 0.1%
    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=1000,
        is_sufficient=True,
        failure_rate=0.1,
        retry_rate=0.1,
        p95_runtime_ms=100.0,
        avg_hourly_volume=50.0,
    )

    # Current window: 100 executions with 1 failure -> 1.0% failure rate
    # Ratio is 1.0 / 1.0 = 1.0x (clamped floor) or 10x relative, BUT delta is 1.0 - 0.1 = 0.9% < 5.0% guard
    for i in range(100):
        t = now - timedelta(seconds=30 * i + 1)
        status = Execution.Status.FAILED if i == 0 else Execution.Status.SUCCESS
        Execution.objects.create(
            job=job,
            external_id=f"exec-small-delta-{i}",
            status=status,
            duration_ms=100,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    evaluate_job_reliability(job.id)

    assert not ReliabilityFinding.objects.filter(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.FAILURE_RATE_ANOMALY,
        status=ReliabilityFinding.Status.ACTIVE,
    ).exists()


@pytest.mark.django_db
def test_retry_rate_anomaly_detection(anomaly_test_setup):
    job = anomaly_test_setup["job"]
    now = timezone.now()

    # Baseline retry rate = 1.0%
    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=500,
        is_sufficient=True,
        failure_rate=1.0,
        retry_rate=1.0,
        p95_runtime_ms=100.0,
        avg_hourly_volume=20.0,
    )

    # Current window: 10 executions, 5 retried -> 50.0% retry rate (delta = 49% >= 5%, ratio = 50x >= 3x)
    for i in range(10):
        t = now - timedelta(minutes=3 * i + 1)
        retry_count = 2 if i < 5 else 0
        Execution.objects.create(
            job=job,
            external_id=f"exec-rr-{i}",
            status=Execution.Status.SUCCESS,
            retry_count=retry_count,
            duration_ms=100,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    evaluate_job_reliability(job.id)

    finding = ReliabilityFinding.objects.get(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.RETRY_RATE_ANOMALY,
        status=ReliabilityFinding.Status.ACTIVE,
    )
    assert finding.details["current_value"] == 50.0
    assert finding.details["baseline_value"] == 1.0


@pytest.mark.django_db
def test_duration_p95_anomaly_detection(anomaly_test_setup):
    job = anomaly_test_setup["job"]
    now = timezone.now()

    # Baseline P95 duration = 200ms
    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=200,
        is_sufficient=True,
        failure_rate=0.0,
        retry_rate=0.0,
        p95_runtime_ms=200.0,
        avg_hourly_volume=10.0,
    )

    # Current window: 10 completed executions with duration = 1500ms
    # Ratio = 1500 / 200 = 7.5x >= 2.5x, Delta = 1300ms >= 1000ms
    for i in range(10):
        t = now - timedelta(minutes=4 * i + 1)
        Execution.objects.create(
            job=job,
            external_id=f"exec-dur-{i}",
            status=Execution.Status.SUCCESS,
            duration_ms=1500,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    evaluate_job_reliability(job.id)

    finding = ReliabilityFinding.objects.get(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.DURATION_ANOMALY,
        status=ReliabilityFinding.Status.ACTIVE,
    )
    assert finding.details["current_value"] == 1500.0
    assert finding.details["baseline_value"] == 200.0
    assert finding.details["deviation_ratio"] == 7.5


@pytest.mark.django_db
def test_volume_surge_and_drop_anomaly(anomaly_test_setup):
    job = anomaly_test_setup["job"]
    now = timezone.now()

    # Baseline volume = 10 executions/hr
    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=1000,
        is_sufficient=True,
        failure_rate=0.0,
        retry_rate=0.0,
        p95_runtime_ms=100.0,
        avg_hourly_volume=10.0,
    )

    # Surge test: 50 executions in 60m window (50 / 10 = 5.0x >= 4.0x)
    for i in range(50):
        t = now - timedelta(seconds=60 * i + 1)
        Execution.objects.create(
            job=job,
            external_id=f"exec-vol-{i}",
            status=Execution.Status.SUCCESS,
            duration_ms=100,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    evaluate_job_reliability(job.id)

    finding = ReliabilityFinding.objects.get(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.EXECUTION_VOLUME_ANOMALY,
        status=ReliabilityFinding.Status.ACTIVE,
    )
    assert finding.details["current_value"] == 50
    assert finding.details["baseline_value"] == 10.0
    assert finding.details["deviation_ratio"] == 5.0


@pytest.mark.django_db
def test_volume_anomaly_skips_when_baseline_volume_low(anomaly_test_setup):
    job = anomaly_test_setup["job"]

    # Baseline volume = 1.0/hr (< MIN_VOLUME_BASELINE_HOURLY 5.0)
    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=20,
        is_sufficient=True,
        failure_rate=0.0,
        retry_rate=0.0,
        p95_runtime_ms=100.0,
        avg_hourly_volume=1.0,
    )

    # 0 executions in current window -> should not trigger volume drop anomaly for low-volume jobs
    evaluate_job_reliability(job.id)

    assert not ReliabilityFinding.objects.filter(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.EXECUTION_VOLUME_ANOMALY,
        status=ReliabilityFinding.Status.ACTIVE,
    ).exists()


@pytest.mark.django_db
def test_insufficient_baseline_skips_anomaly(anomaly_test_setup):
    job = anomaly_test_setup["job"]
    now = timezone.now()

    # Baseline is_sufficient = False
    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=2,
        is_sufficient=False,
        failure_rate=0.0,
        retry_rate=0.0,
        p95_runtime_ms=100.0,
        avg_hourly_volume=1.0,
    )

    # 10 executions all failing in current window
    for i in range(10):
        t = now - timedelta(minutes=i + 1)
        Execution.objects.create(
            job=job,
            external_id=f"exec-insufficient-{i}",
            status=Execution.Status.FAILED,
            duration_ms=100,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    evaluate_job_reliability(job.id)

    # No anomaly finding should be created because baseline is insufficient
    assert not ReliabilityFinding.objects.filter(
        job=job,
        status=ReliabilityFinding.Status.ACTIVE,
    ).exists()


@pytest.mark.django_db
def test_small_current_window_sample_size_skips_anomaly(anomaly_test_setup):
    job = anomaly_test_setup["job"]
    now = timezone.now()

    # Baseline is sufficient
    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=100,
        is_sufficient=True,
        failure_rate=1.0,
        retry_rate=1.0,
        p95_runtime_ms=100.0,
        avg_hourly_volume=10.0,
    )

    # Current window has only 2 executions (both failed). Sample count < MIN_RATE_SAMPLE_COUNT (5)
    for i in range(2):
        t = now - timedelta(minutes=i + 1)
        Execution.objects.create(
            job=job,
            external_id=f"exec-small-sample-{i}",
            status=Execution.Status.FAILED,
            duration_ms=100,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    evaluate_job_reliability(job.id)

    assert not ReliabilityFinding.objects.filter(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.FAILURE_RATE_ANOMALY,
        status=ReliabilityFinding.Status.ACTIVE,
    ).exists()


@pytest.mark.django_db
def test_observation_window_with_zero_executions(anomaly_test_setup):
    job = anomaly_test_setup["job"]

    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=100,
        is_sufficient=True,
        failure_rate=1.0,
        retry_rate=1.0,
        p95_runtime_ms=100.0,
        avg_hourly_volume=1.0,
    )

    # 0 executions in current window evaluated without exception
    evaluate_job_reliability(job.id)
    overview = get_job_reliability_overview(job)
    assert overview["behavior_comparison"]["sample_count"] == 0


@pytest.mark.django_db
def test_adaptive_threshold_calculation_and_clamping():
    # 1. Very low baseline -> clamped to min bounds (5.0%)
    low_baseline = JobBaseline(
        is_sufficient=True,
        failure_rate=0.5,
        retry_rate=0.2,
        p95_runtime_ms=100.0,
    )
    thresh_low = compute_adaptive_thresholds(low_baseline)
    assert thresh_low["failure_rate"] == 5.0
    assert thresh_low["retry_rate"] == 5.0
    assert (
        thresh_low["p95_duration_ms"] == 1100.0
    )  # 100 * 2 = 200, clamped to min 100 + 1000 = 1100

    # 2. Moderate baseline -> multiplied normally
    mod_baseline = JobBaseline(
        is_sufficient=True,
        failure_rate=5.0,
        retry_rate=4.0,
        p95_runtime_ms=2000.0,
    )
    thresh_mod = compute_adaptive_thresholds(mod_baseline)
    assert thresh_mod["failure_rate"] == 15.0  # 5 * 3
    assert thresh_mod["retry_rate"] == 12.0  # 4 * 3
    assert thresh_mod["p95_duration_ms"] == 4000.0  # 2000 * 2 = 4000 (between 3000 and 20000)

    # 3. High baseline -> clamped to max bounds (50.0%)
    high_baseline = JobBaseline(
        is_sufficient=True,
        failure_rate=25.0,
        retry_rate=20.0,
        p95_runtime_ms=2000.0,
    )
    thresh_high = compute_adaptive_thresholds(high_baseline)
    assert thresh_high["failure_rate"] == 50.0  # clamped from 75 to 50
    assert thresh_high["retry_rate"] == 50.0  # clamped from 60 to 50

    # 4. Small baseline P95 bound safety (prevents lower bound > upper bound inversion):
    # base_p95 = 100ms
    # raw min_bound = 100 + 1000 = 1100ms
    # raw base_p95 * 10 = 1000ms
    # max_bound = max(1000, 1100) = 1100ms (ensures max_bound >= min_bound)
    # calculated = 200ms -> clamped to 1100.0ms
    small_p95_baseline = JobBaseline(
        is_sufficient=True,
        failure_rate=2.0,
        retry_rate=1.0,
        p95_runtime_ms=100.0,
    )
    thresh_small = compute_adaptive_thresholds(small_p95_baseline)
    assert thresh_small["p95_duration_ms"] == 1100.0


@pytest.mark.django_db
def test_simultaneous_missed_and_anomaly_findings(anomaly_test_setup):
    job = anomaly_test_setup["job"]
    now = timezone.now()

    # Configure expectation: interval = 60s, grace = 0s
    JobExpectation.objects.create(
        job=job,
        expected_interval_seconds=60,
        grace_period_seconds=0,
        is_enabled=True,
    )
    # Baseline
    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=500,
        is_sufficient=True,
        failure_rate=1.0,
        retry_rate=1.0,
        p95_runtime_ms=100.0,
        avg_hourly_volume=10.0,
    )

    # Last execution was 10 minutes ago, and recent window had 10 failed runs (anomalous failure rate)
    for i in range(10):
        t = now - timedelta(minutes=15 + i)
        Execution.objects.create(
            job=job,
            external_id=f"exec-simul-{i}",
            status=Execution.Status.FAILED,
            duration_ms=100,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    # Evaluate missed and anomaly findings automatically
    evaluate_job_reliability(job.id)

    overview = get_job_reliability_overview(job)

    # Strict state precedence: MISSED > ANOMALOUS
    assert overview["current_state"] == "MISSED"
    # But both findings are preserved in active_findings and active_anomalies
    finding_types = {f.condition_type for f in overview["active_findings"]}
    assert ReliabilityFinding.ConditionType.MISSED_EXECUTION in finding_types
    assert ReliabilityFinding.ConditionType.FAILURE_RATE_ANOMALY in finding_types
    assert len(overview["active_anomalies"]) == 1


@pytest.mark.django_db
def test_simultaneous_stalled_and_anomaly_findings(anomaly_test_setup):
    job = anomaly_test_setup["job"]

    JobExpectation.objects.create(
        job=job,
        max_runtime_seconds=30,
        is_enabled=True,
    )

    # Stalled execution
    stalled_exec = Execution.objects.create(
        job=job,
        external_id="exec-stalled-simul",
        status=Execution.Status.RUNNING,
        started_at=timezone.now() - timedelta(minutes=10),
        last_event_at=timezone.now() - timedelta(minutes=10),
        created_at=timezone.now() - timedelta(minutes=10),
    )

    ReliabilityFinding.objects.create(
        job=job,
        execution=stalled_exec,
        condition_type=ReliabilityFinding.ConditionType.STALLED_EXECUTION,
        status=ReliabilityFinding.Status.ACTIVE,
        severity=ReliabilityFinding.Severity.CRITICAL,
    )

    ReliabilityFinding.objects.create(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.DURATION_ANOMALY,
        status=ReliabilityFinding.Status.ACTIVE,
        severity=ReliabilityFinding.Severity.DEGRADED,
    )

    overview = get_job_reliability_overview(job)

    # STALLED > ANOMALOUS
    assert overview["current_state"] == "STALLED"
    assert len(overview["active_findings"]) == 2
    assert len(overview["active_anomalies"]) == 1


@pytest.mark.django_db
def test_repeated_anomaly_evaluation_idempotency(anomaly_test_setup):
    job = anomaly_test_setup["job"]
    now = timezone.now()

    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=500,
        is_sufficient=True,
        failure_rate=1.0,
        retry_rate=1.0,
        p95_runtime_ms=100.0,
        avg_hourly_volume=10.0,
    )

    for i in range(10):
        t = now - timedelta(minutes=2 * i + 1)
        Execution.objects.create(
            job=job,
            external_id=f"exec-idem-{i}",
            status=Execution.Status.FAILED,
            duration_ms=100,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    # Run evaluation multiple times
    evaluate_job_reliability(job.id)
    evaluate_job_reliability(job.id)
    evaluate_job_reliability(job.id)

    # Exactly 1 active finding must exist
    findings = ReliabilityFinding.objects.filter(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.FAILURE_RATE_ANOMALY,
        status=ReliabilityFinding.Status.ACTIVE,
    )
    assert findings.count() == 1


@pytest.mark.django_db
def test_anomaly_recovery_and_incident_auto_resolve(anomaly_test_setup):
    job = anomaly_test_setup["job"]
    project = anomaly_test_setup["project"]
    now = timezone.now()

    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=500,
        is_sufficient=True,
        failure_rate=1.0,
        retry_rate=1.0,
        p95_runtime_ms=100.0,
        avg_hourly_volume=10.0,
    )

    # Create matching smart alert rule
    AlertRule.objects.create(
        project=project,
        job=job,
        metric=AlertRule.MetricType.FAILURE_RATE_ANOMALY,
        severity=AlertRule.Severity.CRITICAL,
        is_active=True,
    )

    # Step 1: Anomalous condition (10 failures)
    for i in range(10):
        t = now - timedelta(minutes=2 * i + 1)
        Execution.objects.create(
            job=job,
            external_id=f"exec-rec-fail-{i}",
            status=Execution.Status.FAILED,
            duration_ms=100,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    evaluate_job_reliability(job.id)

    finding = ReliabilityFinding.objects.get(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.FAILURE_RATE_ANOMALY,
        status=ReliabilityFinding.Status.ACTIVE,
    )
    assert finding.incident is not None
    incident = finding.incident
    assert incident.status == Incident.Status.OPEN
    assert incident.severity == Incident.Severity.CRITICAL

    # Step 2: Anomaly resolves (delete old failures and add healthy executions to drop failure rate to 0%)
    Execution.objects.filter(job=job).delete()
    for i in range(20):
        t = now - timedelta(minutes=i + 1)
        Execution.objects.create(
            job=job,
            external_id=f"exec-rec-succ-{i}",
            status=Execution.Status.SUCCESS,
            duration_ms=100,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    evaluate_job_reliability(job.id)

    finding.refresh_from_db()
    assert finding.status == ReliabilityFinding.Status.RECOVERED
    assert finding.recovered_at is not None

    incident.refresh_from_db()
    assert incident.status == Incident.Status.RESOLVED
    assert incident.resolution_type == Incident.ResolutionType.AUTOMATIC


@pytest.mark.django_db
def test_anomaly_alert_rule_escalation_to_incident(anomaly_test_setup):
    job = anomaly_test_setup["job"]
    project = anomaly_test_setup["project"]
    now = timezone.now()

    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=500,
        is_sufficient=True,
        failure_rate=1.0,
        retry_rate=1.0,
        p95_runtime_ms=100.0,
        avg_hourly_volume=10.0,
    )

    alert_rule = AlertRule.objects.create(
        project=project,
        job=job,
        metric=AlertRule.MetricType.DURATION_ANOMALY,
        severity=AlertRule.Severity.CRITICAL,
        is_active=True,
    )

    # 10 executions at 3000ms duration (baseline=100ms -> 30x)
    for i in range(10):
        t = now - timedelta(minutes=i + 1)
        Execution.objects.create(
            job=job,
            external_id=f"exec-dur-inc-{i}",
            status=Execution.Status.SUCCESS,
            duration_ms=3000,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    evaluate_job_reliability(job.id)

    finding = ReliabilityFinding.objects.get(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.DURATION_ANOMALY,
        status=ReliabilityFinding.Status.ACTIVE,
    )
    assert finding.incident is not None
    assert finding.incident.alert_rule_id == alert_rule.id
    assert finding.incident.severity == Incident.Severity.CRITICAL
    assert finding.incident.trigger_metadata["metric_value"] == 3000.0
    assert finding.incident.trigger_metadata["current_value"] == 3000.0
    assert finding.incident.trigger_metadata["baseline_value"] == 100.0


@pytest.mark.django_db
def test_anomaly_does_not_create_incident_without_matching_alert_rule(anomaly_test_setup):
    job = anomaly_test_setup["job"]
    now = timezone.now()

    JobBaseline.objects.create(
        job=job,
        sample_window_days=7,
        total_executions_analyzed=500,
        is_sufficient=True,
        failure_rate=1.0,
        retry_rate=1.0,
        p95_runtime_ms=100.0,
        avg_hourly_volume=10.0,
    )

    # No AlertRule created for job or project

    for i in range(10):
        t = now - timedelta(minutes=i + 1)
        Execution.objects.create(
            job=job,
            external_id=f"exec-no-rule-{i}",
            status=Execution.Status.FAILED,
            duration_ms=100,
            started_at=t,
            last_event_at=t,
            created_at=t,
        )

    evaluate_job_reliability(job.id)

    finding = ReliabilityFinding.objects.get(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.FAILURE_RATE_ANOMALY,
        status=ReliabilityFinding.Status.ACTIVE,
    )
    assert finding.severity == ReliabilityFinding.Severity.DEGRADED
    assert finding.incident is None
    assert Incident.objects.filter(job=job).count() == 0


@pytest.mark.django_db
def test_anomaly_alert_rule_without_threshold(anomaly_test_setup):
    project = anomaly_test_setup["project"]
    job = anomaly_test_setup["job"]
    client = APIClient()
    client.force_authenticate(user=anomaly_test_setup["owner"])

    # Create anomaly rule without threshold via API
    response = client.post(
        "/api/alerts/rules/",
        {
            "project": project.id,
            "job": job.id,
            "metric": "FAILURE_RATE_ANOMALY",
            "severity": "CRITICAL",
        },
        format="json",
    )
    assert response.status_code == 201
    res_data = response.data.get("data", response.data)
    assert res_data["metric"] == "FAILURE_RATE_ANOMALY"
    assert res_data["threshold"] == 0.0


@pytest.mark.django_db
def test_tenant_isolation_in_anomaly_detection(anomaly_test_setup):
    client = APIClient()
    # Member of team cannot access other_job's reliability overview
    client.force_authenticate(user=anomaly_test_setup["member_user"])
    other_job = anomaly_test_setup["other_job"]

    res = client.get(f"/api/jobs/{other_job.id}/reliability/")
    assert res.status_code in [403, 404]
