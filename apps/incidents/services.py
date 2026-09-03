from django.core.cache import cache
from django.db import transaction
from django.db.models import (
    Avg,
    Case,
    CharField,
    Count,
    DurationField,
    ExpressionWrapper,
    F,
    IntegerField,
    Max,
    Min,
    Prefetch,
    Q,
    Value,
    When,
)
from django.utils import timezone

from apps.notifications.services import dispatch_incident_event
from apps.teams.models import TeamMember
from .models import (
    Incident,
    IncidentEvent,
    IncidentNote,
    IncidentPostmortem,
    IncidentRunbookExecution,
    PostmortemActionItem,
    Runbook,
)
from .serializers import (
    IncidentEventSerializer,
    IncidentIntelligenceSerializer,
    IncidentPostmortemSerializer,
    IncidentRunbookExecutionSerializer,
    IncidentSerializer,
)
from .tasks import calculate_incident_intelligence_task


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


def create_incident(project, severity, alert_rule=None, job=None, trigger_metadata=None):
    """
    Creates an incident, logs the CREATED IncidentEvent, and queues intelligence calculation.
    """
    with transaction.atomic():
        incident = Incident.objects.create(
            project=project,
            job=job,
            alert_rule=alert_rule,
            severity=severity,
            trigger_metadata=trigger_metadata or {},
        )
        _log_incident_event(
            incident,
            IncidentEvent.EventType.CREATED,
            actor=None,
            metadata={"trigger_metadata": trigger_metadata or {}},
        )
        transaction.on_commit(lambda: calculate_incident_intelligence_task.delay(incident.id))
        return incident


def assign_incident(incident_id, member_id, actor):
    """
    Assigns or unassigns an incident to/from a team member.
    """
    with transaction.atomic():
        incident = Incident.objects.select_for_update().get(id=incident_id)

        if incident.status == Incident.Status.RESOLVED:
            raise ValueError("Cannot assign a resolved incident.")

        if member_id is None:
            if incident.assigned_to_id is None:
                return incident

            previous_assignee_id = incident.assigned_to_id
            incident.assigned_to = None
            incident.assigned_at = None
            incident.assigned_by = actor
            incident.save(update_fields=["assigned_to", "assigned_at", "assigned_by", "updated_at"])

            _log_incident_event(
                incident,
                IncidentEvent.EventType.ASSIGNED,
                actor=actor,
                metadata={
                    "previous_assignee_member_id": previous_assignee_id,
                    "new_assignee_member_id": None,
                    "new_assignee_name": "Unassigned",
                },
            )
            return incident

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
        transaction.on_commit(lambda: calculate_incident_intelligence_task.delay(incident.id))
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
        transaction.on_commit(lambda: calculate_incident_intelligence_task.delay(incident.id))
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
        transaction.on_commit(lambda: calculate_incident_intelligence_task.delay(incident.id))
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


def find_recommended_runbooks(incident_id):
    """
    Find and rank recommended runbooks for an incident.
    Match in descending order of priority:
    1. Exact job AND exact trigger type
    2. Exact job, general trigger (trigger_type=None)
    3. General job (job=None), exact trigger type
    4. General job, general trigger
    """

    incident = Incident.objects.select_related("alert_rule").get(id=incident_id)
    project_id = incident.project_id
    job_id = incident.job_id
    trigger_type = None
    if incident.alert_rule:
        trigger_type = incident.alert_rule.metric
    elif incident.trigger_metadata and isinstance(incident.trigger_metadata, dict):
        trigger_type = incident.trigger_metadata.get("metric_type") or incident.trigger_metadata.get("condition_type")

    # Base queryset for active runbooks in the project
    qs = Runbook.objects.filter(project_id=project_id, is_active=True)

    # Filter by job matching
    job_condition = Q(job_id=job_id) | Q(job__isnull=True)

    # Filter by trigger_type matching
    trigger_condition = Q(trigger_type__isnull=True)
    if trigger_type:
        trigger_condition |= Q(trigger_type=trigger_type)

    qs = qs.filter(job_condition & trigger_condition)

    # Annotate priority and match reason
    reason_cases = [
        When(job_id=job_id, trigger_type=trigger_type, then=Value("EXACT_JOB_AND_TRIGGER")),
        When(job_id=job_id, trigger_type__isnull=True, then=Value("EXACT_JOB_GENERAL_TRIGGER")),
    ]
    if trigger_type:
        reason_cases.append(
            When(job__isnull=True, trigger_type=trigger_type, then=Value("PROJECT_EXACT_TRIGGER"))
        )
    reason_cases.append(
        When(job__isnull=True, trigger_type__isnull=True, then=Value("PROJECT_GENERAL_TRIGGER"))
    )

    priority_cases = [
        When(job_id=job_id, trigger_type=trigger_type, then=Value(1)),
        When(job_id=job_id, trigger_type__isnull=True, then=Value(2)),
    ]

    if trigger_type:
        priority_cases.append(When(job__isnull=True, trigger_type=trigger_type, then=Value(3)))

    priority_cases.append(When(job__isnull=True, trigger_type__isnull=True, then=Value(4)))

    qs = (
        qs.annotate(
            match_priority=Case(
                *priority_cases,
                default=Value(5),
                output_field=IntegerField(),
            ),
            match_reason=Case(
                *reason_cases,
                default=Value("UNKNOWN"),
                output_field=CharField(),
            ),
        )
        .filter(match_priority__lte=4)
        .order_by("match_priority", "-created_at")
    )

    return qs


def get_reliability_report(project_id, start_time, end_time):
    """
    Calculate MTTR and MTBF for a project within a time window.
    """
    cache_key = f"reliability_report_{project_id}_{start_time.isoformat()}_{end_time.isoformat()}"
    cached_report = cache.get(cache_key)
    if cached_report:
        return cached_report

    qs = Incident.objects.filter(
        project_id=project_id,
        created_at__gte=start_time,
        created_at__lte=end_time,
    )

    total_incidents = qs.count()

    resolved_qs = qs.filter(status=Incident.Status.RESOLVED, resolved_at__isnull=False)
    mttr_res = resolved_qs.annotate(
        duration=ExpressionWrapper(F("resolved_at") - F("created_at"), output_field=DurationField())
    ).aggregate(avg_mttr=Avg("duration"))

    mttr_td = mttr_res["avg_mttr"]
    mttr_seconds = mttr_td.total_seconds() if mttr_td else None

    mtbf_res = qs.aggregate(
        min_created=Min("created_at"),
        max_created=Max("created_at"),
        count=Count("id"),
    )

    mtbf_seconds = None
    if mtbf_res["count"] >= 2 and mtbf_res["max_created"] and mtbf_res["min_created"]:
        delta = (mtbf_res["max_created"] - mtbf_res["min_created"]).total_seconds()
        mtbf_seconds = delta / (mtbf_res["count"] - 1)

    by_job_qs = (
        qs.filter(job__isnull=False)
        .values("job_id", "job__name", "job__task_identifier")
        .annotate(
            total_count=Count("id"),
            resolved_count=Count("id", filter=Q(status=Incident.Status.RESOLVED)),
            min_created=Min("created_at"),
            max_created=Max("created_at"),
        )
    )

    job_mttr_qs = (
        resolved_qs.filter(job__isnull=False)
        .values("job_id")
        .annotate(
            avg_mttr=Avg(
                ExpressionWrapper(F("resolved_at") - F("created_at"), output_field=DurationField())
            )
        )
    )
    job_mttr_map = {
        row["job_id"]: row["avg_mttr"].total_seconds() if row["avg_mttr"] else None
        for row in job_mttr_qs
    }

    by_job_list = []
    for row in by_job_qs:
        j_id = row["job_id"]
        j_count = row["total_count"]

        j_mtbf = None
        if j_count >= 2 and row["max_created"] and row["min_created"]:
            j_delta = (row["max_created"] - row["min_created"]).total_seconds()
            j_mtbf = j_delta / (j_count - 1)

        j_mttr = job_mttr_map.get(j_id)

        by_job_list.append(
            {
                "job_id": j_id,
                "job_name": row["job__name"] or f"Job #{j_id}",
                "task_identifier": row["job__task_identifier"] or "",
                "total_incidents": j_count,
                "resolved_incidents": row["resolved_count"],
                "mttr_seconds": j_mttr,
                "mtbf_seconds": j_mtbf,
            }
        )

    report = {
        "project_id": project_id,
        "start": start_time.isoformat(),
        "end": end_time.isoformat(),
        "total_incidents": total_incidents,
        "resolved_incidents": resolved_qs.count(),
        "mttr_seconds": mttr_seconds,
        "mtbf_seconds": mtbf_seconds,
        "by_job": by_job_list,
        "per_job": by_job_list,
    }

    cache.set(cache_key, report, timeout=300)
    return report


def start_runbook_execution(incident_id, runbook_id, actor):
    with transaction.atomic():
        incident = Incident.objects.select_for_update().get(id=incident_id)
        runbook = Runbook.objects.get(id=runbook_id)

        if not runbook.is_active:
            raise ValueError("Runbook is not active.")

        if runbook.project_id != incident.project_id:
            raise ValueError("Runbook belongs to a different project.")

        if runbook.job_id is not None and runbook.job_id != incident.job_id:
            raise ValueError("Runbook is specific to a different job.")

        execution = IncidentRunbookExecution.objects.create(
            incident=incident,
            runbook=runbook,
            status=IncidentRunbookExecution.Status.IN_PROGRESS,
            started_at=timezone.now(),
            started_by=actor,
        )

        _log_incident_event(
            incident,
            IncidentEvent.EventType.RUNBOOK_STARTED,
            actor=actor,
            metadata={
                "execution_id": execution.id,
                "runbook_id": runbook.id,
                "runbook_name": runbook.name,
                "previous_status": "PENDING",
                "new_status": "IN_PROGRESS",
                "message": f"Started runbook: {runbook.name}",
            },
        )
        return execution


ALLOWED_STEP_STATES = {"PENDING", "IN_PROGRESS", "COMPLETED", "SKIPPED"}

VALID_STEP_TRANSITIONS = {
    "PENDING": {"IN_PROGRESS", "SKIPPED"},
    "IN_PROGRESS": {"COMPLETED", "SKIPPED"},
    "COMPLETED": set(),
    "SKIPPED": set(),
}


def transition_runbook_step(execution_id, step_id, from_state, to_state, actor, incident_id=None):
    with transaction.atomic():
        execution = (
            IncidentRunbookExecution.objects.select_related("runbook")
            .select_for_update()
            .get(id=execution_id)
        )

        if incident_id is not None and execution.incident_id != incident_id:
            raise ValueError("Runbook execution does not belong to this incident.")

        if execution.status in [
            IncidentRunbookExecution.Status.COMPLETED,
            IncidentRunbookExecution.Status.CANCELLED,
        ]:
            raise ValueError(f"Cannot transition step in a {execution.status} runbook execution.")

        if from_state not in ALLOWED_STEP_STATES or to_state not in ALLOWED_STEP_STATES:
            raise ValueError(f"Invalid step state. Allowed states: {sorted(ALLOWED_STEP_STATES)}")

        valid_step_ids = set()
        for s in execution.runbook.steps or []:
            if isinstance(s, dict):
                if "id" in s:
                    valid_step_ids.add(str(s["id"]))
            else:
                valid_step_ids.add(str(s))

        if valid_step_ids and str(step_id) not in valid_step_ids:
            raise ValueError(
                f"Step '{step_id}' does not exist in runbook '{execution.runbook.name}'."
            )

        current_state = execution.step_states.get(str(step_id), "PENDING")
        if current_state != from_state:
            raise ValueError(f"Step {step_id} is currently {current_state}, not {from_state}")

        allowed_targets = VALID_STEP_TRANSITIONS.get(current_state, set())
        if to_state not in allowed_targets:
            raise ValueError(
                f"Invalid step state transition from '{current_state}' to '{to_state}'. "
                "Allowed transitions: PENDING -> IN_PROGRESS, PENDING -> SKIPPED, IN_PROGRESS -> COMPLETED, IN_PROGRESS -> SKIPPED."
            )

        execution.step_states[str(step_id)] = to_state

        history_entry = {
            "step_id": str(step_id),
            "from": from_state,
            "to": to_state,
            "actor_id": actor.id if actor else None,
            "actor_name": (actor.get_full_name() or actor.email) if actor else "System",
            "timestamp": timezone.now().isoformat(),
        }

        if not execution.step_history:
            execution.step_history = []
        execution.step_history.append(history_entry)

        execution.save(update_fields=["step_states", "step_history"])
        return execution


VALID_EXECUTION_TRANSITIONS = {
    "PENDING": {"IN_PROGRESS"},
    "IN_PROGRESS": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


def update_runbook_execution_status(incident_id, execution_id, new_status, actor):
    with transaction.atomic():
        execution = (
            IncidentRunbookExecution.objects.select_related("runbook", "incident")
            .select_for_update()
            .get(id=execution_id)
        )

        if execution.incident_id != incident_id:
            raise ValueError("Runbook execution does not belong to this incident.")

        if execution.runbook.project_id != execution.incident.project_id:
            raise ValueError("Runbook belongs to a different project.")

        allowed_targets = VALID_EXECUTION_TRANSITIONS.get(execution.status, set())
        if new_status not in allowed_targets:
            raise ValueError(
                f"Invalid runbook execution status transition from '{execution.status}' to '{new_status}'."
            )

        if new_status == IncidentRunbookExecution.Status.IN_PROGRESS and not execution.started_at:
            execution.started_at = timezone.now()

        if new_status in [
            IncidentRunbookExecution.Status.COMPLETED,
            IncidentRunbookExecution.Status.CANCELLED,
        ]:
            execution.completed_at = timezone.now()

        previous_status = execution.status
        execution.status = new_status
        execution.save(update_fields=["status", "started_at", "completed_at"])

        if new_status == IncidentRunbookExecution.Status.COMPLETED:
            event_type = IncidentEvent.EventType.RUNBOOK_COMPLETED
        elif new_status == IncidentRunbookExecution.Status.CANCELLED:
            event_type = IncidentEvent.EventType.RUNBOOK_CANCELLED
        else:
            event_type = IncidentEvent.EventType.RUNBOOK_STARTED

        _log_incident_event(
            execution.incident,
            event_type,
            actor=actor,
            metadata={
                "execution_id": execution.id,
                "runbook_id": execution.runbook.id,
                "runbook_name": execution.runbook.name,
                "previous_status": previous_status,
                "new_status": new_status,
                "message": f"Runbook execution '{execution.runbook.name}' marked as {new_status}.",
            },
        )
        return execution


def save_incident_postmortem(incident_id, data, actor):
    with transaction.atomic():
        incident = Incident.objects.select_for_update().get(id=incident_id)
        postmortem, created = IncidentPostmortem.objects.get_or_create(
            incident=incident,
            defaults={"created_by": actor, "status": IncidentPostmortem.Status.PENDING},
        )

        if not created:
            if postmortem.status == IncidentPostmortem.Status.COMPLETED:
                raise ValueError("Postmortem is completed and cannot be modified.")
            postmortem.updated_by = actor

        for field in [
            "summary",
            "impact_summary",
            "probable_cause",
            "confirmed_root_cause",
            "resolution",
            "contributing_factors",
            "timeline",
            "what_went_well",
            "what_went_wrong",
        ]:
            if field in data:
                setattr(postmortem, field, data[field])

        if "root_cause" in data and "confirmed_root_cause" not in data:
            postmortem.confirmed_root_cause = data["root_cause"]

        postmortem.save()
        return postmortem


def submit_postmortem_review(incident_id, actor):
    with transaction.atomic():
        incident = Incident.objects.select_for_update().get(id=incident_id)
        postmortem, created = IncidentPostmortem.objects.get_or_create(
            incident=incident,
            defaults={"created_by": actor, "status": IncidentPostmortem.Status.PENDING},
        )

        if postmortem.status != IncidentPostmortem.Status.PENDING:
            raise ValueError(
                f"Postmortem must be in PENDING status to submit for review, currently '{postmortem.status}'."
            )

        if not (postmortem.summary and postmortem.summary.strip()):
            raise ValueError("Postmortem must have a summary before submitting for review.")

        postmortem.status = IncidentPostmortem.Status.IN_REVIEW
        postmortem.reviewed_by = actor
        postmortem.reviewed_at = timezone.now()
        postmortem.updated_by = actor
        postmortem.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "updated_by", "updated_at"]
        )

        _log_incident_event(
            incident,
            IncidentEvent.EventType.POSTMORTEM_SUBMITTED,
            actor=actor,
            metadata={
                "postmortem_id": postmortem.id,
                "status": "IN_REVIEW",
                "message": "Postmortem draft submitted for review.",
            },
        )
        return postmortem


def complete_postmortem_review(incident_id, actor):
    with transaction.atomic():
        incident = Incident.objects.select_for_update().get(id=incident_id)
        postmortem, created = IncidentPostmortem.objects.get_or_create(
            incident=incident,
            defaults={"created_by": actor, "status": IncidentPostmortem.Status.PENDING},
        )

        if postmortem.status != IncidentPostmortem.Status.IN_REVIEW:
            raise ValueError(
                f"Postmortem must be in IN_REVIEW status to be completed, currently '{postmortem.status}'."
            )

        if not (postmortem.summary and postmortem.summary.strip()):
            raise ValueError("Postmortem must have a summary before completing review.")

        postmortem.status = IncidentPostmortem.Status.COMPLETED
        postmortem.updated_by = actor
        postmortem.save(update_fields=["status", "updated_by", "updated_at"])

        _log_incident_event(
            incident,
            IncidentEvent.EventType.POSTMORTEM_COMPLETED,
            actor=actor,
            metadata={
                "postmortem_id": postmortem.id,
                "status": "COMPLETED",
                "message": "Postmortem review completed and finalized.",
            },
        )
        return postmortem


def add_postmortem_action_item(postmortem_id, data, actor):
    with transaction.atomic():
        postmortem = (
            IncidentPostmortem.objects.select_related("incident__project__team")
            .select_for_update()
            .get(id=postmortem_id)
        )

        if postmortem.status == IncidentPostmortem.Status.COMPLETED:
            raise ValueError("Cannot add action items to a completed postmortem.")

        owner = None
        owner_id = data.get("owner_id") or data.get("owner")
        if owner_id:
            owner = TeamMember.objects.filter(
                id=owner_id,
                team_id=postmortem.incident.project.team_id,
                is_active=True,
            ).first()
            if not owner:
                raise ValueError(
                    "Action item owner must be an active member of the project's team."
                )

        status_val = data.get("status", PostmortemActionItem.Status.PENDING)
        completed_at = (
            timezone.now() if status_val == PostmortemActionItem.Status.COMPLETED else None
        )

        title = data.get("title") or data.get("description", "")[:255] or "Action Item"

        item = PostmortemActionItem.objects.create(
            postmortem=postmortem,
            title=title,
            description=data.get("description", ""),
            owner=owner,
            status=status_val,
            due_date=data.get("due_date"),
            completed_at=completed_at,
        )
        return item


def update_postmortem_action_item(item_id, data, actor):
    with transaction.atomic():
        item = (
            PostmortemActionItem.objects.select_related("postmortem__incident__project__team")
            .select_for_update()
            .get(id=item_id)
        )

        if item.postmortem.status == IncidentPostmortem.Status.COMPLETED:
            raise ValueError("Cannot modify action items of a completed postmortem.")

        if "owner_id" in data or "owner" in data:
            owner_id = data.get("owner_id") or data.get("owner")
            if owner_id:
                owner = TeamMember.objects.filter(
                    id=owner_id,
                    team_id=item.postmortem.incident.project.team_id,
                    is_active=True,
                ).first()
                if not owner:
                    raise ValueError(
                        "Action item owner must be an active member of the project's team."
                    )
                item.owner = owner
            else:
                item.owner = None

        if "title" in data:
            item.title = data["title"]
        if "description" in data:
            item.description = data["description"]
        if "due_date" in data:
            item.due_date = data["due_date"]
        if "status" in data:
            new_status = data["status"]
            if (
                new_status == PostmortemActionItem.Status.COMPLETED
                and item.status != PostmortemActionItem.Status.COMPLETED
            ):
                item.completed_at = timezone.now()
            elif new_status != PostmortemActionItem.Status.COMPLETED:
                item.completed_at = None
            item.status = new_status

        item.save()
        return item


def build_incident_knowledge(incident):
    """
    Deterministic, serializable structured knowledge artifact for an incident.
    Combines:
    - Incident core facts
    - AlertRule and trigger metadata
    - Incident timeline events
    - Incident intelligence (impact, correlations, probable root causes)
    - Runbooks used & step history
    - Postmortem analysis & action items
    """
    incident_id = incident.id if hasattr(incident, "id") else incident

    incident_obj = (
        Incident.objects.select_related(
            "project__team",
            "job",
            "alert_rule",
            "assigned_to__user",
            "intelligence",
            "postmortem__reviewed_by",
            "postmortem__created_by",
            "postmortem__updated_by",
        )
        .prefetch_related(
            Prefetch(
                "events",
                queryset=IncidentEvent.objects.select_related("actor").order_by("event_time", "id"),
            ),
            Prefetch(
                "runbook_executions",
                queryset=IncidentRunbookExecution.objects.select_related(
                    "runbook", "started_by", "runbook__created_by", "runbook__updated_by"
                ).order_by("started_at", "id"),
            ),
            Prefetch(
                "postmortem__action_items",
                queryset=PostmortemActionItem.objects.select_related("owner__user").order_by("id"),
            ),
        )
        .get(id=incident_id)
    )

    # 1. Facts
    incident_data = IncidentSerializer(incident_obj).data

    # 2. Timeline Events
    events_data = IncidentEventSerializer(incident_obj.events.all(), many=True).data

    # 3. Intelligence
    intelligence_data = None
    if hasattr(incident_obj, "intelligence") and incident_obj.intelligence:
        intelligence_data = IncidentIntelligenceSerializer(incident_obj.intelligence).data

    # 4. Runbook Executions & Step History
    executions_data = IncidentRunbookExecutionSerializer(
        incident_obj.runbook_executions.all(), many=True
    ).data

    # 5. Postmortem & Action Items
    postmortem_data = None
    if hasattr(incident_obj, "postmortem") and incident_obj.postmortem:
        postmortem_data = IncidentPostmortemSerializer(incident_obj.postmortem).data

    knowledge = {
        "incident": incident_data,
        "events": events_data,
        "intelligence": intelligence_data,
        "runbook_executions": executions_data,
        "postmortem": postmortem_data,
    }
    return knowledge
