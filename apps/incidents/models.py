from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Incident(models.Model):
    """An active or historical reliability issue triggered by an AlertRule."""

    class Status(models.TextChoices):
        OPEN = "OPEN", _("Open")
        ACKNOWLEDGED = "ACKNOWLEDGED", _("Acknowledged")
        RESOLVED = "RESOLVED", _("Resolved")

    class Severity(models.TextChoices):
        DEGRADED = "DEGRADED", _("Degraded")
        CRITICAL = "CRITICAL", _("Critical")

    class ResolutionType(models.TextChoices):
        MANUAL = "MANUAL", _("Manual")
        AUTOMATIC = "AUTOMATIC", _("Automatic")

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="incidents",
        verbose_name=_("project"),
    )
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.CASCADE,
        related_name="incidents",
        null=True,
        blank=True,
        verbose_name=_("job"),
    )
    alert_rule = models.ForeignKey(
        "alerts.AlertRule",
        on_delete=models.SET_NULL,
        related_name="incidents",
        null=True,
        blank=True,
        verbose_name=_("alert rule"),
    )

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    severity = models.CharField(
        _("severity"),
        max_length=20,
        choices=Severity.choices,
        default=Severity.DEGRADED,
    )

    # Assignment
    assigned_to = models.ForeignKey(
        "teams.TeamMember",
        on_delete=models.SET_NULL,
        related_name="assigned_incidents",
        null=True,
        blank=True,
        verbose_name=_("assigned to"),
    )
    assigned_at = models.DateTimeField(_("assigned at"), null=True, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="incidents_assigned_by",
        null=True,
        blank=True,
    )

    # Acknowledgement
    acknowledged_at = models.DateTimeField(_("acknowledged at"), null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="incidents_acknowledged",
        null=True,
        blank=True,
    )

    # Resolution
    resolved_at = models.DateTimeField(_("resolved at"), null=True, blank=True)
    resolution_type = models.CharField(
        _("resolution type"),
        max_length=20,
        choices=ResolutionType.choices,
        null=True,
        blank=True,
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="incidents_resolved",
        null=True,
        blank=True,
    )

    trigger_metadata = models.JSONField(
        _("trigger metadata"),
        default=dict,
        blank=True,
        help_text=_("Metadata about the metric values that triggered this incident."),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("incident")
        verbose_name_plural = _("incidents")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["alert_rule", "project", "job"],
                condition=models.Q(status__in=["OPEN", "ACKNOWLEDGED"])
                & models.Q(job__isnull=False),
                name="unique_active_incident_per_job",
            ),
            models.UniqueConstraint(
                fields=["alert_rule", "project"],
                condition=models.Q(status__in=["OPEN", "ACKNOWLEDGED"])
                & models.Q(job__isnull=True),
                name="unique_active_incident_per_project",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["severity", "status"]),
        ]

    def __str__(self):
        return f"Incident #{self.id} for {self.project.name} ({self.get_status_display()})"


class IncidentEvent(models.Model):
    """Immutable system timeline for auditing."""

    class EventType(models.TextChoices):
        CREATED = "CREATED", _("Created")
        ASSIGNED = "ASSIGNED", _("Assigned")
        ACKNOWLEDGED = "ACKNOWLEDGED", _("Acknowledged")
        NOTE_ADDED = "NOTE_ADDED", _("Note Added")
        REOPENED = "REOPENED", _("Reopened")
        AUTO_RESOLVED = "AUTO_RESOLVED", _("Automatically Resolved")
        MANUALLY_RESOLVED = "MANUALLY_RESOLVED", _("Manually Resolved")

    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(
        _("event type"),
        max_length=30,
        choices=EventType.choices,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    event_time = models.DateTimeField(_("event time"), auto_now_add=True)
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    class Meta:
        verbose_name = _("incident event")
        verbose_name_plural = _("incident events")
        ordering = ["event_time", "id"]

    def __str__(self):
        return f"{self.get_event_type_display()} on Incident #{self.incident_id}"


class IncidentNote(models.Model):
    """Immutable human investigation notes."""

    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="incident_notes",
    )
    content = models.TextField(_("content"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("incident note")
        verbose_name_plural = _("incident notes")
        ordering = ["created_at"]

    def __str__(self):
        return f"Note by {self.author} on Incident #{self.incident_id}"
