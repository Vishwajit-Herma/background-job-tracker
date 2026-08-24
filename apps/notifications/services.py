from django.db import IntegrityError

from apps.incidents.models import IncidentEvent
from apps.teams.models import TeamMember
from apps.notifications.models import (
    NotificationPolicy,
    NotificationChannel,
    InAppNotification,
    NotificationDelivery,
)
from apps.notifications.tasks import deliver_webhook_task, deliver_email_task


def dispatch_incident_event(incident_event_id):
    """
    Dispatches notifications for an incident event based on active policies.
    """
    try:
        incident_event = IncidentEvent.objects.select_related("incident", "incident__project").get(
            id=incident_event_id
        )
    except IncidentEvent.DoesNotExist:
        return

    incident = incident_event.incident

    # Find matching active policies
    # The event_type must be present in the event_types JSON array.
    # Since JSONField contains a list of strings, we use the `contains` lookup
    policies = NotificationPolicy.objects.filter(
        project_id=incident.project_id,
        is_active=True,
        severity=incident.severity,
        event_types__contains=[incident_event.event_type],
    ).select_related("channel")

    # Deduplicate unique channels
    unique_channels = {}
    for policy in policies:
        if policy.channel.is_active:
            unique_channels[policy.channel.id] = policy.channel

    for channel in unique_channels.values():
        if channel.type == NotificationChannel.ChannelType.IN_APP:
            _dispatch_in_app(incident_event, channel)
        elif channel.type == NotificationChannel.ChannelType.WEBHOOK:
            _dispatch_external(incident_event, channel, deliver_webhook_task)
        elif channel.type == NotificationChannel.ChannelType.EMAIL:
            _dispatch_external(incident_event, channel, deliver_email_task)


def _dispatch_in_app(incident_event, channel):
    """
    Creates InAppNotification records synchronously for all active members
    of the team associated with the incident's project.
    """
    incident = incident_event.incident
    team_members = TeamMember.objects.filter(
        team_id=incident.project.team_id, is_active=True
    ).select_related("user")

    title = f"[{incident.get_severity_display()}] Incident #{incident.id} - {incident_event.get_event_type_display()}"
    message = f"An incident event occurred for project {incident.project.name}."

    notifications = []
    for member in team_members:
        notifications.append(
            InAppNotification(
                recipient=member.user,
                incident_event=incident_event,
                title=title,
                message=message,
            )
        )

    if notifications:
        InAppNotification.objects.bulk_create(notifications, ignore_conflicts=True)


def _dispatch_external(incident_event, channel, celery_task):
    """
    Creates a NotificationDelivery record and queues the specified
    Celery task for asynchronous external delivery. Handles IntegrityError
    gracefully to ensure idempotency.
    """
    try:
        delivery, created = NotificationDelivery.objects.get_or_create(
            incident_event=incident_event,
            channel=channel,
        )
        if created:
            celery_task.delay(delivery.id)
    except IntegrityError:
        pass
