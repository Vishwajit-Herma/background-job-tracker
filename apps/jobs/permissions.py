from rest_framework.permissions import BasePermission
from apps.teams.models import TeamMember
from apps.projects.models import Project


class JobPermission(BasePermission):
    """
    Custom permission for Jobs:
    - Must be an active member of the Project's Team to read/list.
    - Must be a Team admin or owner to create/update/delete/restore.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # For CREATE actions, validate that the user is an Admin/Owner of the requested project's team.
        if request.method == "POST" and getattr(view, "action", None) != "restore":
            if not isinstance(request.data, dict):
                return False

            project_id = request.data.get("project")
            if not project_id:
                return True  # Handled by serializer validation if missing

            try:
                project = Project.objects.get(id=project_id)
                return TeamMember.objects.filter(
                    team=project.team,
                    team__is_active=True,
                    user=request.user,
                    is_active=True,
                    role__in=["admin", "owner"],
                ).exists()
            except Project.DoesNotExist, ValueError, TypeError:
                return False

        return True

    def has_object_permission(self, request, view, obj):
        # User must be an active member of the project's team
        member = TeamMember.objects.filter(
            team=obj.project.team, user=request.user, is_active=True
        ).first()

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
