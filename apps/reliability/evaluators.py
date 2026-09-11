import logging
from datetime import timedelta
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.db.models import F

from apps.core.realtime import publish_realtime_event
from apps.jobs.models import Job
from apps.executions.models import Execution
from apps.alerts.models import AlertRule
from apps.incidents.models import Incident
from apps.incidents.services import auto_resolve_incident, create_incident
from apps.reliability.models import ReliabilityFinding
from apps.reliability.services import calculate_window_observation_metrics

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

        # 3. Detect Statistical Anomalies against Baseline
        detect_anomalies(job, expectation, baseline, now)


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
    ).order_by("created_at")

    latest_started_exec = (
        Execution.objects.filter(job=job, started_at__isnull=False)
        .order_by("-started_at")
        .first()
    )

    current_stalled_execution_ids = set()
    current_overdue_execution_ids = set()

    for exec_obj in in_progress:
        if exec_obj.status == Execution.Status.RUNNING and max_runtime and exec_obj.started_at:
            has_newer_exec = bool(
                latest_started_exec
                and latest_started_exec.id != exec_obj.id
                and latest_started_exec.started_at
                and exec_obj.started_at
                and latest_started_exec.started_at > exec_obj.started_at
            )
            runtime_seconds = (now - exec_obj.started_at).total_seconds()
            stale_timeout_threshold = max(max_runtime * 3, 3600)
            is_stale_timeout = runtime_seconds > stale_timeout_threshold

            # Auto-discard execution if a newer task arrived for this job or runtime exceeds stale timeout threshold
            if has_newer_exec or is_stale_timeout:
                reason = (
                    "Discarded: Newer execution arrived for job (worker restarted/lost)"
                    if has_newer_exec
                    else f"Execution timed out / abandoned (exceeded {stale_timeout_threshold}s)"
                )
                exec_obj.status = Execution.Status.FAILED
                exec_obj.finished_at = now
                exec_obj.error_message = reason
                exec_obj.save(update_fields=["status", "finished_at", "error_message"])
                continue

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

        elif exec_obj.status == Execution.Status.PENDING:
            event_time = exec_obj.last_event_at or exec_obj.created_at
            if event_time:
                queued_seconds = (now - event_time).total_seconds()
                is_stale_queue = queued_seconds > 3600

                if has_newer_exec or is_stale_queue:
                    reason = (
                        "Discarded: Newer execution arrived for job"
                        if has_newer_exec
                        else f"Execution queued delay timed out / abandoned (exceeded {int(queued_seconds)}s)"
                    )
                    exec_obj.status = Execution.Status.FAILED
                    exec_obj.finished_at = now
                    exec_obj.error_message = reason
                    exec_obj.save(update_fields=["status", "finished_at", "error_message"])
                    continue

                if max_queue_delay is not None and queued_seconds > max_queue_delay:
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
        metric_value = (
            details.get("current_value")
            if details.get("current_value") is not None
            else details.get("overdue_by_seconds")
            if details.get("overdue_by_seconds") is not None
            else details.get("exceeded_by_seconds", 0)
        )
        trigger_metadata = {
            "metric_type": metric_type,
            "metric_value": metric_value,
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

    publish_realtime_event(
        "reliability.finding.updated",
        project_id=finding.job.project_id,
        payload={
            "finding_id": finding.id,
            "job_id": finding.job_id,
            "status": finding.status,
            "condition_type": finding.condition_type,
        },
    )


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

    publish_realtime_event(
        "reliability.finding.updated",
        project_id=finding.job.project_id,
        payload={
            "finding_id": finding.id,
            "job_id": finding.job_id,
            "status": finding.status,
            "condition_type": finding.condition_type,
        },
    )

    if finding.incident_id:
        try:
            auto_resolve_incident(finding.incident_id, recovery_metadata=recovery_metadata)
        except Exception as e:
            logger.warning("Failed to auto-resolve incident %s: %s", finding.incident_id, e)


ANOMALY_OBSERVATION_WINDOW_MINUTES = 60
MIN_RATE_SAMPLE_COUNT = 5
MIN_DURATION_SAMPLE_COUNT = 5
MIN_VOLUME_BASELINE_HOURLY = 5.0

FAILURE_RATE_RELATIVE_RATIO = 3.0
FAILURE_RATE_ABSOLUTE_DELTA_MIN = 5.0

RETRY_RATE_RELATIVE_RATIO = 3.0
RETRY_RATE_ABSOLUTE_DELTA_MIN = 5.0

DURATION_RELATIVE_RATIO = 2.5
DURATION_ABSOLUTE_DELTA_MIN_MS = 1000.0

VOLUME_SURGE_RATIO = 4.0
VOLUME_DROP_RATIO = 0.2


def detect_anomalies(job, expectation, baseline, now):
    """
    Evaluates statistical behavior anomalies for a job against its baseline.
    Observation window defaults to last 60 minutes.
    Requires baseline to be sufficient and minimum current window sample size.
    """
    if not baseline or not baseline.is_sufficient:
        active_anomalies = ReliabilityFinding.objects.filter(
            job=job,
            condition_type__in=[
                ReliabilityFinding.ConditionType.FAILURE_RATE_ANOMALY,
                ReliabilityFinding.ConditionType.RETRY_RATE_ANOMALY,
                ReliabilityFinding.ConditionType.DURATION_ANOMALY,
                ReliabilityFinding.ConditionType.EXECUTION_VOLUME_ANOMALY,
            ],
            status=ReliabilityFinding.Status.ACTIVE,
        )
        for finding in active_anomalies:
            _recover_finding(
                finding,
                {
                    "condition_type": finding.condition_type,
                    "recovered_at": now.isoformat(),
                    "reason": "Baseline no longer sufficient or available",
                },
            )
        return

    metrics = calculate_window_observation_metrics(
        job=job, window_minutes=ANOMALY_OBSERVATION_WINDOW_MINUTES, now=now
    )
    total_in_window = metrics["total"]
    durations = metrics["durations"]
    current_p95 = metrics["p95"]
    current_failure_rate = metrics["failure_rate"]
    current_retry_rate = metrics["retry_rate"]

    base_failure_rate = baseline.failure_rate if baseline.failure_rate is not None else 0.0
    base_retry_rate = baseline.retry_rate if baseline.retry_rate is not None else 0.0
    base_p95 = baseline.p95_runtime_ms
    base_volume = baseline.avg_hourly_volume if baseline.avg_hourly_volume is not None else 0.0

    # 1. Failure Rate Anomaly
    is_fr_anomaly = False
    fr_details = {}
    if total_in_window >= MIN_RATE_SAMPLE_COUNT:
        fr_ratio = current_failure_rate / max(base_failure_rate, 1.0)
        fr_delta = current_failure_rate - base_failure_rate
        if fr_ratio >= FAILURE_RATE_RELATIVE_RATIO and fr_delta >= FAILURE_RATE_ABSOLUTE_DELTA_MIN:
            is_fr_anomaly = True
            fr_details = {
                "metric_type": "FAILURE_RATE",
                "current_value": current_failure_rate,
                "baseline_value": base_failure_rate,
                "deviation_ratio": round(fr_ratio, 2),
                "adaptive_threshold": round(
                    min(max(max(base_failure_rate, 1.0) * 3.0, 5.0), 50.0), 2
                ),
                "threshold_source": "BASELINE",
                "observation_window_minutes": ANOMALY_OBSERVATION_WINDOW_MINUTES,
                "sample_count": total_in_window,
                "detected_at": now.isoformat(),
            }
    _evaluate_anomaly_finding(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.FAILURE_RATE_ANOMALY,
        metric_type="FAILURE_RATE_ANOMALY",
        is_active=is_fr_anomaly,
        details=fr_details,
        now=now,
    )

    # 2. Retry Rate Anomaly
    is_rr_anomaly = False
    rr_details = {}
    if total_in_window >= MIN_RATE_SAMPLE_COUNT:
        rr_ratio = current_retry_rate / max(base_retry_rate, 1.0)
        rr_delta = current_retry_rate - base_retry_rate
        if rr_ratio >= RETRY_RATE_RELATIVE_RATIO and rr_delta >= RETRY_RATE_ABSOLUTE_DELTA_MIN:
            is_rr_anomaly = True
            rr_details = {
                "metric_type": "RETRY_RATE",
                "current_value": current_retry_rate,
                "baseline_value": base_retry_rate,
                "deviation_ratio": round(rr_ratio, 2),
                "adaptive_threshold": round(
                    min(max(max(base_retry_rate, 1.0) * 3.0, 5.0), 50.0), 2
                ),
                "threshold_source": "BASELINE",
                "observation_window_minutes": ANOMALY_OBSERVATION_WINDOW_MINUTES,
                "sample_count": total_in_window,
                "detected_at": now.isoformat(),
            }
    _evaluate_anomaly_finding(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.RETRY_RATE_ANOMALY,
        metric_type="RETRY_RATE_ANOMALY",
        is_active=is_rr_anomaly,
        details=rr_details,
        now=now,
    )

    # 3. Duration Anomaly
    is_dur_anomaly = False
    dur_details = {}
    if (
        len(durations) >= MIN_DURATION_SAMPLE_COUNT
        and base_p95 is not None
        and base_p95 > 0
        and current_p95 is not None
    ):
        dur_ratio = current_p95 / base_p95
        dur_delta = current_p95 - base_p95
        if dur_ratio >= DURATION_RELATIVE_RATIO and dur_delta >= DURATION_ABSOLUTE_DELTA_MIN_MS:
            is_dur_anomaly = True
            min_bound = base_p95 + 1000.0
            max_bound = max(base_p95 * 10.0, min_bound)
            calculated_threshold = base_p95 * 2.0
            adaptive_threshold = round(min(max(calculated_threshold, min_bound), max_bound), 2)
            dur_details = {
                "metric_type": "P95_DURATION",
                "current_value": round(current_p95, 2),
                "baseline_value": round(base_p95, 2),
                "deviation_ratio": round(dur_ratio, 2),
                "adaptive_threshold": adaptive_threshold,
                "threshold_source": "BASELINE",
                "observation_window_minutes": ANOMALY_OBSERVATION_WINDOW_MINUTES,
                "sample_count": len(durations),
                "detected_at": now.isoformat(),
            }
    _evaluate_anomaly_finding(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.DURATION_ANOMALY,
        metric_type="DURATION_ANOMALY",
        is_active=is_dur_anomaly,
        details=dur_details,
        now=now,
    )

    # 4. Execution Volume Anomaly (global baseline, not seasonality-aware)
    is_vol_anomaly = False
    vol_details = {}
    if base_volume >= MIN_VOLUME_BASELINE_HOURLY:
        vol_ratio = total_in_window / base_volume
        if vol_ratio >= VOLUME_SURGE_RATIO or vol_ratio <= VOLUME_DROP_RATIO:
            is_vol_anomaly = True
            vol_details = {
                "metric_type": "EXECUTION_VOLUME",
                "current_value": total_in_window,
                "baseline_value": base_volume,
                "deviation_ratio": round(vol_ratio, 2),
                "threshold_source": "BASELINE",
                "observation_window_minutes": ANOMALY_OBSERVATION_WINDOW_MINUTES,
                "sample_count": total_in_window,
                "detected_at": now.isoformat(),
            }
    _evaluate_anomaly_finding(
        job=job,
        condition_type=ReliabilityFinding.ConditionType.EXECUTION_VOLUME_ANOMALY,
        metric_type="EXECUTION_VOLUME_ANOMALY",
        is_active=is_vol_anomaly,
        details=vol_details,
        now=now,
    )


def _evaluate_anomaly_finding(job, condition_type, metric_type, is_active, details, now):
    active_finding = ReliabilityFinding.objects.filter(
        job=job,
        condition_type=condition_type,
        status=ReliabilityFinding.Status.ACTIVE,
    ).first()

    if is_active:
        if not active_finding:
            # Create new active finding with default DEGRADED severity
            finding = ReliabilityFinding.objects.create(
                job=job,
                condition_type=condition_type,
                status=ReliabilityFinding.Status.ACTIVE,
                severity=ReliabilityFinding.Severity.DEGRADED,
                details=details,
            )
            # Link or create incident if a matching AlertRule exists
            _link_or_create_incident(finding, metric_type, details)
        else:
            # Idempotently update active finding details & last_evaluated_at
            active_finding.details = details
            active_finding.last_evaluated_at = now
            active_finding.save(update_fields=["details", "last_evaluated_at"])
            # Ensure linked incident is maintained or created if rule was added later
            if not active_finding.incident_id:
                _link_or_create_incident(active_finding, metric_type, details)
    else:
        if active_finding:
            _recover_finding(
                active_finding,
                {
                    "condition_type": condition_type,
                    "recovered_at": now.isoformat(),
                    "reason": "Metric returned within normal baseline parameters",
                },
            )
