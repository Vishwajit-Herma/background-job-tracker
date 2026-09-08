import json
from django.db import IntegrityError
from django.utils import timezone

from apps.core.realtime import publish_realtime_event
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

    # Fetch active policies for the project with active channels
    policies = NotificationPolicy.objects.filter(
        project_id=incident.project_id,
        is_active=True,
        channel__is_active=True,
    ).select_related("channel")

    unique_channels = {}
    for policy in policies:
        # Severity matching:
        # A CRITICAL incident triggers both CRITICAL and DEGRADED policies.
        # A DEGRADED incident triggers DEGRADED policies.
        if (
            incident.severity == Incident.Severity.DEGRADED
            and policy.severity == Incident.Severity.CRITICAL
        ):
            continue

        # Event type matching:
        event_types = policy.event_types or []
        if isinstance(event_types, str):
            try:
                event_types = json.loads(event_types)
            except Exception:
                event_types = [event_types]

        if incident_event.event_type in event_types:
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
        cond_type = incident.trigger_metadata.get("condition_type") or incident_event.metadata.get(
            "condition_type"
        )
        if cond_type == "MISSED_EXECUTION":
            overdue = incident.trigger_metadata.get("overdue_by_seconds", 0)
            title = (
                f"[{incident.get_severity_display()}] Incident #{incident.id} - Missed Execution"
            )
            message = f"Job '{incident.job.name}' on '{incident.project.name}' missed its expected schedule (overdue by {overdue}s)."
        elif cond_type == "STALLED_EXECUTION":
            runtime = incident.trigger_metadata.get("runtime_seconds", 0)
            title = (
                f"[{incident.get_severity_display()}] Incident #{incident.id} - Stalled Execution"
            )
            message = f"An execution for '{incident.job.name}' on '{incident.project.name}' is stalled (running for {runtime}s)."
        elif cond_type == "OVERDUE_EXECUTION":
            queued = incident.trigger_metadata.get("queued_seconds", 0)
            title = f"[{incident.get_severity_display()}] Incident #{incident.id} - Overdue Queued Execution"
            message = f"An execution for '{incident.job.name}' on '{incident.project.name}' is stuck pending in queue ({queued}s)."
        else:
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
        message = (
            f"Incident #{incident.id} on '{incident.project.name}' was resolved by {actor_name}."
        )
    elif event_type == IncidentEvent.EventType.AUTO_RESOLVED:
        title = f"[RESOLVED] Incident #{incident.id} Auto-Resolved"
        message = f"Incident #{incident.id} on '{incident.project.name}' was automatically resolved as metrics returned to normal."
    elif event_type == IncidentEvent.EventType.REOPENED:
        title = f"[{incident.get_severity_display()}] Incident #{incident.id} Reopened"
        message = (
            f"Incident #{incident.id} on '{incident.project.name}' was reopened by {actor_name}."
        )
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
        created_notifs = InAppNotification.objects.bulk_create(notifications, ignore_conflicts=True)
        now_iso = timezone.now().isoformat()
        for notif in created_notifs:
            publish_realtime_event(
                "notification.created",
                user_id=notif.recipient_id,
                payload={
                    "id": notif.id,
                    "title": notif.title,
                    "message": notif.message,
                    "incident_id": incident.id,
                    "event_type": incident_event.event_type,
                    "incident_severity": incident.severity,
                    "project_name": incident.project.name if incident.project else None,
                    "job_name": incident.job.name if incident.job else None,
                    "is_read": False,
                    "created_at": notif.created_at.isoformat()
                    if getattr(notif, "created_at", None)
                    else now_iso,
                },
            )


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
