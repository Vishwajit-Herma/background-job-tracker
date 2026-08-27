from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.jobs.models import Job
from apps.executions.models import Execution
from apps.incidents.models import Incident


class JobExpectation(models.Model):
    """
    Configuration for expected job execution schedule and performance boundaries.
    """

    job = models.OneToOneField(
        Job,
        on_delete=models.CASCADE,
        related_name="expectation",
        verbose_name=_("job"),
    )
    expected_interval_seconds = models.PositiveIntegerField(
        _("expected interval (seconds)"),
        null=True,
        blank=True,
        help_text=_("Expected cadence/interval between job executions in seconds."),
    )
    max_runtime_seconds = models.PositiveIntegerField(
        _("maximum runtime (seconds)"),
        null=True,
        blank=True,
        help_text=_("Maximum runtime before a running execution is considered stalled."),
    )
    grace_period_seconds = models.PositiveIntegerField(
        _("grace period (seconds)"),
        default=0,
        help_text=_(
            "Buffer seconds added to expected interval before declaring a missed execution."
        ),
    )
    max_queue_delay_seconds = models.PositiveIntegerField(
        _("maximum queue delay (seconds)"),
        default=300,
        help_text=_(
            "Maximum seconds an execution can remain pending in queue before considered overdue."
        ),
    )
    is_enabled = models.BooleanField(
        _("is enabled"),
        default=True,
        help_text=_("Whether reliability evaluation is enabled for this job."),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("job expectation")
        verbose_name_plural = _("job expectations")

    def __str__(self):
        return f"Expectation for Job {self.job_id} ({self.job.name})"

    def clean(self):
        super().clean()
        if self.job_id:
            if (
                getattr(self.job, "is_deleted", False)
                or getattr(self.job, "status", "active") != "active"
            ):
                raise ValidationError(
                    {"job": _("Cannot set expectations for an inactive or deleted job.")}
                )
            project = getattr(self.job, "project", None)
            if project and (project.is_deleted or project.status != "active"):
                raise ValidationError(
                    {
                        "job": _(
                            "Cannot set expectations for a job in an inactive or deleted project."
                        )
                    }
                )

        if self.expected_interval_seconds is not None and self.expected_interval_seconds < 1:
            raise ValidationError(
                {"expected_interval_seconds": _("Expected interval must be at least 1 second.")}
            )

        if self.max_runtime_seconds is not None and self.max_runtime_seconds < 1:
            raise ValidationError(
                {"max_runtime_seconds": _("Maximum runtime must be at least 1 second.")}
            )

        if self.grace_period_seconds is not None and self.grace_period_seconds < 0:
            raise ValidationError({"grace_period_seconds": _("Grace period must be non-negative.")})

        if self.max_queue_delay_seconds is not None and self.max_queue_delay_seconds < 0:
            raise ValidationError(
                {"max_queue_delay_seconds": _("Maximum queue delay must be non-negative.")}
            )


class JobBaseline(models.Model):
    """
    Statistical baseline of normal execution behavior derived from telemetry.
    Does not duplicate raw execution records.
    """

    job = models.OneToOneField(
        Job,
        on_delete=models.CASCADE,
        related_name="baseline",
        verbose_name=_("job"),
    )
    sample_window_days = models.PositiveIntegerField(
        _("sample window (days)"),
        default=7,
        help_text=_("Number of historical days analyzed to derive baseline metrics."),
    )
    total_executions_analyzed = models.PositiveIntegerField(
        _("total executions analyzed"),
        default=0,
    )
    is_sufficient = models.BooleanField(
        _("is sufficient"),
        default=False,
        help_text=_(
            "True if sample size is sufficient to establish a statistically valid baseline."
        ),
    )

    avg_interval_seconds = models.FloatField(_("average interval (seconds)"), null=True, blank=True)
    median_interval_seconds = models.FloatField(
        _("median interval (seconds)"), null=True, blank=True
    )
    min_interval_seconds = models.FloatField(_("minimum interval (seconds)"), null=True, blank=True)
    max_interval_seconds = models.FloatField(_("maximum interval (seconds)"), null=True, blank=True)

    avg_runtime_ms = models.FloatField(_("average runtime (ms)"), null=True, blank=True)
    p50_runtime_ms = models.FloatField(_("p50 runtime (ms)"), null=True, blank=True)
    p95_runtime_ms = models.FloatField(_("p95 runtime (ms)"), null=True, blank=True)
    p99_runtime_ms = models.FloatField(_("p99 runtime (ms)"), null=True, blank=True)

    failure_rate = models.FloatField(_("failure rate (%)"), null=True, blank=True)
    retry_rate = models.FloatField(_("retry rate (%)"), null=True, blank=True)
    avg_hourly_volume = models.FloatField(_("average hourly volume"), null=True, blank=True)

    metrics_summary = models.JSONField(_("metrics summary"), default=dict, blank=True)
    calculated_at = models.DateTimeField(_("calculated at"), auto_now=True)

    class Meta:
        verbose_name = _("job baseline")
        verbose_name_plural = _("job baselines")

    def __str__(self):
        return f"Baseline for Job {self.job_id} (Sufficient: {self.is_sufficient})"


class ReliabilityFinding(models.Model):
    """
    Tracks active and historical reliability issues (Missed, Stalled, Overdue, Anomalies)
    for a job, along with recovery lifecycle state.
    """

    class ConditionType(models.TextChoices):
        MISSED_EXECUTION = "MISSED_EXECUTION", _("Missed Execution")
        STALLED_EXECUTION = "STALLED_EXECUTION", _("Stalled Execution")
        OVERDUE_EXECUTION = "OVERDUE_EXECUTION", _("Overdue Execution")
        FAILURE_RATE_ANOMALY = "FAILURE_RATE_ANOMALY", _("Failure Rate Anomaly")
        RETRY_RATE_ANOMALY = "RETRY_RATE_ANOMALY", _("Retry Rate Anomaly")
        DURATION_ANOMALY = "DURATION_ANOMALY", _("Duration Anomaly")
        EXECUTION_VOLUME_ANOMALY = "EXECUTION_VOLUME_ANOMALY", _("Execution Volume Anomaly")

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", _("Active")
        RECOVERED = "RECOVERED", _("Recovered")

    class Severity(models.TextChoices):
        DEGRADED = "DEGRADED", _("Degraded")
        CRITICAL = "CRITICAL", _("Critical")

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="reliability_findings",
        verbose_name=_("job"),
    )
    execution = models.ForeignKey(
        Execution,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reliability_findings",
        verbose_name=_("execution"),
        help_text=_("Specific execution that stalled or became overdue, if applicable."),
    )
    incident = models.ForeignKey(
        Incident,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reliability_findings",
        verbose_name=_("incident"),
    )
    condition_type = models.CharField(
        _("condition type"),
        max_length=30,
        choices=ConditionType.choices,
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    severity = models.CharField(
        _("severity"),
        max_length=20,
        choices=Severity.choices,
        default=Severity.DEGRADED,
    )
    details = models.JSONField(
        _("details"),
        default=dict,
        blank=True,
        help_text=_("Metadata snapshot of observed values and evaluation details."),
    )

    detected_at = models.DateTimeField(_("detected at"), auto_now_add=True)
    recovered_at = models.DateTimeField(_("recovered at"), null=True, blank=True)
    last_evaluated_at = models.DateTimeField(_("last evaluated at"), auto_now=True)

    class Meta:
        verbose_name = _("reliability finding")
        verbose_name_plural = _("reliability findings")
        ordering = ["-detected_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "condition_type"],
                condition=models.Q(status="ACTIVE", execution__isnull=True),
                name="unique_active_job_level_finding",
            ),
            models.UniqueConstraint(
                fields=["job", "condition_type", "execution"],
                condition=models.Q(status="ACTIVE", execution__isnull=False),
                name="unique_active_execution_level_finding",
            ),
        ]
        indexes = [
            models.Index(fields=["job", "status"]),
            models.Index(fields=["condition_type", "status"]),
            models.Index(fields=["detected_at"]),
        ]

    def __str__(self):
        return f"{self.condition_type} on Job {self.job_id} ({self.status})"

    def clean(self):
        super().clean()
        if self.execution and self.execution.job_id != self.job_id:
            raise ValidationError({"execution": _("The execution must belong to the same job.")})
        if self.incident and self.incident.job_id != self.job_id:
            raise ValidationError({"incident": _("The incident must belong to the same job.")})
