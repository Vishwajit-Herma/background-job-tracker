import statistics
from datetime import timedelta
from django.db.models import F
from django.utils import timezone

from apps.executions.models import Execution
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
    """
    now = timezone.now()
    start_dt = now - timedelta(days=sample_window_days)

    executions = (
        Execution.objects.filter(
            job=job,
            created_at__gte=start_dt,
        )
        .order_by("created_at")
        .values("id", "started_at", "created_at", "duration_ms", "status")
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
        "intervals_count": len(intervals),
        "durations_count": len(durations),
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
            "metrics_summary": metrics_summary,
        },
    )
    return baseline


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
        ).order_by("-detected_at")
    )

    # Current reliability state
    if any(
        f.condition_type == ReliabilityFinding.ConditionType.STALLED_EXECUTION
        for f in active_findings
    ):
        current_state = "STALLED"
    elif any(
        f.condition_type == ReliabilityFinding.ConditionType.OVERDUE_EXECUTION
        for f in active_findings
    ):
        current_state = "OVERDUE"
    elif any(
        f.condition_type == ReliabilityFinding.ConditionType.MISSED_EXECUTION
        for f in active_findings
    ):
        current_state = "MISSED"
    else:
        current_state = "HEALTHY"

    # Only populate overdue_by_seconds if MISSED_EXECUTION is active
    overdue_by_seconds = 0
    if current_state == "MISSED" and missed_after_at and now > missed_after_at:
        overdue_by_seconds = int((now - missed_after_at).total_seconds())

    recent_findings = list(ReliabilityFinding.objects.filter(job=job).order_by("-detected_at")[:10])

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
        "latest_execution": {
            "id": latest_exec.id,
            "status": latest_exec.status,
            "duration_ms": latest_exec.duration_ms,
            "last_event_at": latest_exec.last_event_at.isoformat(),
        }
        if latest_exec
        else None,
        "active_findings": active_findings,
        "recent_findings": recent_findings,
        "baseline": baseline,
        "expectation": expectation,
    }
