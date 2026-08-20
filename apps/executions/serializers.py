from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import Execution


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
            "started_at",
            "finished_at",
            "duration_ms",
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


class ExecutionIngestSerializer(serializers.Serializer):
    """
    Validates a single execution telemetry payload from the SDK.
    """

    external_id = serializers.CharField(max_length=255, required=True, allow_blank=False)
    task_identifier = serializers.CharField(max_length=255, required=True, allow_blank=False)
    event_timestamp = serializers.DateTimeField(required=True)

    status = serializers.ChoiceField(
        choices=Execution.Status.choices, default=Execution.Status.PENDING
    )

    started_at = serializers.DateTimeField(required=False, allow_null=True)
    finished_at = serializers.DateTimeField(required=False, allow_null=True)
    duration_ms = serializers.IntegerField(required=False, allow_null=True, min_value=0)

    queue = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    worker = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
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

        return data


class ExecutionBatchIngestSerializer(serializers.Serializer):
    """
    Validates a batch payload of executions.

    API Semantic Definitions:
    - accepted: The total number of unique execution events that were chronologically valid and successfully processed/merged. This counts telemetry events, not database rows.
    - duplicates: Events that were ignored because they were chronologically stale (older than or equal to the stored last_event_at) or exact timestamp duplicates within the same batch.
    - rejected: Events that were dropped because their target Job was INACTIVE or deleted.
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
