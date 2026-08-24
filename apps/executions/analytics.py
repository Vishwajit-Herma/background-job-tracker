from datetime import timedelta

from django.db.models import Aggregate, Avg, Count, FloatField, Q
from django.db.models.functions import Coalesce, TruncDay, TruncHour
from django.utils import timezone as django_timezone

from apps.executions.models import Execution
from apps.executions.serializers import AnalyticsQuerySerializer


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
        p50 = round(agg["p50_duration_ms"]) if agg.get("p50_duration_ms") is not None else None
        p95 = round(agg["p95_duration_ms"]) if agg.get("p95_duration_ms") is not None else None
        p99 = round(agg["p99_duration_ms"]) if agg.get("p99_duration_ms") is not None else None

    avg_duration = (
        round(agg["average_duration_ms"]) if agg.get("average_duration_ms") is not None else None
    )

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
        if time_range == "last_1_hour":
            start = end - timedelta(hours=1)
        elif time_range == "last_7_days":
            start = end - timedelta(days=7)
        elif time_range == "last_30_days":
            start = end - timedelta(days=30)
        else:
            # Default to last_24_hours
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


def get_job_analytics(job_id, start_dt, end_dt, base_qs=None):
    """
    Computes Job-level analytics.
    """
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
    queue_summary = list(
        qs.exclude(queue="")
        .values("queue")
        .annotate(count=Count("id"), failures=Count("id", filter=Q(status=Execution.Status.FAILED)))
        .order_by("-count")
    )

    worker_summary = list(
        qs.exclude(worker="")
        .values("worker")
        .annotate(count=Count("id"), failures=Count("id", filter=Q(status=Execution.Status.FAILED)))
        .order_by("-count")
    )

    # Errors
    errors = list(
        qs.exclude(error_type="")
        .values("error_type")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    metrics = _process_aggregated_metrics(agg)
    metrics.update(
        {
            "job_id": job_id,
            "period": {"start": start_dt.isoformat(), "end": end_dt.isoformat()},
            "health": calculate_health_state(metrics["failure_rate"], metrics["retry_rate"]),
            "queue_summary": queue_summary,
            "worker_summary": worker_summary,
            "errors": errors,
        }
    )
    return metrics


def get_project_analytics(project_id, start_dt, end_dt, base_qs=None):
    """
    Computes Project-level analytics without N+1 queries.
    """
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
                    "average_duration_ms": round(avg_dur),
                    "p95_duration_ms": round(p95_dur) if p95_dur is not None else None,
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
    queue_summary = list(
        qs.exclude(queue="")
        .values("queue")
        .annotate(count=Count("id"), failures=Count("id", filter=Q(status=Execution.Status.FAILED)))
        .order_by("-count")
    )

    worker_summary = list(
        qs.exclude(worker="")
        .values("worker")
        .annotate(count=Count("id"), failures=Count("id", filter=Q(status=Execution.Status.FAILED)))
        .order_by("-count")
    )

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

            success_rate = (successes / total * 100) if total > 0 else 0.0

            p95_dur = b["p95_duration_ms"]
            avg_dur = b["average_duration_ms"]

            trend_points.append(
                {
                    "timestamp": bucket_dt.isoformat(),
                    "executions": total,
                    "successes": successes,
                    "failures": failures,
                    "success_rate": round(success_rate, 2),
                    "average_duration_ms": round(avg_dur) if avg_dur is not None else None,
                    "p95_duration_ms": round(p95_dur)
                    if p95_dur is not None and total >= 2
                    else None,
                }
            )
        else:
            trend_points.append(
                {
                    "timestamp": bucket_dt.isoformat(),
                    "executions": 0,
                    "successes": 0,
                    "failures": 0,
                    "success_rate": 0.0,
                    "average_duration_ms": None,
                    "p95_duration_ms": None,
                }
            )

        # Ensure we don't infinitely loop if something is weird
        if next_dt <= current:
            break
        current = next_dt

    return {"trend": trend_points}
