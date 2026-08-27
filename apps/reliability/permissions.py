from rest_framework.permissions import BasePermission
from apps.projects.models import Project
from apps.teams.models import TeamMember


class ReliabilityPermission(BasePermission):
    """
    Authoritative custom permission for all Reliability endpoints:
    - Must be an active member of the Project's Team to read (GET/HEAD/OPTIONS).
    - Must be a Team Admin or Owner to modify (PUT/PATCH/DELETE/POST).
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True

        project = None
        if isinstance(obj, Project):
            project = obj
        elif hasattr(obj, "project") and obj.project is not None:
            project = obj.project
        elif hasattr(obj, "job") and obj.job is not None:
            project = obj.job.project

        if not project:
            return False

        member = TeamMember.objects.filter(
            team=project.team, user=request.user, is_active=True
        ).first()

        if not member:
            return False

        if request.method in ["PUT", "PATCH", "DELETE", "POST"]:
            return member.is_admin()

        return request.method in ["GET", "HEAD", "OPTIONS"]
