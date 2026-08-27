from django.core.cache import cache
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Incident
from .permissions import IncidentPermission, IncidentNotePermission
from .serializers import (
    IncidentSerializer,
    IncidentEventSerializer,
    IncidentNoteSerializer,
    IncidentAssignSerializer,
    IncidentIntelligenceSerializer,
    IncidentIntelligencePendingSerializer,
)
from apps.config_management.views import BaseViewSetConfig, CustomResponseMixin
from .services import (
    assign_incident,
    acknowledge_incident,
    resolve_incident,
    reopen_incident,
    add_incident_note,
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
        return Incident.objects.filter(
            project__team__members__user=self.request.user,
            project__team__members__is_active=True,
        ).distinct()

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        incident = self.get_object()
        serializer = IncidentAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        member_id = serializer.validated_data["member_id"]

        try:
            incident = assign_incident(incident.id, member_id, request.user)
            return Response(IncidentSerializer(incident).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        incident = self.get_object()

        try:
            incident = acknowledge_incident(incident.id, request.user)
            return Response(IncidentSerializer(incident).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        incident = self.get_object()

        try:
            incident = resolve_incident(incident.id, request.user)
            return Response(IncidentSerializer(incident).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        incident = self.get_object()

        try:
            incident = reopen_incident(incident.id, request.user)
            return Response(IncidentSerializer(incident).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["get", "post"],
        permission_classes=[IsAuthenticated, IncidentPermission, IncidentNotePermission],
    )
    def notes(self, request, pk=None):
        incident = self.get_object()

        if request.method == "GET":
            notes = incident.notes.all().order_by("created_at")
            serializer = IncidentNoteSerializer(notes, many=True)
            return Response(serializer.data)

        elif request.method == "POST":
            serializer = IncidentNoteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            note = add_incident_note(
                incident.id, request.user, serializer.validated_data["content"]
            )

            # Since we didn't save via serializer, we create a new one to return data
            response_serializer = IncidentNoteSerializer(note)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        incident = self.get_object()
        events = incident.events.order_by("event_time", "id")
        serializer = IncidentEventSerializer(events, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="intelligence")
    def intelligence(self, request, pk=None):
        """
        Returns derived intelligence for an incident.
        Never executes heavy synchronous calculation in the request cycle.
        If intelligence is pending, returns 202 Accepted and queues async calculation.
        """
        incident = self.get_object()
        intel = getattr(incident, "intelligence", None)
        if intel:
            serializer = IncidentIntelligenceSerializer(intel)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Trigger async calculation if missing and not already calculating
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
