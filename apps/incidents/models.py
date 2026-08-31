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
        RUNBOOK_STARTED = "RUNBOOK_STARTED", _("Runbook Started")
        RUNBOOK_COMPLETED = "RUNBOOK_COMPLETED", _("Runbook Completed")
        RUNBOOK_CANCELLED = "RUNBOOK_CANCELLED", _("Runbook Cancelled")
        POSTMORTEM_SUBMITTED = "POSTMORTEM_SUBMITTED", _("Postmortem Submitted")
        POSTMORTEM_COMPLETED = "POSTMORTEM_COMPLETED", _("Postmortem Completed")

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


class IncidentIntelligence(models.Model):
    """
    Derived intelligence for an incident: impact analysis, correlated signals,
    and ranked probable root cause candidates.
    Does NOT duplicate telemetry or incident entities; stores computed derivations.
    """

    incident = models.OneToOneField(
        Incident,
        on_delete=models.CASCADE,
        related_name="intelligence",
        verbose_name=_("incident"),
    )
    impact = models.JSONField(
        _("impact analysis"),
        default=dict,
        blank=True,
    )
    correlations = models.JSONField(
        _("correlated signals"),
        default=list,
        blank=True,
    )
    probable_causes = models.JSONField(
        _("probable root causes"),
        default=list,
        blank=True,
    )
    analysis_window_start = models.DateTimeField(
        _("analysis window start"),
        null=True,
        blank=True,
    )
    analysis_window_end = models.DateTimeField(
        _("analysis window end"),
        null=True,
        blank=True,
    )
    analysis_version = models.CharField(
        _("analysis version"),
        max_length=20,
        default="1.0",
    )
    calculated_at = models.DateTimeField(
        _("calculated at"),
        auto_now=True,
    )

    class Meta:
        verbose_name = _("incident intelligence")
        verbose_name_plural = _("incident intelligences")
        ordering = ["-calculated_at"]

    def __str__(self):
        return f"Intelligence for Incident #{self.incident_id}"


class Runbook(models.Model):
    """A standard operating procedure for handling specific incidents."""

    class TriggerType(models.TextChoices):
        MISSED_EXECUTION = "MISSED_EXECUTION", _("Missed Execution")
        STALLED_EXECUTION = "STALLED_EXECUTION", _("Stalled Execution")
        OVERDUE_EXECUTION = "OVERDUE_EXECUTION", _("Overdue Execution")
        FAILURE_RATE_ANOMALY = "FAILURE_RATE_ANOMALY", _("Failure Rate Anomaly")
        RETRY_RATE_ANOMALY = "RETRY_RATE_ANOMALY", _("Retry Rate Anomaly")
        DURATION_ANOMALY = "DURATION_ANOMALY", _("Duration Anomaly")
        EXECUTION_VOLUME_ANOMALY = "EXECUTION_VOLUME_ANOMALY", _("Execution Volume Anomaly")

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="runbooks",
    )
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.CASCADE,
        related_name="runbooks",
        null=True,
        blank=True,
        help_text=_(
            "If set, this runbook applies specifically to this job. Must belong to the same project."
        ),
    )
    name = models.CharField(_("name"), max_length=255)
    description = models.TextField(_("description"), blank=True)
    trigger_type = models.CharField(
        _("trigger type"),
        max_length=50,
        choices=TriggerType.choices,
        null=True,
        blank=True,
    )
    steps = models.JSONField(
        _("steps"),
        default=list,
        help_text=_("List of step definitions for the runbook."),
    )
    is_active = models.BooleanField(_("is active"), default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("runbook")
        verbose_name_plural = _("runbooks")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "is_active", "trigger_type"]),
        ]

    def __str__(self):
        return f"Runbook: {self.name} for {self.project.name}"


class IncidentRunbookExecution(models.Model):
    """An execution of a Runbook for a specific Incident."""

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        IN_PROGRESS = "IN_PROGRESS", _("In Progress")
        COMPLETED = "COMPLETED", _("Completed")
        CANCELLED = "CANCELLED", _("Cancelled")

    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name="runbook_executions",
    )
    runbook = models.ForeignKey(
        Runbook,
        on_delete=models.RESTRICT,
        related_name="executions",
    )

    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    step_states = models.JSONField(
        _("step states"),
        default=dict,
        help_text=_("Current status of each step, keyed by step ID."),
    )
    step_history = models.JSONField(
        _("step history"),
        default=list,
        help_text=_("Append-only log of step state transitions."),
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    class Meta:
        verbose_name = _("incident runbook execution")
        verbose_name_plural = _("incident runbook executions")
        ordering = ["-started_at", "-id"]

    def __str__(self):
        return f"Execution of {self.runbook.name} for Incident #{self.incident_id}"


class IncidentPostmortem(models.Model):
    """A post-incident analysis document."""

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        IN_REVIEW = "IN_REVIEW", _("In Review")
        COMPLETED = "COMPLETED", _("Completed")

    incident = models.OneToOneField(
        Incident,
        on_delete=models.CASCADE,
        related_name="postmortem",
        verbose_name=_("incident"),
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    summary = models.TextField(_("summary"), blank=True)
    impact_summary = models.TextField(_("impact summary"), blank=True)
    probable_cause = models.TextField(_("probable cause"), blank=True)
    confirmed_root_cause = models.TextField(_("confirmed root cause"), blank=True)
    resolution = models.TextField(_("resolution"), blank=True)
    contributing_factors = models.JSONField(
        _("contributing factors"),
        default=list,
        blank=True,
        help_text=_("List of contributing factors identified."),
    )
    timeline = models.JSONField(
        _("timeline"),
        default=list,
        blank=True,
        help_text=_("Human-curated timeline of events during the incident."),
    )
    what_went_well = models.TextField(_("what went well"), blank=True)
    what_went_wrong = models.TextField(_("what went wrong"), blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(_("reviewed at"), null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("incident postmortem")
        verbose_name_plural = _("incident postmortems")

    def __str__(self):
        return f"Postmortem for Incident #{self.incident_id} ({self.get_status_display()})"


class PostmortemActionItem(models.Model):
    """An action item derived from a postmortem."""

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        IN_PROGRESS = "IN_PROGRESS", _("In Progress")
        COMPLETED = "COMPLETED", _("Completed")
        CANCELLED = "CANCELLED", _("Cancelled")

    postmortem = models.ForeignKey(
        IncidentPostmortem,
        on_delete=models.CASCADE,
        related_name="action_items",
    )
    title = models.CharField(_("title"), max_length=255, default="")
    description = models.TextField(_("description"), blank=True)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    owner = models.ForeignKey(
        "teams.TeamMember",
        on_delete=models.SET_NULL,
        related_name="postmortem_action_items",
        null=True,
        blank=True,
    )
    due_date = models.DateField(_("due date"), null=True, blank=True)
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("postmortem action item")
        verbose_name_plural = _("postmortem action items")
        ordering = ["created_at"]

    def __str__(self):
        return f"Action Item '{self.title}' for Incident #{self.postmortem.incident_id}"
