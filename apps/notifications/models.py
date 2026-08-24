from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.incidents.models import Incident, IncidentEvent


class NotificationChannel(models.Model):
    """
    Represents a delivery channel (e.g., Email, Webhook, In-App)
    configured for a specific project.
    """

    class ChannelType(models.TextChoices):
        IN_APP = "IN_APP", _("In-App")
        EMAIL = "EMAIL", _("Email")
        WEBHOOK = "WEBHOOK", _("Webhook")

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="notification_channels",
    )
    type = models.CharField(max_length=20, choices=ChannelType.choices)
    name = models.CharField(max_length=100)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("notification channel")
        verbose_name_plural = _("notification channels")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"

    def clean(self):
        super().clean()
        if self.type == self.ChannelType.WEBHOOK:
            if "url" not in self.config:
                raise ValidationError({"config": _("Webhook config must contain 'url'.")})
            if "secret" not in self.config:
                raise ValidationError({"config": _("Webhook config must contain 'secret'.")})
            if len(self.config.get("secret", "")) < 16:
                raise ValidationError(
                    {"config": _("Webhook secret must be at least 16 characters long.")}
                )
            url = self.config.get("url", "")
            allow_insecure = self.config.get("allow_insecure_http", False)
            if url.startswith("http://") and not allow_insecure:
                raise ValidationError(
                    {
                        "config": _(
                            "HTTPS is required for webhooks unless allow_insecure_http is true."
                        )
                    }
                )
            if not url.startswith("http://") and not url.startswith("https://"):
                raise ValidationError({"config": _("Webhook URL must start with http or https.")})
        elif self.type == self.ChannelType.EMAIL:
            if "recipients" not in self.config or not isinstance(self.config["recipients"], list):
                raise ValidationError({"config": _("Email config must contain 'recipients' list.")})


class NotificationPolicy(models.Model):
    """
    Defines when a NotificationChannel should be triggered,
    based on the incident severity and event types.
    """

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="notification_policies",
    )
    channel = models.ForeignKey(
        NotificationChannel,
        on_delete=models.CASCADE,
        related_name="policies",
    )
    severity = models.CharField(
        max_length=20,
        choices=Incident.Severity.choices,
    )
    event_types = models.JSONField(
        default=list,
        help_text=_("List of incident event types that trigger this policy."),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("notification policy")
        verbose_name_plural = _("notification policies")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Policy for {self.channel.name} ({self.get_severity_display()})"

    def clean(self):
        super().clean()
        if self.channel_id and self.project_id and self.channel.project_id != self.project_id:
            raise ValidationError(
                {"channel": _("Channel must belong to the same project as the policy.")}
            )

        if self.project_id and (self.project.is_deleted or self.project.status != "active"):
            raise ValidationError(
                {
                    "project": _(
                        "Cannot create or update a policy for an inactive or deleted project."
                    )
                }
            )

        valid_events = {
            IncidentEvent.EventType.CREATED,
            IncidentEvent.EventType.ASSIGNED,
            IncidentEvent.EventType.ACKNOWLEDGED,
            IncidentEvent.EventType.NOTE_ADDED,
            IncidentEvent.EventType.AUTO_RESOLVED,
            IncidentEvent.EventType.MANUALLY_RESOLVED,
            IncidentEvent.EventType.REOPENED,
        }

        if not isinstance(self.event_types, list):
            raise ValidationError({"event_types": _("Must be a list of event types.")})

        for evt in self.event_types:
            if evt not in valid_events:
                raise ValidationError({"event_types": _(f"Invalid event type: {evt}")})


class NotificationDelivery(models.Model):
    """
    Tracks the delivery attempts of a notification to an external channel
    for a specific incident event. Ensures idempotency.
    """

    class DeliveryStatus(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        SENT = "SENT", _("Sent")
        FAILED = "FAILED", _("Failed")

    incident_event = models.ForeignKey(
        IncidentEvent,
        on_delete=models.CASCADE,
        related_name="notification_deliveries",
    )
    channel = models.ForeignKey(
        NotificationChannel,
        on_delete=models.PROTECT,
        related_name="deliveries",
    )
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("notification delivery")
        verbose_name_plural = _("notification deliveries")
        constraints = [
            models.UniqueConstraint(
                fields=["incident_event", "channel"],
                name="unique_incident_event_channel",
            )
        ]
        indexes = [
            models.Index(fields=["status", "last_attempt_at"]),
        ]

    def __str__(self):
        return (
            f"Delivery to {self.channel.name} for Event #{self.incident_event_id} ({self.status})"
        )


class InAppNotification(models.Model):
    """
    Represents a notification delivered directly to a user's dashboard.
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="in_app_notifications",
    )
    incident_event = models.ForeignKey(
        IncidentEvent,
        on_delete=models.CASCADE,
        related_name="in_app_notifications",
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("in-app notification")
        verbose_name_plural = _("in-app notifications")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "incident_event"],
                name="unique_in_app_notification",
            )
        ]

    def __str__(self):
        return f"Notification for {self.recipient.email}: {self.title}"
