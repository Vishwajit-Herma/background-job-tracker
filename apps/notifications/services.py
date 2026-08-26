from django.db import IntegrityError

from apps.incidents.models import Incident, IncidentEvent
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

    if incident.severity == Incident.Severity.CRITICAL:
        # A CRITICAL incident triggers both CRITICAL and DEGRADED policies
        matched_severities = [Incident.Severity.CRITICAL, Incident.Severity.DEGRADED]
    else:
        # A DEGRADED incident triggers only DEGRADED policies
        matched_severities = [Incident.Severity.DEGRADED]

    # Find matching active policies
    policies = NotificationPolicy.objects.filter(
        project_id=incident.project_id,
        is_active=True,
        severity__in=matched_severities,
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


def _format_incident_notification(incident_event):
    incident = incident_event.incident
    actor_name = (
        incident_event.actor.get_full_name() or incident_event.actor.email
        if incident_event.actor
        else "System"
    )
    job_str = f" on job '{incident.job.name}'" if incident.job else ""
    event_type = incident_event.event_type

    if event_type == IncidentEvent.EventType.CREATED:
        title = f"[{incident.get_severity_display()}] New Incident #{incident.id} - {incident.project.name}"
        message = f"New {incident.get_severity_display().lower()} incident #{incident.id} triggered on '{incident.project.name}'{job_str}."
    elif event_type == IncidentEvent.EventType.ASSIGNED:
        assignee_name = incident_event.metadata.get("new_assignee_name", "a team member")
        title = f"[{incident.get_severity_display()}] Incident #{incident.id} Assigned to {assignee_name}"
        message = f"Incident #{incident.id} on '{incident.project.name}' was assigned to {assignee_name} by {actor_name}."
    elif event_type == IncidentEvent.EventType.ACKNOWLEDGED:
        title = f"[{incident.get_severity_display()}] Incident #{incident.id} Acknowledged"
        message = f"Incident #{incident.id} on '{incident.project.name}' was acknowledged by {actor_name}."
    elif event_type == IncidentEvent.EventType.MANUALLY_RESOLVED:
        title = f"[RESOLVED] Incident #{incident.id} Manually Resolved"
        message = f"Incident #{incident.id} on '{incident.project.name}' was resolved by {actor_name}."
    elif event_type == IncidentEvent.EventType.AUTO_RESOLVED:
        title = f"[RESOLVED] Incident #{incident.id} Auto-Resolved"
        message = f"Incident #{incident.id} on '{incident.project.name}' was automatically resolved as metrics returned to normal."
    elif event_type == IncidentEvent.EventType.REOPENED:
        title = f"[{incident.get_severity_display()}] Incident #{incident.id} Reopened"
        message = f"Incident #{incident.id} on '{incident.project.name}' was reopened by {actor_name}."
    elif event_type == IncidentEvent.EventType.NOTE_ADDED:
        title = f"[{incident.get_severity_display()}] Note Added on Incident #{incident.id}"
        message = f"{actor_name} added an investigation note to Incident #{incident.id} on '{incident.project.name}'."
    else:
        title = f"[{incident.get_severity_display()}] Incident #{incident.id} - {incident_event.get_event_type_display()}"
        message = f"Incident #{incident.id} updated with {incident_event.get_event_type_display()} on '{incident.project.name}'."

    return title, message


def _dispatch_in_app(incident_event, channel):
    """
    Creates InAppNotification records synchronously for all active members
    of the team associated with the incident's project.
    """
    incident = incident_event.incident
    team_members = TeamMember.objects.filter(
        team_id=incident.project.team_id, is_active=True
    ).select_related("user")

    title, message = _format_incident_notification(incident_event)

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
