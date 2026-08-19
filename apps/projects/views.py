from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.config_management.views import CustomBaseViewSet
from .models import Project
from .serializers import ProjectSerializer
from .permissions import ProjectPermission


class ProjectViewSet(CustomBaseViewSet):
    """
    API endpoints for managing Projects.
    """

    serializer_class = ProjectSerializer
    permission_classes = CustomBaseViewSet.permission_classes + [ProjectPermission]
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

        serializer = self.get_serializer(project)
        return Response(serializer.data, status=status.HTTP_200_OK)
