from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


class AlertRule(models.Model):
    """Configuration for when an incident should be triggered."""

    class MetricType(models.TextChoices):
        FAILURE_RATE = "FAILURE_RATE", _("Failure Rate")
        RETRY_RATE = "RETRY_RATE", _("Retry Rate")
        P95_DURATION = "P95_DURATION", _("P95 Duration")
        MISSED_EXECUTION = "MISSED_EXECUTION", _("Missed Execution")
        STALLED_EXECUTION = "STALLED_EXECUTION", _("Stalled Execution")
        OVERDUE_EXECUTION = "OVERDUE_EXECUTION", _("Overdue Execution")

    class Severity(models.TextChoices):
        DEGRADED = "DEGRADED", _("Degraded")
        CRITICAL = "CRITICAL", _("Critical")

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="alert_rules",
        verbose_name=_("project"),
    )
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.CASCADE,
        related_name="alert_rules",
        null=True,
        blank=True,
        verbose_name=_("job"),
    )
    metric = models.CharField(
        _("metric"),
        max_length=20,
        choices=MetricType.choices,
    )
    threshold = models.FloatField(
        _("threshold"),
        help_text=_("Percentage (0-100) for rates, milliseconds for duration."),
    )
    window_minutes = models.PositiveIntegerField(
        _("window in minutes"),
        default=60,
        validators=[MinValueValidator(1), MaxValueValidator(1440)],
        help_text=_("Evaluation time window (e.g., last 60 minutes)"),
    )
    severity = models.CharField(
        _("severity"),
        max_length=20,
        choices=Severity.choices,
        default=Severity.DEGRADED,
    )
    is_active = models.BooleanField(
        _("is active"),
        default=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("alert rule")
        verbose_name_plural = _("alert rules")
        ordering = ["-created_at"]

    def __str__(self):
        target = self.job.name if self.job else "Project-level"
        return f"{target} - {self.get_metric_display()} >= {self.threshold} ({self.get_severity_display()})"

    def clean(self):
        super().clean()

        if self.project.is_deleted or self.project.status != "active":
            raise ValidationError(
                {"project": _("Cannot create an alert rule for an inactive or deleted project.")}
            )

        if self.job:
            if self.job.project_id != self.project_id:
                raise ValidationError(
                    {"job": _("The selected job must belong to the selected project.")}
                )

            if self.job.is_deleted or self.job.status != "active":
                raise ValidationError(
                    {"job": _("Cannot create an alert rule for an inactive or deleted job.")}
                )

        # Validate threshold based on metric type
        if self.metric in [self.MetricType.FAILURE_RATE, self.MetricType.RETRY_RATE]:
            if not (0 <= self.threshold <= 100):
                raise ValidationError(
                    {"threshold": _("Threshold for rates must be a percentage between 0 and 100.")}
                )
        elif self.metric == self.MetricType.P95_DURATION and self.threshold <= 0:
            raise ValidationError(
                {"threshold": _("Threshold for duration must be greater than 0 milliseconds.")}
            )
        elif (
            self.metric
            in [
                self.MetricType.MISSED_EXECUTION,
                self.MetricType.STALLED_EXECUTION,
                self.MetricType.OVERDUE_EXECUTION,
            ]
            and self.threshold < 0
        ):
            raise ValidationError(
                {"threshold": _("Threshold for reliability metrics must be non-negative.")}
            )
