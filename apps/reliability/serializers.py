from rest_framework import serializers

from apps.reliability.models import JobExpectation, JobBaseline, ReliabilityFinding


class JobExpectationSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobExpectation
        fields = [
            "id",
            "job",
            "expected_interval_seconds",
            "max_runtime_seconds",
            "grace_period_seconds",
            "max_queue_delay_seconds",
            "is_enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "job", "created_at", "updated_at"]

    def validate_expected_interval_seconds(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError("Expected interval must be at least 1 second.")
        return value

    def validate_max_runtime_seconds(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError("Maximum runtime must be at least 1 second.")
        return value

    def validate_grace_period_seconds(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Grace period must be non-negative.")
        return value

    def validate_max_queue_delay_seconds(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Maximum queue delay must be non-negative.")
        return value

    def validate(self, attrs):
        job = attrs.get("job") or (self.instance.job if self.instance else None)
        if job:
            if getattr(job, "is_deleted", False) or getattr(job, "status", "active") != "active":
                raise serializers.ValidationError(
                    {"job": "Cannot configure expectations for an inactive or deleted job."}
                )
            project = getattr(job, "project", None)
            if project and (project.is_deleted or project.status != "active"):
                raise serializers.ValidationError(
                    {
                        "job": "Cannot configure expectations for a job in an inactive or deleted project."
                    }
                )
        return attrs


class JobBaselineSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobBaseline
        fields = [
            "id",
            "job",
            "sample_window_days",
            "total_executions_analyzed",
            "is_sufficient",
            "avg_interval_seconds",
            "median_interval_seconds",
            "min_interval_seconds",
            "max_interval_seconds",
            "avg_runtime_ms",
            "p50_runtime_ms",
            "p95_runtime_ms",
            "p99_runtime_ms",
            "metrics_summary",
            "calculated_at",
        ]
        read_only_fields = fields


class ReliabilityFindingSerializer(serializers.ModelSerializer):
    job_name = serializers.CharField(source="job.name", read_only=True)
    project_id = serializers.IntegerField(source="job.project_id", read_only=True)
    project_name = serializers.CharField(source="job.project.name", read_only=True)

    class Meta:
        model = ReliabilityFinding
        fields = [
            "id",
            "job",
            "job_name",
            "project_id",
            "project_name",
            "execution",
            "incident",
            "condition_type",
            "status",
            "severity",
            "details",
            "detected_at",
            "recovered_at",
            "last_evaluated_at",
        ]
        read_only_fields = fields

    def validate(self, attrs):
        job = attrs.get("job") or (self.instance.job if self.instance else None)
        execution = attrs.get("execution") or (self.instance.execution if self.instance else None)
        incident = attrs.get("incident") or (self.instance.incident if self.instance else None)

        if job and execution and execution.job_id != job.id:
            raise serializers.ValidationError(
                {"execution": "The execution must belong to the same job."}
            )
        if job and incident and incident.job_id != job.id:
            raise serializers.ValidationError(
                {"incident": "The incident must belong to the same job."}
            )
        return attrs


class LatestExecutionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    duration_ms = serializers.IntegerField(allow_null=True)
    last_event_at = serializers.CharField()


class JobReliabilityOverviewSerializer(serializers.Serializer):
    job_id = serializers.IntegerField()
    job_name = serializers.CharField()
    task_identifier = serializers.CharField()
    current_state = serializers.CharField()
    is_enabled = serializers.BooleanField()
    expectation_source = serializers.CharField()
    expected_interval_seconds = serializers.IntegerField(allow_null=True)
    max_runtime_seconds = serializers.IntegerField(allow_null=True)
    grace_period_seconds = serializers.IntegerField()
    last_execution_at = serializers.CharField(allow_null=True)
    next_expected_at = serializers.CharField(allow_null=True)
    missed_after_at = serializers.CharField(allow_null=True)
    overdue_by_seconds = serializers.IntegerField()
    latest_execution = LatestExecutionSerializer(allow_null=True)
    active_findings = ReliabilityFindingSerializer(many=True)
    recent_findings = ReliabilityFindingSerializer(many=True)
    baseline = JobBaselineSerializer(allow_null=True)
    expectation = JobExpectationSerializer(allow_null=True)


class JobReliabilitySummarySerializer(serializers.Serializer):
    job_id = serializers.IntegerField()
    job_name = serializers.CharField()
    task_identifier = serializers.CharField()
    current_state = serializers.CharField()
    expectation_source = serializers.CharField()
    expected_interval_seconds = serializers.IntegerField(allow_null=True)
    max_runtime_seconds = serializers.IntegerField(allow_null=True)
    last_execution_at = serializers.CharField(allow_null=True)
    next_expected_at = serializers.CharField(allow_null=True)
    missed_after_at = serializers.CharField(allow_null=True)
    overdue_by_seconds = serializers.IntegerField()
    active_findings_count = serializers.IntegerField()


class ProjectReliabilityOverviewSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    project_name = serializers.CharField()
    total_jobs = serializers.IntegerField()
    healthy_jobs_count = serializers.IntegerField()
    missed_jobs_count = serializers.IntegerField()
    stalled_jobs_count = serializers.IntegerField()
    overdue_jobs_count = serializers.IntegerField()
    active_findings_count = serializers.IntegerField()
    jobs = JobReliabilitySummarySerializer(many=True)


class BaselineRecalculateQuerySerializer(serializers.Serializer):
    sample_window_days = serializers.IntegerField(
        default=7,
        min_value=1,
        max_value=90,
        required=False,
        help_text="Number of sample days for baseline calculation (between 1 and 90).",
    )
