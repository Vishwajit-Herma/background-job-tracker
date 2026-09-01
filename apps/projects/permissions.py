from rest_framework.permissions import BasePermission

from apps.teams.models import TeamMember
from .models import Project


class ProjectPermission(BasePermission):
    """
    Custom permission for Projects:
    - Staff users and superusers always have full access.
    - Must be an active member of the Team to read/create/update.
    - Must be a Team admin or owner to delete.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_staff or request.user.is_superuser:
            return True

        if request.method == "POST":
            if not isinstance(request.data, dict):
                return False

            team_id = request.data.get("team")
            if not team_id:
                return True

            try:
                return TeamMember.objects.filter(
                    team_id=team_id,
                    team__is_active=True,
                    user=request.user,
                    is_active=True,
                    role__in=["admin", "owner"],
                ).exists()
            except ValueError, TypeError:
                return False

        return True

    def has_object_permission(self, request, view, obj):
        if request.user and (request.user.is_staff or request.user.is_superuser):
            return True

        member = TeamMember.objects.filter(team=obj.team, user=request.user, is_active=True).first()

        if not member:
            return False

        if (
            request.method in ["PUT", "PATCH", "DELETE"]
            or getattr(view, "action", None) == "restore"
        ):
            return member.is_admin()

        return request.method in ["GET", "HEAD", "OPTIONS"]


class APIKeyPermission(BasePermission):
    """
    Custom permission for API Keys:
    - Staff users and superusers always have full access.
    - User must be a Team Admin or Owner to perform any action (create, list, detail, revoke).
    - Regular members have NO access (403 Forbidden).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        project_id = view.kwargs.get("project_pk")
        if not project_id:
            return False

        if request.user.is_staff or request.user.is_superuser:
            project = Project.objects.filter(id=project_id, is_deleted=False).first()
            if project:
                request._project = project
                return True
            return False

        try:
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

            request._project = project
            return True
        except ValueError, TypeError:
            return False

    def has_object_permission(self, request, view, obj):
        if request.user and (request.user.is_staff or request.user.is_superuser):
            return True
        return obj.project_id == int(view.kwargs.get("project_pk"))
