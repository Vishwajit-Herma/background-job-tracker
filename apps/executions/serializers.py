from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import Execution, ExecutionEvent


class ExecutionSerializer(serializers.ModelSerializer):
    """
    Standard serializer for retrieving and listing Executions in the human-facing API.
    All fields are read-only since humans do not edit telemetry.
    """

    class Meta:
        model = Execution
        fields = [
            "id",
            "job",
            "external_id",
            "status",
            "last_event_at",
            "started_at",
            "finished_at",
            "duration_ms",
            "framework",
            "queue",
            "worker",
            "retry_count",
            "error_type",
            "error_message",
            "traceback",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ExecutionEventSerializer(serializers.ModelSerializer):
    """
    Serializer for retrieving historical execution telemetry events.
    All fields are read-only since events are immutable.
    """

    class Meta:
        model = ExecutionEvent
        fields = [
            "id",
            "execution",
            "event_id",
            "status",
            "event_timestamp",
            "received_at",
            "started_at",
            "finished_at",
            "duration_ms",
            "framework",
            "queue",
            "worker",
            "retry_count",
            "error_type",
            "error_message",
            "traceback",
            "metadata",
        ]
        read_only_fields = fields


class ExecutionIngestSerializer(serializers.Serializer):
    """
    Validates a single execution telemetry payload from the SDK.
    """

    event_id = serializers.CharField(max_length=255, required=True, allow_blank=False)
    external_id = serializers.CharField(max_length=255, required=True, allow_blank=False)
    task_identifier = serializers.CharField(max_length=255, required=True, allow_blank=False)
    event_timestamp = serializers.DateTimeField(required=True)

    status = serializers.ChoiceField(
        choices=Execution.Status.choices, default=Execution.Status.PENDING
    )

    started_at = serializers.DateTimeField(required=False, allow_null=True)
    finished_at = serializers.DateTimeField(required=False, allow_null=True)
    duration_ms = serializers.IntegerField(required=False, allow_null=True, min_value=0)

    framework = serializers.CharField(
        max_length=50, required=False, allow_blank=True, allow_null=True, default=""
    )
    queue = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True, default=""
    )
    worker = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True, default=""
    )
    retry_count = serializers.IntegerField(required=False, default=0, min_value=0)

    error_type = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    error_message = serializers.CharField(
        max_length=50000, required=False, allow_blank=True, default=""
    )
    traceback = serializers.CharField(
        max_length=100000, required=False, allow_blank=True, default=""
    )

    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be a JSON object (dictionary).")
        return value

    def validate(self, data):
        started_at = data.get("started_at")
        finished_at = data.get("finished_at")

        if started_at and finished_at and started_at > finished_at:
            raise serializers.ValidationError(
                {"started_at": "started_at cannot be after finished_at."}
            )

        # Django convention: use empty string instead of null for CharFields
        if data.get("queue") is None:
            data["queue"] = ""
        if data.get("worker") is None:
            data["worker"] = ""

        return data


class ExecutionBatchIngestSerializer(serializers.Serializer):
    """
    Validates a batch payload of executions.

    API Semantic Definitions:
    - accepted: Number of unique telemetry events successfully persisted/processed. Accepted counts successfully persisted telemetry events, not Execution rows updated.
    - duplicates: Events whose event_id was already seen for the same Execution, including retries of an already persisted event.
    - rejected: Events rejected because of validation or business rules such as inactive/deleted Jobs.
    """

    executions = serializers.ListField(
        child=ExecutionIngestSerializer(),
        allow_empty=False,
    )

    def validate_executions(self, value):
        max_batch_size = getattr(settings, "MAX_EXECUTION_BATCH_SIZE", 500)
        if len(value) > max_batch_size:
            raise ValidationError(
                f"Batch size exceeds the maximum limit of {max_batch_size} executions per request."
            )
        return value


class AnalyticsQuerySerializer(serializers.Serializer):
    """
    Validates query parameters for analytics endpoints.
    """

    start = serializers.DateTimeField(required=False)
    end = serializers.DateTimeField(required=False)
    range = serializers.ChoiceField(
        choices=[
            "1h",
            "last_1_hour",
            "6h",
            "last_6_hours",
            "24h",
            "last_24_hours",
            "7d",
            "last_7_days",
            "30d",
            "last_30_days",
        ],
        required=False,
    )
    jobs = serializers.CharField(required=False, help_text="Comma-separated list of Job IDs")
    queue = serializers.CharField(required=False)
    worker = serializers.CharField(required=False)

    def validate(self, data):
        start = data.get("start")
        end = data.get("end")

        if start and end:
            if start >= end:
                raise serializers.ValidationError("start must be before end.")
            if (end - start).days > 90:
                raise serializers.ValidationError(
                    "Time range cannot exceed 90 days to prevent excessive data aggregation."
                )
        elif start and not end:
            if (timezone.now() - start).days > 90:
                raise serializers.ValidationError(
                    "Time range cannot exceed 90 days to prevent excessive data aggregation."
                )

        # Parse comma-separated jobs
        jobs_str = data.get("jobs", "")
        if jobs_str:
            try:
                data["jobs"] = [int(j.strip()) for j in jobs_str.split(",") if j.strip()]
            except ValueError as e:
                raise serializers.ValidationError(
                    {"jobs": "Must be a comma-separated list of integers."}
                ) from e

        return data


class TrendPointSerializer(serializers.Serializer):
    timestamp = serializers.DateTimeField()
    executions = serializers.IntegerField()
    successes = serializers.IntegerField()
    failures = serializers.IntegerField()
    retries = serializers.IntegerField()
    success_rate = serializers.FloatField()
    failure_rate = serializers.FloatField(required=False)
    retry_rate = serializers.FloatField(required=False)
    average_duration_ms = serializers.FloatField(allow_null=True)
    p95_duration_ms = serializers.FloatField(allow_null=True)


class TrendResponseSerializer(serializers.Serializer):
    trend = TrendPointSerializer(many=True)


class AnalyticsQueueSummarySerializer(serializers.Serializer):
    queue = serializers.CharField()
    count = serializers.IntegerField()
    failures = serializers.IntegerField()
    retries = serializers.IntegerField()
    successes = serializers.IntegerField()
    success_rate = serializers.FloatField()
    failure_rate = serializers.FloatField()
    retry_rate = serializers.FloatField()


class AnalyticsWorkerSummarySerializer(serializers.Serializer):
    worker = serializers.CharField()
    count = serializers.IntegerField()
    failures = serializers.IntegerField()
    retries = serializers.IntegerField()
    successes = serializers.IntegerField()
    success_rate = serializers.FloatField()
    failure_rate = serializers.FloatField()
    retry_rate = serializers.FloatField()


class AnalyticsErrorSerializer(serializers.Serializer):
    error_type = serializers.CharField()
    count = serializers.IntegerField()
    affected_jobs = serializers.IntegerField(required=False)


class PeriodSerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()


class DeltaSerializer(serializers.Serializer):
    current = serializers.FloatField(allow_null=True)
    previous = serializers.FloatField(allow_null=True)
    delta_points = serializers.FloatField(allow_null=True)
    delta_percent = serializers.FloatField(allow_null=True)
    comparison_period = serializers.CharField(allow_null=True)


class ThresholdsSerializer(serializers.Serializer):
    failure_rate = serializers.FloatField(allow_null=True, required=False)
    retry_rate = serializers.FloatField(allow_null=True, required=False)
    p95_duration = serializers.FloatField(allow_null=True, required=False)


class JobAnalyticsSerializer(serializers.Serializer):
    job_id = serializers.IntegerField()
    job_name = serializers.CharField()
    task_identifier = serializers.CharField()
    period = PeriodSerializer()
    executions = DeltaSerializer()
    successes = serializers.IntegerField()
    failures = serializers.IntegerField()
    retries = serializers.IntegerField()
    success_rate = DeltaSerializer()
    failure_rate = DeltaSerializer()
    retry_rate = DeltaSerializer()
    average_duration_ms = DeltaSerializer()
    p50_duration_ms = serializers.FloatField(allow_null=True)
    p95_duration_ms = DeltaSerializer()
    p99_duration_ms = serializers.FloatField(allow_null=True)
    health = serializers.CharField()
    open_incidents = serializers.IntegerField()
    critical_incidents = serializers.IntegerField()
    queue_summary = AnalyticsQueueSummarySerializer(many=True)
    worker_summary = AnalyticsWorkerSummarySerializer(many=True)
    errors = AnalyticsErrorSerializer(many=True)
    thresholds = ThresholdsSerializer(required=False)


class FailingJobSerializer(serializers.Serializer):
    job_id = serializers.IntegerField()
    name = serializers.CharField()
    task_identifier = serializers.CharField()
    execution_count = serializers.IntegerField()
    failure_count = serializers.IntegerField()
    failure_rate = serializers.FloatField()


class SlowJobSerializer(serializers.Serializer):
    job_id = serializers.IntegerField()
    name = serializers.CharField()
    task_identifier = serializers.CharField()
    average_duration_ms = serializers.FloatField()
    p95_duration_ms = serializers.FloatField(allow_null=True)


class ProjectAnalyticsSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    period = PeriodSerializer()
    executions = DeltaSerializer()
    successes = serializers.IntegerField()
    failures = serializers.IntegerField()
    retries = serializers.IntegerField()
    success_rate = DeltaSerializer()
    failure_rate = DeltaSerializer()
    retry_rate = DeltaSerializer()
    average_duration_ms = DeltaSerializer()
    p50_duration_ms = serializers.FloatField(allow_null=True)
    p95_duration_ms = DeltaSerializer()
    p99_duration_ms = serializers.FloatField(allow_null=True)
    healthy_jobs = serializers.IntegerField()
    degraded_jobs = serializers.IntegerField()
    critical_jobs = serializers.IntegerField()
    health = serializers.CharField()
    open_incidents = serializers.IntegerField()
    critical_incidents = serializers.IntegerField()
    top_failing_jobs = FailingJobSerializer(many=True)
    slowest_jobs = SlowJobSerializer(many=True)
    queue_summary = AnalyticsQueueSummarySerializer(many=True)
    worker_summary = AnalyticsWorkerSummarySerializer(many=True)
    errors = AnalyticsErrorSerializer(many=True)
    thresholds = ThresholdsSerializer(required=False)
