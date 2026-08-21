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
from .models import APIKey, Project
from .permissions import APIKeyPermission, ProjectPermission
from .serializers import APIKeyCreateSerializer, APIKeySerializer, ProjectSerializer


class ProjectViewSet(CustomBaseViewSet):
    """
    API endpoints for managing Projects.
    """

    serializer_class = ProjectSerializer
    permission_classes = list(CustomBaseViewSet.permission_classes) + [ProjectPermission]  # type: ignore[operator, list-item]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]

    def get_queryset(self):
        """
        Enforce strict tenant isolation: only return projects
        belonging to teams the user is an active member of.
        """
        # Use all_objects if the action is 'restore' to allow finding deleted records
        base_qs = (
            Project.all_objects if getattr(self, "action", None) == "restore" else Project.objects
        )

        qs = base_qs.filter(
            team__is_active=True,
            team__members__user=self.request.user,
            team__members__is_active=True,
        )
        return qs

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
