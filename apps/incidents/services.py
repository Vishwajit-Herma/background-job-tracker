from django.db import transaction
from django.utils import timezone

from apps.teams.models import TeamMember
from .models import Incident, IncidentEvent, IncidentNote


def _log_incident_event(incident, event_type, actor=None, metadata=None):
    """
    Creates an immutable event for the incident timeline.
    MUST only be called inside the transition transaction to guarantee integrity.
    """
    IncidentEvent.objects.create(
        incident=incident,
        event_type=event_type,
        actor=actor,
        metadata=metadata or {},
    )


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

        _log_incident_event(
            incident,
            IncidentEvent.EventType.ACKNOWLEDGED,
            actor=actor,
            metadata={"acknowledged_by": actor.id if actor else None},
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

        _log_incident_event(
            incident,
            IncidentEvent.EventType.MANUALLY_RESOLVED,
            actor=actor,
            metadata={
                "resolution_type": "MANUAL",
                "resolved_by": actor.id if actor else None,
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

        _log_incident_event(incident, IncidentEvent.EventType.REOPENED, actor=actor, metadata={})
        return incident


def auto_resolve_incident(incident_id):
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
        incident.save(
            update_fields=["status", "resolved_by", "resolved_at", "resolution_type", "updated_at"]
        )

        _log_incident_event(
            incident,
            IncidentEvent.EventType.AUTO_RESOLVED,
            actor=None,
            metadata={"resolution_type": "AUTOMATIC", "previous_status": previous_status},
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
