from rest_framework.permissions import BasePermission

from apps.teams.models import TeamMember
from .models import Project


class ProjectPermission(BasePermission):
    """
    Custom permission for Projects:
    - Must be an active member of the Team to read/create/update.
    - Must be a Team admin or owner to delete.
    """

    def has_permission(self, request, view):
        # General authentication is handled by IsAuthenticated in the ViewSet.
        if not request.user or not request.user.is_authenticated:
            return False

        # For CREATE actions, validate that the user is a Admin/Owner of the requested team.
        if request.method == "POST":
            # request.data can be a list if the user sends a JSON array.
            if not isinstance(request.data, dict):
                return False  # We do not support bulk creation natively, reject safely.

            team_id = request.data.get("team")
            if not team_id:
                return True

            try:
                # User must be an active Admin/Owner of the requested team, and team must be active
                return TeamMember.objects.filter(
                    team_id=team_id,
                    team__is_active=True,
                    user=request.user,
                    is_active=True,
                    role__in=["admin", "owner"],
                ).exists()
            except (ValueError, TypeError):
                # If they pass team="abc" or an object instead of an integer ID,
                # catch the error so DRF returns 403 instead of crashing with 500.
                return False

        # For LIST/GET actions, `get_queryset` handles tenant isolation.
        return True

    def has_object_permission(self, request, view, obj):
        # User must be an active member of the project's team
        member = TeamMember.objects.filter(team=obj.team, user=request.user, is_active=True).first()

        if not member:
            return False

        # Only Admins and Owners can update, delete or restore
        if (
            request.method in ["PUT", "PATCH", "DELETE"]
            or getattr(view, "action", None) == "restore"
        ):
            return member.is_admin()

        # All active members can read
        return request.method in ["GET", "HEAD", "OPTIONS"]


class APIKeyPermission(BasePermission):
    """
    Custom permission for API Keys:
    - User must be a Team Admin or Owner to perform any action (create, list, detail, revoke).
    - Regular members have NO access (403 Forbidden).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # The project_id comes from the URL. We can access it from view.kwargs.
        project_id = view.kwargs.get("project_pk")
        if not project_id:
            return False

        try:
            # User must be an Admin/Owner of the team that owns this project.
            # And the project itself must be active.

            project = Project.objects.filter(
                id=project_id,
                is_deleted=False,
                team__is_active=True,
                team__members__user=request.user,
                team__members__is_active=True,
                team__members__role__in=["admin", "owner"],
            ).first()

            if not project:
                return False

            # Attach the project to the view so we can use it in create/etc. without fetching again.
            request._project = project
            return True
        except (ValueError, TypeError):
            return False

    def has_object_permission(self, request, view, obj):
        # We've already validated project-level admin access in has_permission.
        # Ensure the key belongs to the right project.
        return obj.project_id == int(view.kwargs.get("project_pk"))
