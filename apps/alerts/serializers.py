from rest_framework import serializers
from .models import AlertRule


class AlertRuleSerializer(serializers.ModelSerializer):
    """
    Serializer for managing Alert Rules tied to Projects and optional Jobs.
    Handles metric-specific threshold validation for rates, duration, and anomaly detection.
    """

    threshold = serializers.FloatField(required=False, default=0.0)

    class Meta:
        model = AlertRule
        fields = [
            "id",
            "project",
            "job",
            "metric",
            "threshold",
            "window_minutes",
            "severity",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        """
        Ensure job belongs to the project.
        """
        project = data.get("project") or (self.instance.project if self.instance else None)
        job = data.get("job")

        # If job is provided but missing in data (e.g. PATCH), get from instance
        if "job" not in data and self.instance:
            job = self.instance.job

        if project and (project.is_deleted or project.status != "active"):
            raise serializers.ValidationError(
                {"project": "Cannot create an alert rule for an inactive or deleted project."}
            )

        if job and project and job.project_id != project.id:
            raise serializers.ValidationError({"job": "Job must belong to the specified project."})

        if job and (job.is_deleted or job.status != "active"):
            raise serializers.ValidationError(
                {"job": "Cannot create an alert rule for an inactive or deleted job."}
            )

        # Validate threshold
        metric = data.get("metric") or getattr(self.instance, "metric", None)
        threshold = data.get("threshold")
        if threshold is None and self.instance:
            threshold = self.instance.threshold

        if metric in [AlertRule.MetricType.FAILURE_RATE, AlertRule.MetricType.RETRY_RATE]:
            if threshold is None:
                raise serializers.ValidationError(
                    {"threshold": "Threshold is required for rate alerts."}
                )
            if not (0 <= threshold <= 100):
                raise serializers.ValidationError(
                    {"threshold": "Threshold for rates must be a percentage between 0 and 100."}
                )
        elif metric == AlertRule.MetricType.P95_DURATION:
            if threshold is None or threshold <= 0:
                raise serializers.ValidationError(
                    {"threshold": "Threshold for duration must be greater than 0 milliseconds."}
                )
        elif metric in [
            AlertRule.MetricType.MISSED_EXECUTION,
            AlertRule.MetricType.STALLED_EXECUTION,
            AlertRule.MetricType.OVERDUE_EXECUTION,
            AlertRule.MetricType.FAILURE_RATE_ANOMALY,
            AlertRule.MetricType.RETRY_RATE_ANOMALY,
            AlertRule.MetricType.DURATION_ANOMALY,
            AlertRule.MetricType.EXECUTION_VOLUME_ANOMALY,
        ]:
            if threshold is None:
                data["threshold"] = 0.0
            elif threshold < 0:
                raise serializers.ValidationError(
                    {"threshold": "Threshold for reliability/anomaly alerts must be non-negative."}
                )

        return data

    def validate_project(self, value):
        if self.instance and self.instance.project_id != value.id:
            raise serializers.ValidationError("Project cannot be changed after creation.")
        return value
