import statistics
from datetime import timedelta
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Max, Min
from django.utils import timezone

from apps.executions.models import Execution
from apps.incidents.models import Incident
from apps.reliability.models import JobBaseline, ReliabilityFinding


def _calculate_percentile(sorted_list, percentile):
    """
    Computes nearest-rank percentile on a sorted list of numbers.
    percentile is a float between 0.0 and 1.0 (e.g. 0.95 for p95).
    """
    if not sorted_list:
        return None
    if len(sorted_list) == 1:
        return float(sorted_list[0])

    k = (len(sorted_list) - 1) * percentile
    f = int(k)
    c = f + 1
    if c >= len(sorted_list):
        return float(sorted_list[-1])
    d0 = sorted_list[f] * (c - k)
    d1 = sorted_list[c] * (k - f)
    return float(round(d0 + d1, 2))


def calculate_job_baseline(job, sample_window_days=7):
    """
    Derives statistical baseline metrics for a job from existing execution history.
    Does not duplicate raw execution records.

    Semantics:
    1. Cadence Baseline: Assumes a single recurring execution stream for scheduled tasks.
       Calculates intervals between consecutive execution starts.
    2. Runtime Baseline: Specifically represents the runtime distribution of
       successfully completed executions (Execution.Status.SUCCESS). Failed execution
       runtimes are monitored via error rate and execution failure alerts.
    3. Rate & Volume Baseline: Derives baseline failure rate, retry rate, and average
       hourly execution volume across the exact same sample window population.
    """
    now = timezone.now()
    start_dt = now - timedelta(days=sample_window_days)

    executions = (
        Execution.objects.filter(
            job=job,
            created_at__gte=start_dt,
        )
        .order_by("created_at")
        .values("id", "started_at", "created_at", "duration_ms", "status", "retry_count")
    )

    total_count = executions.count()
    if total_count < 3:
        baseline, _ = JobBaseline.objects.update_or_create(
            job=job,
            defaults={
                "sample_window_days": sample_window_days,
                "total_executions_analyzed": total_count,
                "is_sufficient": False,
                "avg_interval_seconds": None,
                "median_interval_seconds": None,
                "min_interval_seconds": None,
                "max_interval_seconds": None,
                "avg_runtime_ms": None,
                "p50_runtime_ms": None,
                "p95_runtime_ms": None,
                "p99_runtime_ms": None,
                "failure_rate": None,
                "retry_rate": None,
                "avg_hourly_volume": None,
                "metrics_summary": {"reason": "Insufficient executions in sample window (< 3)."},
            },
        )
        return baseline

    # Calculate intervals between consecutive execution starts (single recurring stream assumption)
    timestamps = [
        (e["started_at"] or e["created_at"])
        for e in executions
        if (e["started_at"] or e["created_at"]) is not None
    ]
    timestamps.sort()

    intervals = []
    for i in range(1, len(timestamps)):
        diff = (timestamps[i] - timestamps[i - 1]).total_seconds()
        if diff >= 0:
            intervals.append(diff)

    # Runtime percentiles derived strictly from successfully completed executions
    durations = [
        float(e["duration_ms"])
        for e in executions
        if e["duration_ms"] is not None and e["status"] == Execution.Status.SUCCESS
    ]
    durations.sort()

    failed_count = sum(1 for e in executions if e["status"] == Execution.Status.FAILED)
    retried_count = sum(1 for e in executions if (e.get("retry_count") or 0) > 0)

    failure_rate = round((failed_count / total_count * 100), 2) if total_count > 0 else 0.0
    retry_rate = round((retried_count / total_count * 100), 2) if total_count > 0 else 0.0

    # Determine the effective active duration for the job in this sample window.
    # For newly created jobs (e.g. created today), we avoid diluting volume across
    # days when the job did not yet exist.
    hours_in_window = sample_window_days * 24.0
    earliest_activity = getattr(job, "created_at", None)
    if executions:
        first_exec_time = executions[0].get("created_at") or executions[0].get("started_at")
        if first_exec_time and (earliest_activity is None or first_exec_time < earliest_activity):
            earliest_activity = first_exec_time

    if earliest_activity and earliest_activity > start_dt:
        elapsed_hours = (now - earliest_activity).total_seconds() / 3600.0
        effective_hours = min(hours_in_window, max(elapsed_hours, 1.0))
    else:
        effective_hours = hours_in_window

    avg_hourly_volume = round(total_count / effective_hours, 2) if effective_hours > 0 else 0.0

    is_sufficient = len(intervals) >= 2 and total_count >= 3

    avg_interval = round(statistics.mean(intervals), 2) if intervals else None
    median_interval = round(statistics.median(intervals), 2) if intervals else None
    min_interval = round(min(intervals), 2) if intervals else None
    max_interval = round(max(intervals), 2) if intervals else None

    avg_runtime = round(statistics.mean(durations), 2) if durations else None
    p50_runtime = _calculate_percentile(durations, 0.50) if durations else None
    p95_runtime = _calculate_percentile(durations, 0.95) if durations else None
    p99_runtime = _calculate_percentile(durations, 0.99) if durations else None

    metrics_summary = {
        "sample_start": start_dt.isoformat(),
        "sample_end": now.isoformat(),
        "total_executions": total_count,
        "effective_sample_hours": round(effective_hours, 2),
        "intervals_count": len(intervals),
        "durations_count": len(durations),
        "failed_count": failed_count,
        "retried_count": retried_count,
    }

    baseline, _ = JobBaseline.objects.update_or_create(
        job=job,
        defaults={
            "sample_window_days": sample_window_days,
            "total_executions_analyzed": total_count,
            "is_sufficient": is_sufficient,
            "avg_interval_seconds": avg_interval,
            "median_interval_seconds": median_interval,
            "min_interval_seconds": min_interval,
            "max_interval_seconds": max_interval,
            "avg_runtime_ms": avg_runtime,
            "p50_runtime_ms": p50_runtime,
            "p95_runtime_ms": p95_runtime,
            "p99_runtime_ms": p99_runtime,
            "failure_rate": failure_rate,
            "retry_rate": retry_rate,
            "avg_hourly_volume": avg_hourly_volume,
            "metrics_summary": metrics_summary,
        },
    )
    return baseline


def compute_adaptive_thresholds(baseline):
    """
    Computes baseline-derived adaptive thresholds with safety bounds (clamping).
    """
    if not baseline or not baseline.is_sufficient:
        return {
            "failure_rate": None,
            "retry_rate": None,
            "p95_duration_ms": None,
            "is_available": False,
            "source": "UNAVAILABLE",
        }

    base_fr = baseline.failure_rate if baseline.failure_rate is not None else 0.0
    adaptive_fr = round(min(max(max(base_fr, 1.0) * 3.0, 5.0), 50.0), 2)

    base_rr = baseline.retry_rate if baseline.retry_rate is not None else 0.0
    adaptive_rr = round(min(max(max(base_rr, 1.0) * 3.0, 5.0), 50.0), 2)

    base_p95 = baseline.p95_runtime_ms
    if base_p95 is not None and base_p95 > 0:
        min_bound = base_p95 + 1000.0
        max_bound = max(base_p95 * 10.0, min_bound)
        calculated = base_p95 * 2.0
        adaptive_p95 = round(min(max(calculated, min_bound), max_bound), 2)
    else:
        adaptive_p95 = None

    return {
        "failure_rate": adaptive_fr,
        "retry_rate": adaptive_rr,
        "p95_duration_ms": adaptive_p95,
        "is_available": True,
        "source": "BASELINE",
    }


def calculate_window_observation_metrics(job, window_minutes=60, now=None):
    """
    Calculates observed execution behavior metrics (failure rate, retry rate,
    P95 duration, volume/sample count) over a rolling observation window.
    Shared between anomaly evaluation and reliability overview to guarantee identical semantics.
    """
    if now is None:
        now = timezone.now()
    window_start = now - timedelta(minutes=window_minutes)
    executions = list(
        Execution.objects.filter(
            job=job,
            created_at__gte=window_start,
        ).values("id", "status", "retry_count", "duration_ms")
    )
    total = len(executions)
    failed_count = sum(1 for e in executions if e["status"] == Execution.Status.FAILED)
    retried_count = sum(1 for e in executions if (e.get("retry_count") or 0) > 0)
    durations = [
        float(e["duration_ms"])
        for e in executions
        if e["duration_ms"] is not None and e["status"] == Execution.Status.SUCCESS
    ]
    durations.sort()
    p95 = _calculate_percentile(durations, 0.95) if durations else None

    failure_rate = round(failed_count / total * 100, 2) if total > 0 else 0.0
    retry_rate = round(retried_count / total * 100, 2) if total > 0 else 0.0

    return {
        "window_minutes": window_minutes,
        "window_start": window_start,
        "total": total,
        "failed_count": failed_count,
        "retried_count": retried_count,
        "durations": durations,
        "p95": p95,
        "failure_rate": failure_rate,
        "retry_rate": retry_rate,
    }


def get_job_reliability_overview(job):
    """
    Returns a comprehensive reliability overview for a job including current state,
    expectations, baseline, next expected execution, missed after timestamp, and findings.
    Standardized on execution start occurrence ordering (-started_at, -created_at).
    """
    now = timezone.now()

    expectation = getattr(job, "expectation", None)
    baseline = getattr(job, "baseline", None)

    latest_exec = (
        Execution.objects.filter(job=job)
        .order_by(F("started_at").desc(nulls_last=True), "-created_at")
        .first()
    )

    last_execution_at = None
    if latest_exec:
        last_execution_at = latest_exec.started_at or latest_exec.created_at

    expected_interval_seconds = None
    expectation_source = "NONE"

    if expectation and expectation.expected_interval_seconds:
        expected_interval_seconds = expectation.expected_interval_seconds
        expectation_source = "CONFIGURED"
    elif baseline and baseline.is_sufficient and baseline.median_interval_seconds:
        expected_interval_seconds = int(baseline.median_interval_seconds)
        expectation_source = "BASELINE"

    max_runtime_seconds = None
    if expectation and expectation.max_runtime_seconds:
        max_runtime_seconds = expectation.max_runtime_seconds
    elif baseline and baseline.is_sufficient and baseline.p95_runtime_ms:
        max_runtime_seconds = int(max(1, round(baseline.p95_runtime_ms / 1000 * 1.5)))

    next_expected_at = None
    missed_after_at = None

    if last_execution_at and expected_interval_seconds:
        next_expected_at = last_execution_at + timedelta(seconds=expected_interval_seconds)
        grace_period = expectation.grace_period_seconds if expectation else 0
        missed_after_at = next_expected_at + timedelta(seconds=grace_period)

    # Active findings
    active_findings = list(
        ReliabilityFinding.objects.filter(
            job=job,
            status=ReliabilityFinding.Status.ACTIVE,
        )
    )

    active_stalled = any(
        f.condition_type == ReliabilityFinding.ConditionType.STALLED_EXECUTION
        for f in active_findings
    )
    active_overdue = any(
        f.condition_type == ReliabilityFinding.ConditionType.OVERDUE_EXECUTION
        for f in active_findings
    )
    active_missed = any(
        f.condition_type == ReliabilityFinding.ConditionType.MISSED_EXECUTION
        for f in active_findings
    )

    # Anomaly findings
    active_anomalies = [
        f
        for f in active_findings
        if f.condition_type
        in [
            ReliabilityFinding.ConditionType.FAILURE_RATE_ANOMALY,
            ReliabilityFinding.ConditionType.RETRY_RATE_ANOMALY,
            ReliabilityFinding.ConditionType.DURATION_ANOMALY,
            ReliabilityFinding.ConditionType.EXECUTION_VOLUME_ANOMALY,
        ]
    ]

    # Current reliability state with strict precedence:
    # DISABLED > STALLED > OVERDUE > MISSED > ANOMALOUS > HEALTHY
    if expectation and not expectation.is_enabled:
        current_state = "DISABLED"
    elif active_stalled:
        current_state = "STALLED"
    elif active_overdue:
        current_state = "OVERDUE"
    elif active_missed or (missed_after_at and now > missed_after_at):
        current_state = "MISSED"
    elif active_anomalies:
        current_state = "ANOMALOUS"
    else:
        current_state = "HEALTHY"

    # Only populate overdue_by_seconds if MISSED_EXECUTION is active
    overdue_by_seconds = 0
    if current_state == "MISSED" and missed_after_at and now > missed_after_at:
        overdue_by_seconds = int((now - missed_after_at).total_seconds())

    recent_findings = list(ReliabilityFinding.objects.filter(job=job).order_by("-detected_at")[:10])

    # Behavior metrics in observation window (last 60m) using shared helper
    metrics = calculate_window_observation_metrics(job, window_minutes=60, now=now)
    cur_total = metrics["total"]
    cur_fr = metrics["failure_rate"]
    cur_rr = metrics["retry_rate"]
    cur_p95 = metrics["p95"]

    adaptive_thresholds = compute_adaptive_thresholds(baseline)

    behavior_comparison = {
        "observation_window_minutes": 60,
        "sample_count": cur_total,
        "failure_rate": {
            "current": cur_fr if cur_total > 0 else None,
            "baseline": baseline.failure_rate if (baseline and baseline.is_sufficient) else None,
            "adaptive_threshold": adaptive_thresholds["failure_rate"],
            "deviation_ratio": (
                round(cur_fr / max(baseline.failure_rate or 1.0, 1.0), 2)
                if (baseline and baseline.is_sufficient and cur_total > 0)
                else None
            ),
        },
        "retry_rate": {
            "current": cur_rr if cur_total > 0 else None,
            "baseline": baseline.retry_rate if (baseline and baseline.is_sufficient) else None,
            "adaptive_threshold": adaptive_thresholds["retry_rate"],
            "deviation_ratio": (
                round(cur_rr / max(baseline.retry_rate or 1.0, 1.0), 2)
                if (baseline and baseline.is_sufficient and cur_total > 0)
                else None
            ),
        },
        "p95_duration_ms": {
            "current": cur_p95,
            "baseline": baseline.p95_runtime_ms if (baseline and baseline.is_sufficient) else None,
            "adaptive_threshold": adaptive_thresholds["p95_duration_ms"],
            "deviation_ratio": (
                round(cur_p95 / baseline.p95_runtime_ms, 2)
                if (baseline and baseline.is_sufficient and cur_p95 and baseline.p95_runtime_ms)
                else None
            ),
        },
        "hourly_volume": {
            "current": cur_total,
            "baseline": baseline.avg_hourly_volume
            if (baseline and baseline.is_sufficient)
            else None,
            "deviation_ratio": (
                round(cur_total / max(baseline.avg_hourly_volume or 1.0, 1.0), 2)
                if (baseline and baseline.is_sufficient and baseline.avg_hourly_volume)
                else None
            ),
        },
    }

    # Calculate MTTR and MTBF metrics for this specific job
    job_incidents = Incident.objects.filter(job=job)
    resolved_job_incidents = job_incidents.filter(
        status=Incident.Status.RESOLVED, resolved_at__isnull=False
    )
    mttr_res = resolved_job_incidents.annotate(
        duration=ExpressionWrapper(F("resolved_at") - F("created_at"), output_field=DurationField())
    ).aggregate(avg_mttr=Avg("duration"))
    mttr_td = mttr_res["avg_mttr"]
    job_mttr_seconds = mttr_td.total_seconds() if mttr_td else None

    mtbf_res = job_incidents.aggregate(
        min_created=Min("created_at"),
        max_created=Max("created_at"),
        count=Count("id"),
    )
    job_mtbf_seconds = None
    if mtbf_res["count"] >= 2 and mtbf_res["max_created"] and mtbf_res["min_created"]:
        delta = (mtbf_res["max_created"] - mtbf_res["min_created"]).total_seconds()
        job_mtbf_seconds = delta / (mtbf_res["count"] - 1)

    return {
        "job_id": job.id,
        "job_name": job.name,
        "task_identifier": job.task_identifier,
        "current_state": current_state,
        "is_enabled": expectation.is_enabled if expectation else True,
        "expectation_source": expectation_source,
        "expected_interval_seconds": expected_interval_seconds,
        "max_runtime_seconds": max_runtime_seconds,
        "grace_period_seconds": expectation.grace_period_seconds if expectation else 0,
        "last_execution_at": last_execution_at.isoformat() if last_execution_at else None,
        "next_expected_at": next_expected_at.isoformat() if next_expected_at else None,
        "missed_after_at": missed_after_at.isoformat() if missed_after_at else None,
        "overdue_by_seconds": overdue_by_seconds,
        "mttr_seconds": job_mttr_seconds,
        "mtbf_seconds": job_mtbf_seconds,
        "latest_execution": {
            "id": latest_exec.id,
            "status": latest_exec.status,
            "duration_ms": latest_exec.duration_ms,
            "last_event_at": latest_exec.last_event_at.isoformat(),
        }
        if latest_exec
        else None,
        "active_findings": active_findings,
        "active_anomalies": active_anomalies,
        "recent_findings": recent_findings,
        "baseline": baseline,
        "expectation": expectation,
        "adaptive_thresholds": adaptive_thresholds,
        "behavior_comparison": behavior_comparison,
    }
