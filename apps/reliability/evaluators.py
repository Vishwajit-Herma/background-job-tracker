import logging
from datetime import timedelta
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.db.models import F

from apps.jobs.models import Job
from apps.executions.models import Execution
from apps.alerts.models import AlertRule
from apps.incidents.models import Incident
from apps.incidents.services import auto_resolve_incident, create_incident
from apps.reliability.models import ReliabilityFinding

logger = logging.getLogger(__name__)


def evaluate_all_jobs_reliability():
    """
    Finds all active jobs and evaluates their reliability status.
    Uses short per-job transactions to avoid long table locks.
    """
    job_ids = Job.objects.filter(
        status="active",
        is_deleted=False,
        project__status="active",
        project__is_deleted=False,
    ).values_list("id", flat=True)

    evaluated_count = 0
    for job_id in job_ids:
        try:
            evaluate_job_reliability(job_id)
            evaluated_count += 1
        except Exception as e:
            logger.exception("Error evaluating reliability for job %s: %s", job_id, e)

    return evaluated_count


def evaluate_job_reliability(job_id):
    """
    Evaluates reliability conditions (Missed, Stalled, Overdue) for a single job
    inside a locked atomic transaction.
    """
    with transaction.atomic():
        try:
            job = (
                Job.objects.select_for_update()
                .select_related("project")
                .get(
                    id=job_id,
                    status="active",
                    is_deleted=False,
                    project__status="active",
                    project__is_deleted=False,
                )
            )
        except Job.DoesNotExist:
            return

        now = timezone.now()

        expectation = getattr(job, "expectation", None)
        if expectation and not expectation.is_enabled:
            # Cleanly recover any active findings and auto-resolve associated incidents when disabled
            active_findings = ReliabilityFinding.objects.filter(
                job=job, status=ReliabilityFinding.Status.ACTIVE
            )
            for finding in active_findings:
                _recover_finding(
                    finding,
                    {
                        "condition_type": finding.condition_type,
                        "recovered_at": now.isoformat(),
                        "reason": "Reliability evaluation disabled for job",
                    },
                )
            return

        baseline = getattr(job, "baseline", None)

        # 1. Detect Missed Executions (scheduled run did not occur)
        detect_missed_execution(job, expectation, baseline, now)

        # 2. Detect Stalled (running too long) and Overdue (pending too long) Executions
        detect_stalled_and_overdue_executions(job, expectation, baseline, now)


def detect_missed_execution(job, expectation, baseline, now):
    """
    Checks if a job has missed its expected execution cadence.
    Uses explicit execution-occurrence timestamp (started_at or created_at).
    """
    expected_interval = None
    if expectation and expectation.expected_interval_seconds:
        expected_interval = expectation.expected_interval_seconds
    elif baseline and baseline.is_sufficient and baseline.median_interval_seconds:
        expected_interval = int(baseline.median_interval_seconds)

    if not expected_interval:
        # Without an expected interval from expectation or baseline, we cannot determine if missed.
        return

    grace_period = expectation.grace_period_seconds if expectation else 0

    latest_exec = (
        Execution.objects.filter(job=job)
        .order_by(F("started_at").desc(nulls_last=True), "-created_at")
        .first()
    )

    last_occurrence_at = (
        latest_exec.started_at or latest_exec.created_at if latest_exec else job.created_at
    )
    threshold = last_occurrence_at + timedelta(seconds=expected_interval + grace_period)

    active_finding = ReliabilityFinding.objects.filter(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.MISSED_EXECUTION,
        status=ReliabilityFinding.Status.ACTIVE,
        execution__isnull=True,
    ).first()

    if now > threshold:
        overdue_by_seconds = int((now - threshold).total_seconds())
        details = {
            "expected_interval_seconds": expected_interval,
            "grace_period_seconds": grace_period,
            "last_occurrence_at": last_occurrence_at.isoformat(),
            "threshold_at": threshold.isoformat(),
            "overdue_by_seconds": overdue_by_seconds,
        }

        if not active_finding:
            try:
                with transaction.atomic():
                    finding = ReliabilityFinding.objects.create(
                        job=job,
                        condition_type=ReliabilityFinding.ConditionType.MISSED_EXECUTION,
                        status=ReliabilityFinding.Status.ACTIVE,
                        severity=ReliabilityFinding.Severity.DEGRADED,
                        details=details,
                    )
                    _link_or_create_incident(
                        finding, AlertRule.MetricType.MISSED_EXECUTION, details
                    )
            except IntegrityError:
                pass
        else:
            active_finding.details = details
            active_finding.last_evaluated_at = now
            active_finding.save(update_fields=["details", "last_evaluated_at"])
    else:
        # Job has executed on time; mark schedule recovered
        if active_finding:
            _recover_finding(
                active_finding,
                {
                    "condition_type": ReliabilityFinding.ConditionType.MISSED_EXECUTION,
                    "recovered_at": now.isoformat(),
                    "reason": "schedule_resumed",
                    "recovered_by_execution_id": latest_exec.id if latest_exec else None,
                },
            )


def detect_stalled_and_overdue_executions(job, expectation, baseline, now):
    """
    Checks for in-progress executions:
    - STALLED: RUNNING longer than allowed (max_runtime_seconds)
    - OVERDUE: PENDING queued longer than allowed (max_queue_delay_seconds)
    Strictly configuration-driven for queue delay; does not trigger unless configured.
    """
    max_runtime = None
    if expectation and expectation.max_runtime_seconds:
        max_runtime = expectation.max_runtime_seconds
    elif baseline and baseline.is_sufficient and baseline.p95_runtime_ms:
        max_runtime = int(max(1, round(baseline.p95_runtime_ms / 1000 * 1.5)))

    # Only evaluate queue delay if explicitly configured on expectation
    max_queue_delay = (
        expectation.max_queue_delay_seconds
        if (expectation and expectation.max_queue_delay_seconds is not None)
        else None
    )

    in_progress = Execution.objects.filter(
        job=job,
        status__in=[Execution.Status.RUNNING, Execution.Status.PENDING],
    )

    current_stalled_execution_ids = set()
    current_overdue_execution_ids = set()

    for exec_obj in in_progress:
        if exec_obj.status == Execution.Status.RUNNING and max_runtime and exec_obj.started_at:
            runtime_seconds = (now - exec_obj.started_at).total_seconds()
            if runtime_seconds > max_runtime:
                current_stalled_execution_ids.add(exec_obj.id)
                details = {
                    "execution_id": exec_obj.id,
                    "external_id": exec_obj.external_id,
                    "started_at": exec_obj.started_at.isoformat(),
                    "runtime_seconds": int(runtime_seconds),
                    "max_runtime_seconds": max_runtime,
                    "exceeded_by_seconds": int(runtime_seconds - max_runtime),
                }
                active_finding = ReliabilityFinding.objects.filter(
                    job=job,
                    execution=exec_obj,
                    condition_type=ReliabilityFinding.ConditionType.STALLED_EXECUTION,
                    status=ReliabilityFinding.Status.ACTIVE,
                ).first()

                if not active_finding:
                    try:
                        with transaction.atomic():
                            finding = ReliabilityFinding.objects.create(
                                job=job,
                                execution=exec_obj,
                                condition_type=ReliabilityFinding.ConditionType.STALLED_EXECUTION,
                                status=ReliabilityFinding.Status.ACTIVE,
                                severity=ReliabilityFinding.Severity.CRITICAL,
                                details=details,
                            )
                            _link_or_create_incident(
                                finding, AlertRule.MetricType.STALLED_EXECUTION, details
                            )
                    except IntegrityError:
                        pass
                else:
                    active_finding.details = details
                    active_finding.last_evaluated_at = now
                    active_finding.save(update_fields=["details", "last_evaluated_at"])

        elif exec_obj.status == Execution.Status.PENDING and max_queue_delay is not None:
            event_time = exec_obj.last_event_at or exec_obj.created_at
            if event_time:
                queued_seconds = (now - event_time).total_seconds()
                if queued_seconds > max_queue_delay:
                    current_overdue_execution_ids.add(exec_obj.id)
                    details = {
                        "execution_id": exec_obj.id,
                        "external_id": exec_obj.external_id,
                        "created_at": event_time.isoformat(),
                        "queued_seconds": int(queued_seconds),
                        "max_queue_delay_seconds": max_queue_delay,
                        "exceeded_by_seconds": int(queued_seconds - max_queue_delay),
                    }
                    active_finding = ReliabilityFinding.objects.filter(
                        job=job,
                        execution=exec_obj,
                        condition_type=ReliabilityFinding.ConditionType.OVERDUE_EXECUTION,
                        status=ReliabilityFinding.Status.ACTIVE,
                    ).first()

                    if not active_finding:
                        try:
                            with transaction.atomic():
                                finding = ReliabilityFinding.objects.create(
                                    job=job,
                                    execution=exec_obj,
                                    condition_type=ReliabilityFinding.ConditionType.OVERDUE_EXECUTION,
                                    status=ReliabilityFinding.Status.ACTIVE,
                                    severity=ReliabilityFinding.Severity.DEGRADED,
                                    details=details,
                                )
                                _link_or_create_incident(
                                    finding, AlertRule.MetricType.OVERDUE_EXECUTION, details
                                )
                        except IntegrityError:
                            pass
                    else:
                        active_finding.details = details
                        active_finding.last_evaluated_at = now
                        active_finding.save(update_fields=["details", "last_evaluated_at"])

    # Recover previously active stalled or overdue findings whose execution has finished
    previously_active_stalled = ReliabilityFinding.objects.filter(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.STALLED_EXECUTION,
        status=ReliabilityFinding.Status.ACTIVE,
    )
    for finding in previously_active_stalled:
        if finding.execution_id not in current_stalled_execution_ids:
            _recover_finding(
                finding,
                {
                    "condition_type": ReliabilityFinding.ConditionType.STALLED_EXECUTION,
                    "recovered_at": now.isoformat(),
                    "execution_id": finding.execution_id,
                    "final_status": finding.execution.status if finding.execution else None,
                },
            )

    previously_active_overdue = ReliabilityFinding.objects.filter(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.OVERDUE_EXECUTION,
        status=ReliabilityFinding.Status.ACTIVE,
    )
    for finding in previously_active_overdue:
        if finding.execution_id not in current_overdue_execution_ids:
            _recover_finding(
                finding,
                {
                    "condition_type": ReliabilityFinding.ConditionType.OVERDUE_EXECUTION,
                    "recovered_at": now.isoformat(),
                    "execution_id": finding.execution_id,
                    "final_status": finding.execution.status if finding.execution else None,
                },
            )


def _link_or_create_incident(finding, metric_type, details):
    """
    Checks if an alert rule matches this reliability condition, and if so,
    creates an Incident using the centralized Incident service.
    """
    job = finding.job
    alert_rule = (
        AlertRule.objects.filter(
            project=job.project,
            job=job,
            metric=metric_type,
            is_active=True,
        ).first()
        or AlertRule.objects.filter(
            project=job.project,
            job__isnull=True,
            metric=metric_type,
            is_active=True,
        ).first()
    )

    if alert_rule:
        severity = alert_rule.severity
        trigger_metadata = {
            "metric_type": metric_type,
            "metric_value": details.get("overdue_by_seconds")
            or details.get("exceeded_by_seconds", 0),
            "threshold": alert_rule.threshold,
            "evaluated_at": timezone.now().isoformat(),
            **details,
        }

        # Check for existing active incident for this rule/job
        active_incident = Incident.objects.filter(
            alert_rule=alert_rule,
            project=job.project,
            job=job,
            status__in=[Incident.Status.OPEN, Incident.Status.ACKNOWLEDGED],
        ).first()

        if not active_incident:
            try:
                with transaction.atomic():
                    incident = create_incident(
                        project=job.project,
                        job=job,
                        alert_rule=alert_rule,
                        severity=severity,
                        trigger_metadata=trigger_metadata,
                    )
                    finding.incident = incident
                    finding.save(update_fields=["incident"])
            except IntegrityError:
                pass
        else:
            finding.incident = active_incident
            finding.save(update_fields=["incident"])


def _recover_finding(finding, recovery_metadata):
    """
    Marks a ReliabilityFinding as RECOVERED and auto-resolves any associated Incident.
    Includes last_evaluated_at update.
    """
    now = timezone.now()
    finding.status = ReliabilityFinding.Status.RECOVERED
    finding.recovered_at = now
    finding.last_evaluated_at = now
    finding.save(update_fields=["status", "recovered_at", "last_evaluated_at"])

    if finding.incident_id:
        try:
            auto_resolve_incident(finding.incident_id, recovery_metadata=recovery_metadata)
        except Exception as e:
            logger.warning("Failed to auto-resolve incident %s: %s", finding.incident_id, e)
