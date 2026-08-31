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

        if action in [
            "execute_runbook",
            "transition_step",
            "runbook_execution_status",
            "postmortem",
            "postmortem_submit_review",
        ]:
            # All active members can execute runbooks, edit postmortem drafts, and submit for review
            return True

        if action == "postmortem_complete":
            # Only Team Admins/Owners can complete and finalize postmortem reviews
            return member.is_admin()

        if action == "postmortem_action_items":
            # Team Admin/Owner: create action items (POST); Active Team Members: view (GET)
            if request.method == "POST":
                return member.is_admin()
            return True

        if action == "postmortem_action_item_detail":
            # Team Admin/Owner: delete action items (DELETE); Admins or Assigned Owner: update (PATCH)
            if request.method == "DELETE":
                return member.is_admin()
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


class RunbookPermission(BasePermission):
    """
    Custom permissions for Runbooks.
    Project Owner/Admin -> create/update/delete
    Project Members -> view/use
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # If it's a create request, we need to check if the user is an admin for the provided project
        if request.method == "POST" and view.action == "create":
            project_id = request.data.get("project")
            if not project_id:
                return False
            member = TeamMember.objects.filter(
                team__projects__id=project_id, user=request.user, is_active=True
            ).first()
            if not member or not member.is_admin():
                return False

        return True

    def has_object_permission(self, request, view, obj):
        member = TeamMember.objects.filter(
            team=obj.project.team, user=request.user, is_active=True
        ).first()

        if not member:
            return False

        if request.method in ["PUT", "PATCH", "DELETE"]:
            # Only Team Admins/Owners can edit/delete runbooks
            return member.is_admin()

        # Members can view/use (e.g. GET, POST to an execute action if any)
        return True
