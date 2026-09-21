from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import IntegrityError
from django_filters.rest_framework import DjangoFilterBackend

from django.utils import timezone
from django.db.models import Q
from apps.config_management.views import CustomBaseViewSet
from apps.reliability.evaluators import evaluate_job_reliability
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
    throttle_classes = []  # Explicitly disable default AnonRateThrottle (100/hr) for M2M ingestion

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
    http_method_names = ["get", "post", "head", "options"]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["job__project", "job", "status", "queue", "worker"]
    search_fields = [
        "external_id",
        "job__name",
        "job__task_identifier",
        "worker",
        "queue",
        "error_message",
    ]
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

    def filter_queryset(self, queryset):
        search_query = self.request.query_params.get("search", "").strip()

        # Apply other filter backends (DjangoFilterBackend, OrderingFilter)
        for backend in list(self.filter_backends):
            if backend is not SearchFilter:
                queryset = backend().filter_queryset(self.request, queryset, self)

        if search_query:
            clean_term = search_query.lstrip("#").strip()
            if clean_term.isdigit():
                queryset = queryset.filter(
                    Q(id=int(clean_term))
                    | Q(external_id__icontains=search_query)
                    | Q(job__name__icontains=search_query)
                    | Q(job__task_identifier__icontains=search_query)
                    | Q(worker__icontains=search_query)
                    | Q(queue__icontains=search_query)
                    | Q(error_message__icontains=search_query)
                )
            else:
                queryset = queryset.filter(
                    Q(external_id__icontains=search_query)
                    | Q(job__name__icontains=search_query)
                    | Q(job__task_identifier__icontains=search_query)
                    | Q(worker__icontains=search_query)
                    | Q(queue__icontains=search_query)
                    | Q(error_message__icontains=search_query)
                )

        return queryset

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

    @extend_schema(
        summary="Cancel Execution",
        description="Cancel an in-progress or stuck running execution and re-evaluate job reliability.",
        responses={200: ExecutionSerializer},
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        execution = self.get_object()
        if execution.status not in [Execution.Status.RUNNING, Execution.Status.PENDING]:
            return Response(
                {
                    "detail": f"Execution is in terminal state '{execution.status}' and cannot be cancelled."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        execution.status = Execution.Status.CANCELLED
        execution.finished_at = timezone.now()
        execution.error_message = f"Manually cancelled by user ({request.user.email})"
        execution.save(update_fields=["status", "finished_at", "error_message"])

        evaluate_job_reliability(execution.job_id)

        execution.refresh_from_db()
        serializer = self.get_serializer(execution)
        return Response(serializer.data)
