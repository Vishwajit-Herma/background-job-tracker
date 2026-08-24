from rest_framework.permissions import BasePermission
from apps.teams.models import TeamMember


class AlertRulePermission(BasePermission):
    """
    Custom permission for AlertRules:
    - Must be an active member of the Project's Team to read.
    - Must be a Team admin or owner to create/update/delete.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method == "POST":
            # For CREATE, user must be admin/owner of the project's team
            if not isinstance(request.data, dict):
                return False

            project_id = request.data.get("project")
            if not project_id:
                return False

            try:
                return TeamMember.objects.filter(
                    team__projects__id=project_id,
                    team__is_active=True,
                    user=request.user,
                    is_active=True,
                    role__in=["admin", "owner"],
                ).exists()
            except ValueError, TypeError:
                return False

        return True

    def has_object_permission(self, request, view, obj):
        # User must be an active member of the project's team
        member = TeamMember.objects.filter(
            team=obj.project.team, user=request.user, is_active=True
        ).first()

        if not member:
            return False

        # Only Admins and Owners can update, delete
        if request.method in ["PUT", "PATCH", "DELETE"]:
            return member.is_admin()

        # All active members can read
        return request.method in ["GET", "HEAD", "OPTIONS"]
