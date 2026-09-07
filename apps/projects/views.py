from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.config_management.views import CustomBaseViewSet
from apps.executions.analytics import get_project_analytics, get_trend, parse_analytics_query
from apps.executions.models import Execution
from apps.executions.serializers import (
    ProjectAnalyticsSerializer,
    TrendResponseSerializer,
)
from apps.incidents.models import Incident
from .models import APIKey, Project
from .permissions import APIKeyPermission, ProjectPermission
from .serializers import APIKeyCreateSerializer, APIKeySerializer, ProjectSerializer
from django.db.models import Count, Q, Exists, OuterRef, Subquery, IntegerField
from django.db.models.functions import Coalesce


class ProjectViewSet(CustomBaseViewSet):
    """
    API endpoints for managing Projects.
    """

    serializer_class = ProjectSerializer
    permission_classes = list(CustomBaseViewSet.permission_classes) + [ProjectPermission]  # type: ignore[operator, list-item]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]
    filterset_fields = ["team", "status"]

    def _get_base_tenant_qs(self):
        """Minimal queryset for tenant isolation — no expensive annotations."""
        base = Project.all_objects if getattr(self, "action", None) == "restore" else Project.objects
        if self.request.user.is_staff:
            return base.all()
        return base.filter(
            team__is_active=True,
            team__members__user=self.request.user,
            team__members__is_active=True,
        ).distinct()

    def get_queryset(self):
        """
        Enforce strict tenant isolation: only return projects
        belonging to teams the user is an active member of.

        Annotations are computed carefully to avoid the Cartesian product
        problem that arises from multiple COUNT joins on the same queryset.
        success_count uses a correlated Subquery instead of a joined COUNT
        to keep the SQL clean and fast.

        NOTE: the heavy annotation is skipped for analytics/trend/reliability
        actions via get_object() override — those actions only need the project pk.
        """
        # Use all_objects if the action is 'restore' to allow finding deleted records
        base_qs = (
            Project.all_objects if getattr(self, "action", None) == "restore" else Project.objects
        )

        critical_incidents = Incident.objects.filter(
            project=OuterRef("pk"),
            status__in=["OPEN", "ACKNOWLEDGED"],
            severity="CRITICAL",
        ).filter(Q(job__isnull=True) | Q(job__is_deleted=False))

        # Use a correlated subquery for success_count to avoid COUNT join
        # conflicts (which produce inflated numbers when multiple COUNT
        # annotations are combined on a single queryset with JOINs).
        success_subquery = (
            Execution.objects.filter(
                job__project=OuterRef("pk"),
                job__is_deleted=False,
                status="success",
            )
            .order_by()
            .values("job__project")
            .annotate(cnt=Count("id"))
            .values("cnt")
        )

        base_qs = base_qs.select_related("team").annotate(
            jobs_count=Count("jobs", filter=Q(jobs__is_deleted=False), distinct=True),
            executions_count=Count(
                "jobs__executions", filter=Q(jobs__is_deleted=False), distinct=True
            ),
            success_count=Coalesce(
                Subquery(success_subquery, output_field=IntegerField()), 0
            ),
            active_incidents_count=Count(
                "incidents",
                filter=Q(incidents__status__in=["OPEN", "ACKNOWLEDGED"])
                & (Q(incidents__job__isnull=True) | Q(incidents__job__is_deleted=False)),
                distinct=True,
            ),
            has_critical_incident=Exists(critical_incidents),
        )

        if self.request.user.is_staff:
            return base_qs.all()

        qs = base_qs.filter(
            team__is_active=True,
            team__members__user=self.request.user,
            team__members__is_active=True,
        ).distinct()
        return qs

    def get_object(self):
        """
        Use a lightweight queryset (no annotations) for detail actions that
        don't render project KPI cards — only need pk for their own queries.
        """
        lightweight_actions = {"analytics", "analytics_trend", "reliability_report"}
        if getattr(self, "action", None) in lightweight_actions:
            # Temporarily swap the queryset to avoid heavy annotation overhead.
            original_get_queryset = self.get_queryset
            self.get_queryset = self._get_base_tenant_qs  # type: ignore[method-assign]
            try:
                return super().get_object()
            finally:
                self.get_queryset = original_get_queryset  # type: ignore[method-assign]
        return super().get_object()

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """
        Restore a soft-deleted project.
        """
        # The view's get_queryset() will use all_objects due to action == 'restore'
        project = self.get_object()

        if not project.is_deleted:
            return Response(
                {"error": "Project is not deleted."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Validate that no active project has taken this name
        if Project.objects.filter(team=project.team, name=project.name).exists():
            return Response(
                {
                    "name": "Cannot restore: an active project with this name already exists in this team."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        project.restore(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """
        Get analytics for a specific Project.
        """
        project = self.get_object()
        start, end, _, filters = parse_analytics_query(request)

        qs = Execution.objects.filter(**filters) if filters else None
        metrics = get_project_analytics(project.id, start, end, base_qs=qs)

        serializer = ProjectAnalyticsSerializer(metrics)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="analytics/trend")
    def analytics_trend(self, request, pk=None):
        """
        Get time-bucketed trend analytics for a specific Project.
        """
        project = self.get_object()
        start, end, bucket_type, filters = parse_analytics_query(request)

        qs = Execution.objects.filter(job__project_id=project.id, **filters)

        trend_data = get_trend(qs, start, end, bucket_type)
        serializer = TrendResponseSerializer(trend_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="reliability-report")
    def reliability_report(self, request, pk=None):
        """
        Get MTTR and MTBF metrics for a specific Project.
        """
        from apps.incidents.services import get_reliability_report

        project = self.get_object()
        start, end, _, _ = parse_analytics_query(request)

        if not start or not end:
            return Response(
                {"error": "start and end parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report = get_reliability_report(project.id, start, end)
        return Response(report, status=status.HTTP_200_OK)


class APIKeyViewSet(CustomBaseViewSet):
    """
    API endpoints for managing API Keys scoped to a specific Project.
    """

    permission_classes = list(CustomBaseViewSet.permission_classes) + [APIKeyPermission]  # type: ignore[operator, list-item]
    http_method_names = ["get", "post"]  # Only CREATE, LIST, GET, plus custom actions
    search_fields = ["name", "key_prefix"]
    ordering_fields = ["name", "created_at", "revoked_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return APIKeyCreateSerializer
        return APIKeySerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if hasattr(self.request, "_project"):
            context["project"] = self.request._project
        return context

    def get_queryset(self):
        """
        Tenant isolation: The project ID is validated in APIKeyPermission.
        We simply return the keys for the project_pk.
        """
        project_id = self.kwargs.get("project_pk")
        # Ensure we only return keys for active projects (validated in permission).
        return APIKey.objects.filter(project_id=project_id)

    @action(detail=True, methods=["post"])
    def revoke(self, request, project_pk=None, pk=None):
        """
        Revoke an API key.
        Once revoked, it cannot be un-revoked.
        """
        key = self.get_object()

        if key.is_revoked:
            return Response(
                {"detail": "API key is already revoked."}, status=status.HTTP_400_BAD_REQUEST
            )

        key.revoked_at = timezone.now()
        key.revoked_by = request.user
        key.save(update_fields=["revoked_at", "revoked_by"])

        serializer = self.get_serializer(key)
        return Response(serializer.data, status=status.HTTP_200_OK)
