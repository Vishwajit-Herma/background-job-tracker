from django.db import transaction
from django.utils import timezone

from apps.teams.models import TeamMember
from apps.notifications.services import dispatch_incident_event
from .models import Incident, IncidentEvent, IncidentNote


NOTIFIABLE_EVENTS = {
    IncidentEvent.EventType.CREATED,
    IncidentEvent.EventType.ASSIGNED,
    IncidentEvent.EventType.ACKNOWLEDGED,
    IncidentEvent.EventType.NOTE_ADDED,
    IncidentEvent.EventType.AUTO_RESOLVED,
    IncidentEvent.EventType.MANUALLY_RESOLVED,
    IncidentEvent.EventType.REOPENED,
}


def _log_incident_event(incident, event_type, actor=None, metadata=None):
    """
    Creates an immutable event for the incident timeline.
    MUST only be called inside the transition transaction to guarantee integrity.
    """
    event = IncidentEvent.objects.create(
        incident=incident,
        event_type=event_type,
        actor=actor,
        metadata=metadata or {},
    )

    if event_type in NOTIFIABLE_EVENTS:
        transaction.on_commit(lambda: dispatch_incident_event(event.id))


def assign_incident(incident_id, member_id, actor):
    """
    Assigns an incident to a member.
    """
    with transaction.atomic():
        incident = Incident.objects.select_for_update().get(id=incident_id)

        if incident.status == Incident.Status.RESOLVED:
            raise ValueError("Cannot assign a resolved incident.")

        member = TeamMember.objects.filter(
            id=member_id,
            team_id=incident.project.team_id,
            is_active=True,
        ).first()

        if not member:
            raise ValueError("Assignee must be an active member of the project's team.")

        if incident.assigned_to_id == member.id:
            return incident

        previous_assignee_id = incident.assigned_to_id

        incident.assigned_to = member
        incident.assigned_at = timezone.now()
        incident.assigned_by = actor
        incident.save(update_fields=["assigned_to", "assigned_at", "assigned_by", "updated_at"])

        _log_incident_event(
            incident,
            IncidentEvent.EventType.ASSIGNED,
            actor=actor,
            metadata={
                "previous_assignee_member_id": previous_assignee_id,
                "new_assignee_member_id": member.id,
                "new_assignee_name": member.user.get_full_name() or member.user.email,
            },
        )
        return incident


def acknowledge_incident(incident_id, actor):
    """
    Acknowledges an incident.
    """
    with transaction.atomic():
        incident = Incident.objects.select_for_update().get(id=incident_id)

        if incident.status != Incident.Status.OPEN:
            raise ValueError("Only OPEN incidents can be acknowledged.")

        incident.status = Incident.Status.ACKNOWLEDGED
        incident.acknowledged_by = actor
        incident.acknowledged_at = timezone.now()
        incident.save(update_fields=["status", "acknowledged_by", "acknowledged_at", "updated_at"])

        actor_name = (actor.get_full_name() or actor.email) if actor else "System"
        _log_incident_event(
            incident,
            IncidentEvent.EventType.ACKNOWLEDGED,
            actor=actor,
            metadata={
                "acknowledged_by": actor.id if actor else None,
                "acknowledged_by_name": actor_name,
            },
        )
        return incident


def resolve_incident(incident_id, actor):
    """
    Manually resolves an incident.
    """
    with transaction.atomic():
        incident = Incident.objects.select_for_update().get(id=incident_id)

        if incident.status == Incident.Status.RESOLVED:
            raise ValueError("Incident is already resolved.")

        previous_status = incident.status

        incident.status = Incident.Status.RESOLVED
        incident.resolved_by = actor
        incident.resolved_at = timezone.now()
        incident.resolution_type = Incident.ResolutionType.MANUAL
        incident.save(
            update_fields=["status", "resolved_by", "resolved_at", "resolution_type", "updated_at"]
        )

        actor_name = (actor.get_full_name() or actor.email) if actor else "System"
        _log_incident_event(
            incident,
            IncidentEvent.EventType.MANUALLY_RESOLVED,
            actor=actor,
            metadata={
                "resolution_type": "MANUAL",
                "resolved_by": actor.id if actor else None,
                "resolved_by_name": actor_name,
                "previous_status": previous_status,
            },
        )
        return incident


def reopen_incident(incident_id, actor):
    """
    Reopens a resolved incident.
    """
    with transaction.atomic():
        incident = Incident.objects.select_for_update().get(id=incident_id)

        if incident.status != Incident.Status.RESOLVED:
            raise ValueError("Only RESOLVED incidents can be reopened.")

        incident.status = Incident.Status.OPEN
        incident.resolved_by = None
        incident.resolved_at = None
        incident.resolution_type = None
        incident.acknowledged_by = None
        incident.acknowledged_at = None
        incident.save(
            update_fields=[
                "status",
                "resolved_by",
                "resolved_at",
                "resolution_type",
                "acknowledged_by",
                "acknowledged_at",
                "updated_at",
            ]
        )

        actor_name = (actor.get_full_name() or actor.email) if actor else "System"
        _log_incident_event(
            incident,
            IncidentEvent.EventType.REOPENED,
            actor=actor,
            metadata={
                "reopened_by": actor.id if actor else None,
                "reopened_by_name": actor_name,
            },
        )
        return incident


def auto_resolve_incident(incident_id, recovery_metadata=None):
    """
    Automatically resolves an incident based on metric recovery.
    """
    with transaction.atomic():
        incident = Incident.objects.select_for_update().get(id=incident_id)

        if incident.status == Incident.Status.RESOLVED:
            return incident

        previous_status = incident.status

        incident.status = Incident.Status.RESOLVED
        incident.resolved_by = None
        incident.resolved_at = timezone.now()
        incident.resolution_type = Incident.ResolutionType.AUTOMATIC

        update_fields = ["status", "resolved_by", "resolved_at", "resolution_type", "updated_at"]
        if recovery_metadata:
            incident.trigger_metadata = recovery_metadata
            update_fields.append("trigger_metadata")

        incident.save(update_fields=update_fields)

        _log_incident_event(
            incident,
            IncidentEvent.EventType.AUTO_RESOLVED,
            actor=None,
            metadata={
                "resolution_type": "AUTOMATIC",
                "resolved_by_name": "System (Auto-recovery)",
                "previous_status": previous_status,
                "recovery_metadata": recovery_metadata,
            },
        )
        return incident


def add_incident_note(incident_id, author, content):
    """
    Adds a note to an incident.
    """
    with transaction.atomic():
        incident = Incident.objects.select_for_update().get(id=incident_id)
        note = IncidentNote.objects.create(incident=incident, author=author, content=content)

        _log_incident_event(
            incident,
            IncidentEvent.EventType.NOTE_ADDED,
            actor=author,
            metadata={"note_id": note.id},
        )
        return note
