from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.config_management.models import AuditModel
from apps.projects.models import Project


class TaskRegistry(models.Model):
    """
    A record of tasks observed by the SDK on customer Celery workers.
    This is independent of the Job lifecycle and acts as the source of truth
    for task registration status.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="task_registries", verbose_name=_("project")
    )
    task_identifier = models.CharField(_("task identifier"), max_length=255)
    task_name = models.CharField(_("task name"), max_length=255, blank=True)
    first_seen_at = models.DateTimeField(_("first seen at"), auto_now_add=True)
    last_seen_at = models.DateTimeField(_("last seen at"), auto_now=True)

    class Meta:
        verbose_name = _("task registry entry")
        verbose_name_plural = _("task registry entries")
        ordering = ["-last_seen_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "task_identifier"],
                name="unique_task_registry_per_project",
            )
        ]

    def __str__(self):
        return f"{self.task_identifier} (Project {self.project_id})"


class Job(AuditModel):
    """
    A logical background task being monitored.
    Uniquely identified by project + task_identifier.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")

    class VerificationStatus(models.TextChoices):
        VERIFIED = "verified", _("Verified")
        UNVERIFIED = "unverified", _("Unverified")

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="jobs",
        verbose_name=_("project"),
    )
    name = models.CharField(_("job name"), max_length=255)
    task_identifier = models.CharField(_("task identifier"), max_length=255)
    description = models.TextField(_("description"), blank=True)

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    verification_status = models.CharField(
        _("verification status"),
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
    )
    last_verified_at = models.DateTimeField(_("last verified at"), null=True, blank=True)

    class Meta:
        verbose_name = _("job")
        verbose_name_plural = _("jobs")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "task_identifier"],
                condition=models.Q(is_deleted=False),
                name="unique_active_job_task_identifier_per_project",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.task_identifier})"
