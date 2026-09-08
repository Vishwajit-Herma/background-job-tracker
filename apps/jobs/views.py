from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.config_management.views import CustomBaseViewSet
from apps.core.realtime import publish_realtime_event
from apps.executions.analytics import get_job_analytics, get_trend, parse_analytics_query
from apps.executions.authentication import ProjectAPIKeyAuthentication
from apps.executions.models import Execution
from apps.executions.serializers import (
    JobAnalyticsSerializer,
    TrendResponseSerializer,
)
from apps.projects.models import Project
from apps.incidents.models import Incident
from django.db.models import Count, Q, Exists, OuterRef, Subquery, IntegerField
from django.db.models.functions import Coalesce
from .models import Job
from .permissions import JobPermission
from .serializers import (
    JobCreateSerializer,
    JobSerializer,
    JobUpdateSerializer,
    TaskRegistrySyncSerializer,
)
from .services import sync_task_registry


class JobViewSet(CustomBaseViewSet):
    """
    API endpoints for managing Jobs.
    """

    permission_classes = list(CustomBaseViewSet.permission_classes) + [JobPermission]  # type: ignore[operator, list-item]
    search_fields = ["name", "task_identifier", "project__name"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]
    filterset_fields = ["project", "status"]

    def get_serializer_class(self):
        if self.action == "create":
            return JobCreateSerializer
        if self.action in ["update", "partial_update"]:
            return JobUpdateSerializer
        if self.action == "sync":
            return TaskRegistrySyncSerializer
        return JobSerializer

    def get_queryset(self):
        """
        Enforce strict tenant isolation: only return jobs belonging to
        projects that the user is an active member of (via team membership).

        success_count uses a correlated Subquery instead of a joined COUNT
        to avoid Cartesian product inflation from multiple COUNT joins.
        """
        base_qs = Job.all_objects if getattr(self, "action", None) == "restore" else Job.objects

        critical_incidents = Incident.objects.filter(
            job=OuterRef("pk"),
            status__in=["OPEN", "ACKNOWLEDGED"],
            severity="CRITICAL",
        )

        success_subquery = (
            Execution.objects.filter(
                job=OuterRef("pk"),
                status="success",
            )
            .order_by()
            .values("job")
            .annotate(cnt=Count("id"))
            .values("cnt")
        )

        base_qs = base_qs.select_related("project", "created_by", "modified_by").annotate(
            executions_count=Count("executions", distinct=True),
            success_count=Coalesce(Subquery(success_subquery, output_field=IntegerField()), 0),
            active_incidents_count=Count(
                "incidents",
                filter=Q(incidents__status__in=["OPEN", "ACKNOWLEDGED"]),
                distinct=True,
            ),
            has_critical_incident=Exists(critical_incidents),
        )

        qs = base_qs.filter(
            project__is_deleted=False,
            project__team__is_active=True,
            project__team__members__user=self.request.user,
            project__team__members__is_active=True,
        ).distinct()
        return qs

    def perform_create(self, serializer):
        super().perform_create(serializer)
        job = serializer.instance
        publish_realtime_event(
            "job.updated",
            project_id=job.project_id,
            payload={"job_id": job.id, "action": "created"},
        )

    def perform_update(self, serializer):
        super().perform_update(serializer)
        job = serializer.instance
        publish_realtime_event(
            "job.updated",
            project_id=job.project_id,
            payload={"job_id": job.id, "action": "updated"},
        )

    def perform_destroy(self, instance):
        project_id = instance.project_id
        job_id = instance.id
        super().perform_destroy(instance)
        publish_realtime_event(
            "job.updated",
            project_id=project_id,
            payload={"job_id": job_id, "action": "deleted"},
        )

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """
        Restore a soft-deleted job.
        """
        job = self.get_object()

        if not job.is_deleted:
            return Response({"error": "Job is not deleted."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate that no active job has taken this task_identifier in this project
        if Job.objects.filter(project=job.project, task_identifier=job.task_identifier).exists():
            return Response(
                {
                    "task_identifier": "Cannot restore: an active Job with this task identifier already exists in this project."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        job.restore(user=request.user)
        publish_realtime_event(
            "job.updated",
            project_id=job.project_id,
            payload={"job_id": job.id, "action": "restored"},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=["post"],
        authentication_classes=[ProjectAPIKeyAuthentication],
        permission_classes=[],
    )
    def sync(self, request):
        """
        SDK ingestion endpoint to synchronize discovered task identifiers.
        Expects a body like {"tasks": ["task1", "task2"]}
        """
        project = request.auth
        if not isinstance(project, Project):
            return Response(
                {"error": "Invalid authentication."}, status=status.HTTP_401_UNAUTHORIZED
            )

        if project.is_deleted or project.status != Project.Status.ACTIVE:
            return Response(
                {"error": "Project is deleted or inactive."}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Execute discovery service logic
        sync_task_registry(project, serializer.validated_data["tasks"])

        return Response({"status": "synchronized"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """
        Get analytics for a specific Job.
        """
        job = self.get_object()
        start, end, _, filters = parse_analytics_query(request)

        # Remove job_id__in from filters since Job analytics is for a single job
        filters.pop("job_id__in", None)
        qs = Execution.objects.filter(**filters) if filters else None

        metrics = get_job_analytics(job.id, start, end, base_qs=qs)
        metrics["job_name"] = job.name
        metrics["task_identifier"] = job.task_identifier

        serializer = JobAnalyticsSerializer(metrics)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="analytics/trend")
    def analytics_trend(self, request, pk=None):
        """
        Get time-bucketed trend analytics for a specific Job.
        """
        job = self.get_object()
        start, end, bucket_type, filters = parse_analytics_query(request)

        filters.pop("job_id__in", None)
        qs = Execution.objects.filter(job_id=job.id, **filters)

        trend_data = get_trend(qs, start, end, bucket_type)
        serializer = TrendResponseSerializer(trend_data)
        return Response(serializer.data, status=status.HTTP_200_OK)
