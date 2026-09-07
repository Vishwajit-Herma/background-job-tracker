from django.core.cache import cache
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Incident,
    IncidentPostmortem,
    PostmortemActionItem,
    Runbook,
)
from .permissions import IncidentPermission, IncidentNotePermission, RunbookPermission
from .serializers import (
    IncidentSerializer,
    IncidentEventSerializer,
    IncidentNoteSerializer,
    IncidentAssignSerializer,
    IncidentIntelligenceSerializer,
    IncidentIntelligencePendingSerializer,
    RunbookSerializer,
    IncidentRunbookExecutionSerializer,
    ExecuteRunbookSerializer,
    TransitionStepSerializer,
    UpdateRunbookExecutionStatusSerializer,
    IncidentPostmortemSerializer,
    PostmortemActionItemSerializer,
    ActionItemCreateSerializer,
)
from apps.config_management.views import BaseViewSetConfig, CustomResponseMixin
from apps.teams.models import TeamMember
from .services import (
    assign_incident,
    acknowledge_incident,
    resolve_incident,
    reopen_incident,
    add_incident_note,
    find_recommended_runbooks,
    start_runbook_execution,
    transition_runbook_step,
    update_runbook_execution_status,
    save_incident_postmortem,
    submit_postmortem_review,
    complete_postmortem_review,
    add_postmortem_action_item,
    update_postmortem_action_item,
    build_incident_knowledge,
)
from .tasks import calculate_incident_intelligence_task


class IncidentViewSet(BaseViewSetConfig, CustomResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for managing Incidents.
    """

    serializer_class = IncidentSerializer
    permission_classes = [IsAuthenticated, IncidentPermission]
    filterset_fields = [
        "project",
        "job",
        "status",
        "severity",
        "assigned_to",
        "assigned_to__user",
        "alert_rule",
    ]
    search_fields = ["id", "project__name", "job__name"]
    ordering_fields = ["created_at", "updated_at", "severity"]

    def get_queryset(self):
        """
        Enforce tenant isolation. User can only see incidents for projects
        owned by teams they are active members of.
        """
        return (
            Incident.objects.filter(
                project__team__members__user=self.request.user,
                project__team__members__is_active=True,
            )
            .select_related(
                "project",
                "job",
                "alert_rule",
                "assigned_to__user",
                "assigned_by",
                "acknowledged_by",
                "resolved_by",
            )
            .distinct()
        )

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        """
        Assign or unassign an incident to a team member.

        Payload:
            - member_id: TeamMember ID to assign to, or null to unassign.

        Behavior:
            - Validates member active status within project's team.
            - Logs an ASSIGNED event in the incident timeline.
            - Rejects assignment for RESOLVED incidents.
        """
        incident = self.get_object()
        serializer = IncidentAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        member_id = serializer.validated_data["member_id"]

        try:
            incident = assign_incident(incident.id, member_id, request.user)
            return Response(IncidentSerializer(incident).data)
        except ValueError as e:
            return Response(
                {"error": str(e), "message": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        """
        Acknowledge an OPEN incident.

        Behavior:
            - Transitions status from OPEN to ACKNOWLEDGED.
            - Records acknowledged_by and acknowledged_at.
            - Logs an ACKNOWLEDGED event in timeline.
        """
        incident = self.get_object()

        try:
            incident = acknowledge_incident(incident.id, request.user)
            return Response(IncidentSerializer(incident).data)
        except ValueError as e:
            return Response(
                {"error": str(e), "message": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        """
        Manually resolve an incident.

        Behavior:
            - Transitions status to RESOLVED.
            - Sets resolution_type = MANUAL.
            - Records resolved_by and resolved_at.
            - Logs a MANUALLY_RESOLVED event in timeline.
        """
        incident = self.get_object()

        try:
            incident = resolve_incident(incident.id, request.user)
            return Response(IncidentSerializer(incident).data)
        except ValueError as e:
            return Response(
                {"error": str(e), "message": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        """
        Reopen a RESOLVED incident.

        Behavior:
            - Transitions status back from RESOLVED to OPEN.
            - Clears resolution metadata.
            - Logs a REOPENED event in timeline.
        """
        incident = self.get_object()

        try:
            incident = reopen_incident(incident.id, request.user)
            return Response(IncidentSerializer(incident).data)
        except ValueError as e:
            return Response(
                {"error": str(e), "message": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(
        detail=True,
        methods=["get", "post"],
        permission_classes=[IsAuthenticated, IncidentPermission, IncidentNotePermission],
    )
    def notes(self, request, pk=None):
        """
        List or add investigation notes for an incident.

        GET:
            - Returns list of immutable investigation notes.
        POST:
            - Payload: {"content": "Investigation findings..."}
            - Adds a new note authored by request.user and logs a NOTE_ADDED event.
        """
        incident = self.get_object()

        if request.method == "GET":
            notes = incident.notes.select_related("author").order_by("created_at")
            serializer = IncidentNoteSerializer(notes, many=True)
            return Response(serializer.data)

        elif request.method == "POST":
            serializer = IncidentNoteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            note = add_incident_note(
                incident.id, request.user, serializer.validated_data["content"]
            )

            response_serializer = IncidentNoteSerializer(note)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        """
        Retrieve full timeline audit events for an incident.

        Returns:
            - Chronological list of events (creation, assignment, acknowledgment, notes, runbooks, postmortem).
        """
        incident = self.get_object()
        events = incident.events.select_related("actor").order_by("event_time", "id")
        serializer = IncidentEventSerializer(events, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="intelligence")
    def intelligence(self, request, pk=None):
        """
        Returns derived intelligence analysis for an incident.

        Behavior:
            - If calculated: returns HTTP 200 with impact, correlations, probable causes.
            - If missing/pending: queues async task and returns HTTP 202 Accepted.
        """
        incident = self.get_object()
        intel = getattr(incident, "intelligence", None)
        if intel:
            serializer = IncidentIntelligenceSerializer(intel)
            return Response(serializer.data, status=status.HTTP_200_OK)

        lock_key = f"intelligence_calculating_{incident.id}"
        if cache.add(lock_key, True, timeout=300):
            calculate_incident_intelligence_task.delay(incident.id)

        pending_data = {
            "status": "PENDING",
            "message": "Incident intelligence calculation is in progress.",
            "incident_id": incident.id,
            "impact": None,
            "correlations": [],
            "probable_causes": [],
            "analysis_window_start": None,
            "analysis_window_end": None,
            "analysis_version": "1.0",
            "calculated_at": None,
        }
        serializer = IncidentIntelligencePendingSerializer(pending_data)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"], url_path="recommended-runbooks")
    def recommended_runbooks(self, request, pk=None):
        """
        Find and recommend active runbooks for an incident.

        Behavior:
            - Scores matching runbooks based on project, job, metric, and trigger matching.
            - Rendered in UI under Incident Detail -> Response tab.
        """
        incident = self.get_object()
        runbooks = find_recommended_runbooks(incident.id)
        return Response(RunbookSerializer(runbooks, many=True).data)

    @action(detail=True, methods=["post"], url_path="execute-runbook")
    def execute_runbook(self, request, pk=None):
        """
        Start execution of a runbook for an incident.

        Payload:
            - runbook_id: ID of the active runbook to execute.

        Behavior:
            - Instantiates an IncidentRunbookExecution with step states set to PENDING.
            - Logs a RUNBOOK_STARTED event in the incident timeline.
        """
        incident = self.get_object()
        serializer = ExecuteRunbookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            execution = start_runbook_execution(
                incident.id,
                serializer.validated_data["runbook_id"],
                request.user,
            )
            return Response(
                IncidentRunbookExecutionSerializer(execution).data, status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"runbook-execution/(?P<execution_id>[^/.]+)/status",
    )
    def runbook_execution_status(self, request, pk=None, execution_id=None):
        """
        Update runbook execution status (e.g. COMPLETED, CANCELLED).

        Payload:
            - status: "COMPLETED" | "CANCELLED"
        """
        incident = self.get_object()
        serializer = UpdateRunbookExecutionStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            execution = update_runbook_execution_status(
                incident_id=incident.id,
                execution_id=execution_id,
                new_status=serializer.validated_data["status"],
                actor=request.user,
            )
            return Response(IncidentRunbookExecutionSerializer(execution).data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="runbook-executions")
    def runbook_executions(self, request, pk=None):
        """
        List all runbook executions for an incident.
        """
        incident = self.get_object()
        executions = incident.runbook_executions.select_related(
            "runbook", "started_by", "runbook__created_by", "runbook__updated_by"
        ).order_by("-started_at")
        return Response(IncidentRunbookExecutionSerializer(executions, many=True).data)

    @action(detail=True, methods=["get"], url_path="knowledge")
    def knowledge(self, request, pk=None):
        """
        Generate structured knowledge artifact for an incident.

        Returns:
            - Comprehensive JSON artifact combining facts, timeline, intelligence, runbooks, and postmortem.
            - Rendered in UI under Incident Detail -> Postmortem tab -> Knowledge Panel.
        """
        incident = self.get_object()
        try:
            data = build_incident_knowledge(incident.id)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["post"], url_path="transition-step")
    def transition_step(self, request, pk=None):
        """
        Transition a runbook execution step state.

        Payload:
            - execution_id: ID of the runbook execution.
            - step_id: Step identifier.
            - from_state: Current step state (e.g. PENDING, IN_PROGRESS).
            - to_state: Targeted step state (e.g. IN_PROGRESS, COMPLETED, SKIPPED).
        """
        incident = self.get_object()
        serializer = TransitionStepSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            execution = transition_runbook_step(
                execution_id=serializer.validated_data["execution_id"],
                step_id=serializer.validated_data["step_id"],
                from_state=serializer.validated_data["from_state"],
                to_state=serializer.validated_data["to_state"],
                actor=request.user,
                incident_id=incident.id,
            )
            return Response(IncidentRunbookExecutionSerializer(execution).data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get", "post"], url_path="postmortem")
    def postmortem(self, request, pk=None):
        """
        Retrieve or save/update the postmortem report for an incident.

        GET:
            - Returns incident postmortem if created, else HTTP 404.
        POST:
            - Payload: {"summary": "...", "root_cause_analysis": "...", "confirmed_root_cause": "...", "prevention_steps": "..."}
            - Saves or updates postmortem draft.
        """
        incident = self.get_object()

        if request.method == "GET":
            postmortem = getattr(incident, "postmortem", None)
            if not postmortem:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
            return Response(IncidentPostmortemSerializer(postmortem).data)

        elif request.method == "POST":
            try:
                postmortem = save_incident_postmortem(incident.id, request.data, request.user)
                return Response(IncidentPostmortemSerializer(postmortem).data)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="postmortem/submit-review")
    def postmortem_submit_review(self, request, pk=None):
        """
        Submit postmortem draft for review (PENDING -> IN_REVIEW).
        Requires summary field to be present.
        """
        incident = self.get_object()
        try:
            postmortem = submit_postmortem_review(incident.id, request.user)
            return Response(IncidentPostmortemSerializer(postmortem).data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="postmortem/complete")
    def postmortem_complete(self, request, pk=None):
        """
        Complete postmortem review (IN_REVIEW -> COMPLETED).
        Requires summary field and that all action items are completed.
        """
        incident = self.get_object()
        try:
            postmortem = complete_postmortem_review(incident.id, request.user)
            return Response(IncidentPostmortemSerializer(postmortem).data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get", "post"], url_path="postmortem/action-items")
    def postmortem_action_items(self, request, pk=None):
        """
        List or create postmortem action items (prevention tasks).

        GET:
            - Returns list of action items for incident's postmortem.
        POST:
            - Payload: {"title": "...", "owner": member_id, "due_date": "YYYY-MM-DD"}
            - Creates a new postmortem action item.
        """
        incident = self.get_object()
        postmortem = getattr(incident, "postmortem", None)

        if request.method == "GET":
            if not postmortem:
                return Response([])
            items = postmortem.action_items.select_related("owner__user").all()
            return Response(PostmortemActionItemSerializer(items, many=True).data)

        elif request.method == "POST":
            if not postmortem:
                postmortem = save_incident_postmortem(incident.id, {}, request.user)

            serializer = ActionItemCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            try:
                data = serializer.validated_data.copy()
                if "owner" in data and data["owner"]:
                    data["owner_id"] = data["owner"].id
                item = add_postmortem_action_item(postmortem.id, data, request.user)
                return Response(
                    PostmortemActionItemSerializer(item).data, status=status.HTTP_201_CREATED
                )
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"postmortem/action-items/(?P<item_id>[^/.]+)",
    )
    def postmortem_action_item_detail(self, request, pk=None, item_id=None):
        """
        Update or delete a specific postmortem action item.

        PATCH:
            - Payload: {"title": "...", "status": "IN_PROGRESS" | "COMPLETED", "due_date": "..."}
            - Restricted to team admins or assigned item owner.
        DELETE:
            - Deletes action item. Cannot delete items from completed postmortems.
        """
        incident = self.get_object()
        postmortem = getattr(incident, "postmortem", None)
        if not postmortem:
            return Response({"detail": "Postmortem not found."}, status=status.HTTP_404_NOT_FOUND)

        item = PostmortemActionItem.objects.filter(id=item_id, postmortem=postmortem).first()
        if not item:
            return Response({"detail": "Action item not found."}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "DELETE":
            if postmortem.status == IncidentPostmortem.Status.COMPLETED:
                return Response(
                    {"error": "Cannot delete action items of a completed postmortem."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        elif request.method == "PATCH":
            member = TeamMember.objects.filter(
                team=incident.project.team, user=request.user, is_active=True
            ).first()

            is_admin = bool(member and member.is_admin())
            is_assigned_owner = bool(member and item.owner_id and item.owner_id == member.id)

            if not is_admin and not is_assigned_owner:
                return Response(
                    {
                        "detail": "Only team admins or the assigned item owner can update this action item."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            if not is_admin and ("owner" in request.data or "owner_id" in request.data):
                new_owner = request.data.get("owner") or request.data.get("owner_id")
                if new_owner and int(new_owner) != member.id:
                    return Response(
                        {"error": "Only team admins can reassign action items to other members."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            try:
                updated_item = update_postmortem_action_item(item.id, request.data, request.user)
                return Response(PostmortemActionItemSerializer(updated_item).data)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RunbookViewSet(BaseViewSetConfig, viewsets.ModelViewSet):
    """
    API endpoints for managing Runbooks.
    """

    serializer_class = RunbookSerializer
    permission_classes = [IsAuthenticated, RunbookPermission]
    filterset_fields = ["project", "job", "is_active", "trigger_type"]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "updated_at", "name"]

    def get_queryset(self):
        """
        Enforce tenant isolation. User can only see runbooks for projects
        owned by teams they are active members of.
        """
        return (
            Runbook.objects.filter(
                project__team__members__user=self.request.user,
                project__team__members__is_active=True,
            )
            .select_related(
                "project",
                "job",
                "created_by",
                "updated_by",
            )
            .distinct()
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        if instance.executions.exists():
            instance.is_active = False
            instance.save(update_fields=["is_active", "updated_at"])
        else:
            instance.delete()

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        runbook = self.get_object()
        runbook.is_active = False
        runbook.save(update_fields=["is_active", "updated_at"])
        return Response(RunbookSerializer(runbook).data, status=status.HTTP_200_OK)
