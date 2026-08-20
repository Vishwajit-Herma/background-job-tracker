from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.config_management.views import CustomBaseViewSet
from apps.projects.models import Project
from .models import Job
from .serializers import (
    JobSerializer,
    JobCreateSerializer,
    JobUpdateSerializer,
    TaskRegistrySyncSerializer,
)
from .permissions import JobPermission, TaskRegistryPermission
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
        """
        base_qs = Job.all_objects if getattr(self, "action", None) == "restore" else Job.objects

        qs = base_qs.select_related("project", "created_by", "modified_by").filter(
            project__is_deleted=False,
            project__team__is_active=True,
            project__team__members__user=self.request.user,
            project__team__members__is_active=True,
        )
        return qs

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
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], permission_classes=[TaskRegistryPermission])
    def sync(self, request):
        """
        SDK ingestion endpoint to synchronize discovered task identifiers.
        Expects a body like {"project": 1, "tasks": ["task1", "task2"]}
        """
        # For this milestone, we expect project ID in the body and validate it via permission classes.
        # In the future, the Project ID will be implicitly derived from the API Key authentication.
        project_id = request.data.get("project")
        if not project_id:
            return Response(
                {"project": "This field is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        # We pass kwargs to the view to allow the permission class to access the project ID
        self.kwargs["project_pk"] = project_id

        # Check permission explicitly since this is a list action that manually passes context
        for permission in self.get_permissions():
            if not permission.has_permission(request, self):
                self.permission_denied(request)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            project = Project.objects.get(id=project_id, is_deleted=False)
        except Project.DoesNotExist:
            return Response(
                {"project": "Invalid or deleted project."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Execute discovery service logic
        sync_task_registry(project, serializer.validated_data["tasks"])

        return Response({"status": "synchronized"}, status=status.HTTP_200_OK)
