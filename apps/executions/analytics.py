from datetime import timedelta

from django.db.models import Aggregate, Avg, Count, FloatField, Q
from django.db.models.functions import Coalesce, TruncDay, TruncHour
from django.utils import timezone as django_timezone

from apps.executions.models import Execution
from apps.executions.serializers import AnalyticsQuerySerializer
from apps.incidents.models import Incident
from apps.alerts.models import AlertRule


class PercentileCont(Aggregate):
    """
    PostgreSQL PERCENTILE_CONT implementation for Django ORM.
    Requires PostgreSQL as the backend.
    """

    function = "PERCENTILE_CONT"
    name = "PercentileCont"
    output_field = FloatField()
    template = "%(function)s(%(percentile)s) WITHIN GROUP (ORDER BY %(expressions)s)"

    def __init__(self, expression, percentile, **extra):
        super().__init__(expression, percentile=percentile, **extra)


# Health Thresholds
HEALTH_DEGRADED_FAILURE_RATE = 2.0  # Percentage
HEALTH_CRITICAL_FAILURE_RATE = 10.0  # Percentage

HEALTH_DEGRADED_RETRY_RATE = 10.0  # Percentage
HEALTH_CRITICAL_RETRY_RATE = 30.0  # Percentage


def calculate_health_state(failure_rate, retry_rate=0.0):
    """
    Derives deterministic health state based on failure and retry rates.
    """
    if failure_rate >= HEALTH_CRITICAL_FAILURE_RATE or retry_rate >= HEALTH_CRITICAL_RETRY_RATE:
        return "CRITICAL"
    if failure_rate >= HEALTH_DEGRADED_FAILURE_RATE or retry_rate >= HEALTH_DEGRADED_RETRY_RATE:
        return "DEGRADED"
    return "HEALTHY"


def _base_metrics_aggregations():
    """Returns the base aggregation dictionary for executions."""
    return {
        "executions": Count("id"),
        "successes": Count("id", filter=Q(status=Execution.Status.SUCCESS)),
        "failures": Count("id", filter=Q(status=Execution.Status.FAILED)),
        "retries": Count("id", filter=Q(retry_count__gt=0)),
        "average_duration_ms": Avg("duration_ms"),
        "p50_duration_ms": PercentileCont("duration_ms", 0.50),
        "p95_duration_ms": PercentileCont("duration_ms", 0.95),
        "p99_duration_ms": PercentileCont("duration_ms", 0.99),
    }


def __round_dur(val):
    return round(val, 2) if val is not None else None


def _process_aggregated_metrics(agg):
    """
    Processes raw database aggregations into rate calculations and cleans up null values.
    """
    total = agg["executions"] or 0
    successes = agg["successes"] or 0
    failures = agg["failures"] or 0
    retries = agg["retries"] or 0

    success_rate = (successes / total * 100) if total > 0 else 0.0
    failure_rate = (failures / total * 100) if total > 0 else 0.0
    retry_rate = (retries / total * 100) if total > 0 else 0.0

    # Minimum observations required to consider percentiles valid
    if total < 2:
        p50 = None
        p95 = None
        p99 = None
    else:
        p50 = __round_dur(agg.get("p50_duration_ms"))
        p95 = __round_dur(agg.get("p95_duration_ms"))
        p99 = __round_dur(agg.get("p99_duration_ms"))

    avg_duration = __round_dur(agg.get("average_duration_ms"))

    return {
        "executions": total,
        "successes": successes,
        "failures": failures,
        "retries": retries,
        "success_rate": round(success_rate, 2),
        "failure_rate": round(failure_rate, 2),
        "retry_rate": round(retry_rate, 2),
        "average_duration_ms": avg_duration,
        "p50_duration_ms": p50,
        "p95_duration_ms": p95,
        "p99_duration_ms": p99,
        "health": calculate_health_state(failure_rate, retry_rate),
    }


def calculate_delta(current, previous):
    current_val = current or 0.0
    previous_val = previous or 0.0

    if current_val == 0 and previous_val == 0:
        return {
            "current": current,
            "previous": previous,
            "delta_points": None,
            "delta_percent": None,
        }

    delta_points = current_val - previous_val

    delta_percent = None if previous_val == 0 else (delta_points / previous_val) * 100

    return {
        "current": current,
        "previous": previous,
        "delta_points": round(delta_points, 2),
        "delta_percent": round(delta_percent, 2) if delta_percent is not None else None,
    }


def format_delta_metric(current, previous, comparison_period):
    delta = calculate_delta(current, previous)
    delta["comparison_period"] = comparison_period
    return delta


def parse_analytics_query(request):
    """
    Parses and validates the analytics query params.
    Returns (start_dt, end_dt, bucket_type, filters_dict)
    """
    serializer = AnalyticsQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)

    start = serializer.validated_data.get("start")
    end = serializer.validated_data.get("end")
    time_range = serializer.validated_data.get("range", "last_24_hours")

    if not end:
        end = django_timezone.now()

    if not start:
        if time_range in ("1h", "last_1_hour"):
            start = end - timedelta(hours=1)
        elif time_range in ("6h", "last_6_hours"):
            start = end - timedelta(hours=6)
        elif time_range in ("7d", "last_7_days"):
            start = end - timedelta(days=7)
        elif time_range in ("30d", "last_30_days"):
            start = end - timedelta(days=30)
        else:
            # Default to last_24_hours / 24h
            start = end - timedelta(hours=24)

    # Determine bucket type intelligently based on the actual duration
    duration = end - start
    bucket_type = "day" if duration.days > 3 else "hour"

    # Extract extra filters
    filters = {}
    if "jobs" in serializer.validated_data:
        filters["job_id__in"] = serializer.validated_data["jobs"]
    if "queue" in serializer.validated_data and serializer.validated_data["queue"]:
        filters["queue"] = serializer.validated_data["queue"]
    if "worker" in serializer.validated_data and serializer.validated_data["worker"]:
        filters["worker"] = serializer.validated_data["worker"]

    return start, end, bucket_type, filters


def _build_summary(qs, group_by_field):
    aggs = list(
        qs.exclude(**{group_by_field: ""})
        .values(group_by_field)
        .annotate(
            count=Count("id"),
            failures=Count("id", filter=Q(status=Execution.Status.FAILED)),
            retries=Count("id", filter=Q(retry_count__gt=0)),
            successes=Count("id", filter=Q(status=Execution.Status.SUCCESS)),
        )
        .order_by("-count")
    )
    for row in aggs:
        total = row["count"]
        row["success_rate"] = round((row["successes"] / total * 100), 2) if total > 0 else 0.0
        row["failure_rate"] = round((row["failures"] / total * 100), 2) if total > 0 else 0.0
        row["retry_rate"] = round((row["retries"] / total * 100), 2) if total > 0 else 0.0
    return aggs


def get_job_analytics(job_id, start_dt, end_dt, base_qs=None):
    """
    Computes Job-level analytics.
    """
    duration = end_dt - start_dt
    prev_end_dt = start_dt
    prev_start_dt = start_dt - duration

    qs = base_qs if base_qs is not None else Execution.objects.all()
    qs = qs.filter(
        Q(job_id=job_id)
        & (
            Q(started_at__gte=start_dt, started_at__lt=end_dt)
            | Q(started_at__isnull=True, created_at__gte=start_dt, created_at__lt=end_dt)
        )
    )

    agg = qs.aggregate(**_base_metrics_aggregations())

    # Queue and worker summaries
    queue_summary = _build_summary(qs, "queue")
    worker_summary = _build_summary(qs, "worker")

    # Errors
    errors = list(
        qs.exclude(error_type="")
        .values("error_type")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    metrics = _process_aggregated_metrics(agg)

    # Previous period
    prev_qs = base_qs if base_qs is not None else Execution.objects.all()
    prev_qs = prev_qs.filter(
        Q(job_id=job_id)
        & (
            Q(started_at__gte=prev_start_dt, started_at__lt=prev_end_dt)
            | Q(started_at__isnull=True, created_at__gte=prev_start_dt, created_at__lt=prev_end_dt)
        )
    )
    prev_agg = prev_qs.aggregate(**_base_metrics_aggregations())
    prev_metrics = _process_aggregated_metrics(prev_agg)

    comp_period = (
        f"previous {duration.days} day{'s' if duration.days > 1 else ''}"
        if duration.days >= 1
        else f"previous {duration.seconds // 3600} hour{'s' if (duration.seconds // 3600) > 1 else ''}"
    )

    metrics["executions"] = format_delta_metric(
        metrics["executions"], prev_metrics["executions"], comp_period
    )
    metrics["success_rate"] = format_delta_metric(
        metrics["success_rate"], prev_metrics["success_rate"], comp_period
    )
    metrics["failure_rate"] = format_delta_metric(
        metrics["failure_rate"], prev_metrics["failure_rate"], comp_period
    )
    metrics["retry_rate"] = format_delta_metric(
        metrics["retry_rate"], prev_metrics["retry_rate"], comp_period
    )
    metrics["average_duration_ms"] = format_delta_metric(
        metrics["average_duration_ms"], prev_metrics["average_duration_ms"], comp_period
    )
    metrics["p95_duration_ms"] = format_delta_metric(
        metrics["p95_duration_ms"], prev_metrics["p95_duration_ms"], comp_period
    )
    open_incidents = Incident.objects.filter(
        job_id=job_id, status__in=[Incident.Status.OPEN, Incident.Status.ACKNOWLEDGED]
    ).count()
    critical_incidents = Incident.objects.filter(
        job_id=job_id,
        status__in=[Incident.Status.OPEN, Incident.Status.ACKNOWLEDGED],
        severity=Incident.Severity.CRITICAL,
    ).count()

    rules = AlertRule.objects.filter(job_id=job_id, is_active=True)
    thresholds = {}
    for r in rules:
        if r.metric == AlertRule.MetricType.FAILURE_RATE:
            thresholds["failure_rate"] = r.threshold
        elif r.metric == AlertRule.MetricType.RETRY_RATE:
            thresholds["retry_rate"] = r.threshold
        elif r.metric == AlertRule.MetricType.P95_DURATION:
            thresholds["p95_duration"] = r.threshold

    metrics.update(
        {
            "job_id": job_id,
            "period": {"start": start_dt.isoformat(), "end": end_dt.isoformat()},
            "open_incidents": open_incidents,
            "critical_incidents": critical_incidents,
            "queue_summary": queue_summary,
            "worker_summary": worker_summary,
            "errors": errors,
            "thresholds": thresholds,
        }
    )
    return metrics


def get_project_analytics(project_id, start_dt, end_dt, base_qs=None):
    """
    Computes Project-level analytics without N+1 queries.
    """
    duration = end_dt - start_dt
    prev_end_dt = start_dt
    prev_start_dt = start_dt - duration

    qs = base_qs if base_qs is not None else Execution.objects.all()
    qs = qs.filter(
        Q(job__project_id=project_id)
        & (
            Q(started_at__gte=start_dt, started_at__lt=end_dt)
            | Q(started_at__isnull=True, created_at__gte=start_dt, created_at__lt=end_dt)
        )
    )

    # 1. Overall Aggregation
    agg = qs.aggregate(**_base_metrics_aggregations())
    metrics = _process_aggregated_metrics(agg)

    # Previous period
    prev_qs = base_qs if base_qs is not None else Execution.objects.all()
    prev_qs = prev_qs.filter(
        Q(job__project_id=project_id)
        & (
            Q(started_at__gte=prev_start_dt, started_at__lt=prev_end_dt)
            | Q(started_at__isnull=True, created_at__gte=prev_start_dt, created_at__lt=prev_end_dt)
        )
    )
    prev_agg = prev_qs.aggregate(**_base_metrics_aggregations())
    prev_metrics = _process_aggregated_metrics(prev_agg)

    comp_period = (
        f"previous {duration.days} day{'s' if duration.days > 1 else ''}"
        if duration.days >= 1
        else f"previous {duration.seconds // 3600} hour{'s' if (duration.seconds // 3600) > 1 else ''}"
    )

    metrics["executions"] = format_delta_metric(
        metrics["executions"], prev_metrics["executions"], comp_period
    )
    metrics["success_rate"] = format_delta_metric(
        metrics["success_rate"], prev_metrics["success_rate"], comp_period
    )
    metrics["failure_rate"] = format_delta_metric(
        metrics["failure_rate"], prev_metrics["failure_rate"], comp_period
    )
    metrics["retry_rate"] = format_delta_metric(
        metrics["retry_rate"], prev_metrics["retry_rate"], comp_period
    )
    metrics["average_duration_ms"] = format_delta_metric(
        metrics["average_duration_ms"], prev_metrics["average_duration_ms"], comp_period
    )
    metrics["p95_duration_ms"] = format_delta_metric(
        metrics["p95_duration_ms"], prev_metrics["p95_duration_ms"], comp_period
    )

    job_aggs = qs.values("job_id", "job__name", "job__task_identifier").annotate(
        executions=Count("id"),
        failures=Count("id", filter=Q(status=Execution.Status.FAILED)),
        retries=Count("id", filter=Q(retry_count__gt=0)),
        average_duration_ms=Avg("duration_ms"),
        p95_duration_ms=PercentileCont("duration_ms", 0.95),
    )

    healthy_jobs = 0
    degraded_jobs = 0
    critical_jobs = 0
    failing_jobs_list = []
    slow_jobs_list = []

    for j in job_aggs:
        job_total = j["executions"] or 0
        job_failures = j["failures"] or 0
        job_retries = j["retries"] or 0

        failure_rate = (job_failures / job_total * 100) if job_total > 0 else 0.0
        retry_rate = (job_retries / job_total * 100) if job_total > 0 else 0.0

        health = calculate_health_state(failure_rate, retry_rate)

        if health == "CRITICAL":
            critical_jobs += 1
        elif health == "DEGRADED":
            degraded_jobs += 1
        else:
            healthy_jobs += 1

        if job_failures > 0:
            failing_jobs_list.append(
                {
                    "job_id": j["job_id"],
                    "name": j["job__name"],
                    "task_identifier": j["job__task_identifier"],
                    "execution_count": job_total,
                    "failure_count": job_failures,
                    "failure_rate": round(failure_rate, 2),
                }
            )

        avg_dur = j["average_duration_ms"]
        p95_dur = j["p95_duration_ms"]
        if avg_dur is not None:
            slow_jobs_list.append(
                {
                    "job_id": j["job_id"],
                    "name": j["job__name"],
                    "task_identifier": j["job__task_identifier"],
                    "average_duration_ms": __round_dur(avg_dur),
                    "p95_duration_ms": __round_dur(p95_dur),
                }
            )

    # Sort in python
    top_failing_jobs = sorted(failing_jobs_list, key=lambda x: x["failure_count"], reverse=True)[
        :10
    ]
    slowest_jobs = sorted(
        slow_jobs_list,
        key=lambda x: (x["p95_duration_ms"] or 0, x["average_duration_ms"] or 0),
        reverse=True,
    )[:10]

    # Queue and worker summaries across the project
    queue_summary = _build_summary(qs, "queue")
    worker_summary = _build_summary(qs, "worker")

    # Errors
    errors = list(
        qs.exclude(error_type="")
        .values("error_type")
        .annotate(count=Count("id"), affected_jobs=Count("job_id", distinct=True))
        .order_by("-count")[:10]
    )

    overall_health = "HEALTHY"
    if critical_jobs > 0:
        overall_health = "CRITICAL"
    elif degraded_jobs > 0:
        overall_health = "DEGRADED"

    open_incidents = Incident.objects.filter(
        project_id=project_id, status__in=[Incident.Status.OPEN, Incident.Status.ACKNOWLEDGED]
    ).count()
    critical_incidents = Incident.objects.filter(
        project_id=project_id,
        status__in=[Incident.Status.OPEN, Incident.Status.ACKNOWLEDGED],
        severity=Incident.Severity.CRITICAL,
    ).count()

    rules = AlertRule.objects.filter(project_id=project_id, is_active=True, job__isnull=True)
    thresholds = {}
    for r in rules:
        if r.metric == AlertRule.MetricType.FAILURE_RATE:
            thresholds["failure_rate"] = r.threshold
        elif r.metric == AlertRule.MetricType.RETRY_RATE:
            thresholds["retry_rate"] = r.threshold
        elif r.metric == AlertRule.MetricType.P95_DURATION:
            thresholds["p95_duration"] = r.threshold

    metrics.update(
        {
            "project_id": project_id,
            "period": {"start": start_dt.isoformat(), "end": end_dt.isoformat()},
            "healthy_jobs": healthy_jobs,
            "degraded_jobs": degraded_jobs,
            "critical_jobs": critical_jobs,
            "health": overall_health,
            "top_failing_jobs": top_failing_jobs,
            "slowest_jobs": slowest_jobs,
            "queue_summary": queue_summary,
            "worker_summary": worker_summary,
            "errors": errors,
            "open_incidents": open_incidents,
            "critical_incidents": critical_incidents,
            "thresholds": thresholds,
        }
    )
    return metrics


def get_trend(qs, start_dt, end_dt, bucket_type="hour"):
    """
    Computes time-bucketed trend metrics for charts.
    """
    qs = qs.filter(
        Q(started_at__gte=start_dt, started_at__lt=end_dt)
        | Q(started_at__isnull=True, created_at__gte=start_dt, created_at__lt=end_dt)
    )

    trunc_func = TruncDay if bucket_type == "day" else TruncHour

    # Use Coalesce so we can bucket executions missing started_at by created_at
    buckets = (
        qs.annotate(sort_time=Coalesce("started_at", "created_at"))
        .annotate(bucket=trunc_func("sort_time"))
        .values("bucket")
        .annotate(
            executions=Count("id"),
            successes=Count("id", filter=Q(status=Execution.Status.SUCCESS)),
            failures=Count("id", filter=Q(status=Execution.Status.FAILED)),
            retries=Count("id", filter=Q(retry_count__gt=0)),
            average_duration_ms=Avg("duration_ms"),
            p95_duration_ms=PercentileCont("duration_ms", 0.95),
        )
        .order_by("bucket")
    )

    bucket_map = {b["bucket"]: b for b in buckets if b["bucket"]}
    trend_points = []

    current = start_dt
    while current < end_dt:
        if bucket_type == "day":
            bucket_dt = current.replace(hour=0, minute=0, second=0, microsecond=0)
            next_dt = bucket_dt + timedelta(days=1)
        else:
            bucket_dt = current.replace(minute=0, second=0, microsecond=0)
            next_dt = bucket_dt + timedelta(hours=1)

        b = bucket_map.get(bucket_dt)
        if b:
            total = b["executions"] or 0
            successes = b["successes"] or 0
            failures = b["failures"] or 0
            retries = b["retries"] or 0

            success_rate = (successes / total * 100) if total > 0 else 0.0
            failure_rate = (failures / total * 100) if total > 0 else 0.0
            retry_rate = (retries / total * 100) if total > 0 else 0.0

            p95_dur = b["p95_duration_ms"]
            avg_dur = b["average_duration_ms"]

            trend_points.append(
                {
                    "timestamp": bucket_dt.isoformat(),
                    "executions": total,
                    "successes": successes,
                    "failures": failures,
                    "retries": retries,
                    "success_rate": round(success_rate, 2),
                    "failure_rate": round(failure_rate, 2),
                    "retry_rate": round(retry_rate, 2),
                    "average_duration_ms": __round_dur(avg_dur),
                    "p95_duration_ms": __round_dur(p95_dur) if total >= 2 else None,
                }
            )
        else:
            trend_points.append(
                {
                    "timestamp": bucket_dt.isoformat(),
                    "executions": 0,
                    "successes": 0,
                    "failures": 0,
                    "retries": 0,
                    "success_rate": 0.0,
                    "failure_rate": 0.0,
                    "retry_rate": 0.0,
                    "average_duration_ms": None,
                    "p95_duration_ms": None,
                }
            )

        # Ensure we don't infinitely loop if something is weird
        if next_dt <= current:
            break
        current = next_dt

    return {"trend": trend_points}
