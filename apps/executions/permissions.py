from rest_framework.permissions import BasePermission

from apps.projects.models import Project
from apps.teams.models import TeamMember


class HasActiveProjectAPIKey(BasePermission):
    """
    Validates that the request has a valid and active Project in `request.auth`.
    Used by the ingestion endpoints.
    """

    def has_permission(self, request, view):
        project = request.auth
        if not isinstance(project, Project):
            return False

        if project.is_deleted:
            return False

        # If the project is inactive, we reject ingestion.
        # This will result in a 403 Forbidden.
        return project.status == Project.Status.ACTIVE


class ExecutionReadPermission(BasePermission):
    """
    Validates that a human user has read access to the Execution.
    The user must be an active member of the Team that owns the Project.
    """

    def has_permission(self, request, view):
        # Read-only permission. Execution creation is strictly via API Key ingestion.
        if request.method not in ["GET", "HEAD", "OPTIONS"]:
            return False

        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # User must be an active member of the project's team
        return TeamMember.objects.filter(
            team=obj.job.project.team, user=request.user, is_active=True
        ).exists()
