from rest_framework.permissions import BasePermission
from apps.teams.models import TeamMember


class IncidentPermission(BasePermission):
    """
    Custom permissions for Incidents.
    Enforces Tenant Isolation and strict Action RBAC.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # No general POST create endpoint for incidents. Evaluator creates them.
        return not (request.method == "POST" and view.action == "create")

    def has_object_permission(self, request, view, obj):
        # Tenant isolation: User must be active member of incident's project's team
        member = TeamMember.objects.filter(
            team=obj.project.team, user=request.user, is_active=True
        ).first()

        if not member:
            return False

        action = getattr(view, "action", None)

        if action in ["assign", "reopen"]:
            # Only Team Admins/Owners
            return member.is_admin()

        if action in ["acknowledge", "resolve"]:
            # Only Assignee OR Team Admin/Owner
            is_assignee = bool(obj.assigned_to_id and obj.assigned_to_id == member.id)
            return is_assignee or member.is_admin()

        if action == "notes":
            # All active members can view/add notes
            return True

        if action == "events":
            # All active members can view timeline
            return True

        # For standard retrieve/list
        return request.method in ["GET", "HEAD", "OPTIONS"]


class IncidentNotePermission(BasePermission):
    """
    Strict immutability for notes.
    """

    def has_object_permission(self, request, view, obj):
        # Prevent edit/delete
        return request.method not in ["PUT", "PATCH", "DELETE"]
