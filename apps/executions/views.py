from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import IntegrityError
from django_filters.rest_framework import DjangoFilterBackend

from apps.config_management.views import CustomBaseViewSet
from .models import Execution, ExecutionEvent
from .serializers import (
    ExecutionSerializer,
    ExecutionEventSerializer,
    ExecutionIngestSerializer,
    ExecutionBatchIngestSerializer,
)
from .authentication import ProjectAPIKeyAuthentication
from .permissions import HasActiveProjectAPIKey, ExecutionReadPermission
from .services import ingest_executions_batch


@extend_schema_view(
    create=extend_schema(
        summary="Ingest Single Execution",
        description="Ingest a single background job execution event from an SDK.",
        request=ExecutionIngestSerializer,
        responses={202: None},
    ),
    batch=extend_schema(
        summary="Ingest Batch Executions",
        description="Ingest a batch of background job execution events. Max 500 per request.",
        request=ExecutionBatchIngestSerializer,
        responses={202: None},
    ),
)
class IngestionViewSet(viewsets.ViewSet):
    """
    Machine-to-machine API for ingesting Execution telemetry.
    Authenticated via X-API-Key header.
    """

    authentication_classes = [ProjectAPIKeyAuthentication]
    permission_classes = [HasActiveProjectAPIKey]

    def create(self, request):
        """
        Ingest a single execution event.
        """
        serializer = ExecutionIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project = request.auth

        for attempt in range(3):
            try:
                result = ingest_executions_batch(project, [serializer.validated_data])
                break
            except IntegrityError:
                if attempt == 2:
                    raise

        return Response(
            {
                "status_code": status.HTTP_202_ACCEPTED,
                "status": "success",
                "message": "Execution accepted.",
                "data": result,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["post"])
    def batch(self, request):
        """
        Ingest a batch of execution events.
        """
        serializer = ExecutionBatchIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project = request.auth
        executions_data = serializer.validated_data["executions"]

        for attempt in range(3):
            try:
                result = ingest_executions_batch(project, executions_data)
                break
            except IntegrityError:
                if attempt == 2:
                    raise

        return Response(
            {
                "status_code": status.HTTP_202_ACCEPTED,
                "status": "success",
                "message": "Executions accepted.",
                "data": result,
            },
            status=status.HTTP_202_ACCEPTED,
        )


@extend_schema_view(
    list=extend_schema(
        summary="List Executions",
        description="Returns a paginated list of executions belonging to the user's team.",
    ),
    retrieve=extend_schema(
        summary="Retrieve Execution", description="Returns details of a specific execution."
    ),
)
class ExecutionViewSet(CustomBaseViewSet):
    """
    Human-facing read-only API for viewing Executions.
    """

    permission_classes = list(CustomBaseViewSet.permission_classes) + [ExecutionReadPermission]  # type: ignore[operator, list-item]
    serializer_class = ExecutionSerializer
    http_method_names = ["get", "head", "options"]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["job__project", "job", "status", "queue", "worker"]
    search_fields = ["external_id", "error_message"]
    ordering_fields = ["started_at", "duration_ms", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """
        Enforce strict tenant isolation: only return executions belonging to
        projects that the user is an active member of.
        """
        qs = (
            Execution.objects.filter(
                job__is_deleted=False,
                job__project__is_deleted=False,
                job__project__team__is_active=True,
                job__project__team__members__user=self.request.user,
                job__project__team__members__is_active=True,
            )
            .select_related("job", "job__project")
            .distinct()
        )
        return qs

    @extend_schema(
        summary="Execution Timeline",
        description="Returns the historical timeline of telemetry events for this execution.",
        responses={200: ExecutionEventSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        execution = self.get_object()
        events_qs = ExecutionEvent.objects.filter(execution=execution).order_by(
            "-event_timestamp", "-id"
        )

        page = self.paginate_queryset(events_qs)
        if page is not None:
            serializer = ExecutionEventSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ExecutionEventSerializer(events_qs, many=True)
        return Response(serializer.data)
