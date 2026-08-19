from rest_framework.permissions import BasePermission

from apps.teams.models import TeamMember


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

        # For CREATE actions, validate that the user is a member of the requested team.
        if request.method == "POST":
            # request.data can be a list if the user sends a JSON array.
            if not isinstance(request.data, dict):
                return False  # We do not support bulk creation natively, reject safely.

            team_id = request.data.get("team")
            if not team_id:
                return True

            try:
                # User must be an active member of the requested team, and team must be active
                return TeamMember.objects.filter(
                    team_id=team_id, team__is_active=True, user=request.user, is_active=True
                ).exists()
            except ValueError, TypeError:
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

        # Only Admins and Owners can delete or restore
        if request.method == "DELETE" or getattr(view, "action", None) == "restore":
            return member.is_admin()

        # All active members can read/update
        return True
