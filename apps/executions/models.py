from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.jobs.models import Job


class Execution(models.Model):
    """
    Represents a single execution of a background Job.
    Data is generally ingested from an external system (e.g. Celery workers via SDK).
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Running")
        SUCCESS = "success", _("Success")
        FAILED = "failed", _("Failed")
        RETRY = "retry", _("Retry")
        CANCELLED = "cancelled", _("Cancelled")

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="executions",
        verbose_name=_("job"),
    )

    # The stable identifier reported by the external system (e.g., Celery task UUID)
    external_id = models.CharField(_("external ID"), max_length=255)

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    last_event_at = models.DateTimeField(_("last event at"))
    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    finished_at = models.DateTimeField(_("finished at"), null=True, blank=True)
    duration_ms = models.IntegerField(_("duration in ms"), null=True, blank=True)

    queue = models.CharField(_("queue"), max_length=255, blank=True)
    worker = models.CharField(_("worker"), max_length=255, blank=True)
    retry_count = models.IntegerField(_("retry count"), default=0)

    error_type = models.CharField(_("error type"), max_length=255, blank=True)
    error_message = models.TextField(_("error message"), blank=True)
    traceback = models.TextField(_("traceback"), blank=True)

    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("execution")
        verbose_name_plural = _("executions")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "external_id"],
                name="unique_execution_external_id_per_job",
            )
        ]

    def __str__(self):
        return f"Execution {self.external_id} ({self.status})"
