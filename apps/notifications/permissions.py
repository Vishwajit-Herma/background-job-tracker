from rest_framework import permissions


class IsTeamAdminOrOwner(permissions.BasePermission):
    """
    Allows access only to team admins or owners of the project.
    Expects the view to filter querysets correctly; this just checks object level.
    """

    def has_object_permission(self, request, view, obj):
        team_id = obj.project.team_id

        # Avoid circular imports or complex lookups if possible, but we can query TeamMember
        from apps.teams.models import TeamMember

        member = TeamMember.objects.filter(
            team_id=team_id, user=request.user, is_active=True
        ).first()

        if not member:
            return False

        return member.role in [TeamMember.Role.OWNER, TeamMember.Role.ADMIN]


class IsNotificationRecipient(permissions.BasePermission):
    """
    Allows access only to the recipient of the notification.
    """

    def has_object_permission(self, request, view, obj):
        return obj.recipient_id == request.user.id
