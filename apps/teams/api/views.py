from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, permissions, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError

from django.contrib.auth import get_user_model
from apps.teams.models import Team, TeamMember, TeamInvitation
from .serializers import (
    TeamSerializer, 
    TeamMemberSerializer,
    TeamMemberUpdateSerializer,
    TeamInvitationSerializer
)

User = get_user_model()


class TeamViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Teams.
    Enforces tenant isolation: users can only view/modify teams they belong to,
    unless they are staff.
    """
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return all active teams for staff, otherwise only teams the user is a member of."""
        if self.request.user.is_staff:
            return Team.objects.filter(is_active=True).distinct()
            
        return Team.objects.filter(
            members__user=self.request.user,
            members__is_active=True,
            is_active=True,
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_destroy(self, instance):
        if instance.owner != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("Only the team owner or a staff member can delete the team.")
        instance.is_active = False
        instance.save()


class TeamMemberViewSet(viewsets.ModelViewSet):
    """
    ViewSet for listing and managing team members.
    """
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "delete"]

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            return TeamMemberUpdateSerializer
        return TeamMemberSerializer

    def get_queryset(self):
        team_id = self.kwargs.get("team_pk")
        
        if self.request.user.is_staff:
            return TeamMember.objects.filter(team_id=team_id, is_active=True).select_related("user")
            
        # Verify the current user is a member of this team
        if not TeamMember.objects.filter(team_id=team_id, user=self.request.user, is_active=True).exists():
            return TeamMember.objects.none()
            
        return TeamMember.objects.filter(team_id=team_id, is_active=True).select_related("user")

    def perform_destroy(self, instance):
        if instance.role == "owner" and not self.request.user.is_staff:
            raise ValidationError("Cannot remove the team owner.")
        if instance.user == self.request.user:
            # Users can remove themselves (leave team)
            pass
        else:
            # Verify current user is admin/owner or staff
            if not self.request.user.is_staff:
                current_member = TeamMember.objects.filter(team=instance.team, user=self.request.user, is_active=True).first()
                if not current_member or not current_member.can_manage_members():
                    raise PermissionDenied("You do not have permission to remove members.")
            
        instance.is_active = False
        instance.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        if not self.request.user.is_staff:
            current_member = TeamMember.objects.filter(team=instance.team, user=self.request.user, is_active=True).first()
            if not current_member or not current_member.can_manage_members():
                raise PermissionDenied("You do not have permission to update member roles.")
                
        if serializer.validated_data.get("role") == "owner" and not self.request.user.is_staff:
            current_member = TeamMember.objects.filter(team=instance.team, user=self.request.user, is_active=True).first()
            if not current_member or not current_member.is_owner():
                raise PermissionDenied("Only team owners can grant the owner role.")
                
        if instance.role == "owner" and serializer.validated_data.get("role") != "owner" and not self.request.user.is_staff:
            raise ValidationError("Cannot change the role of the team owner.")
        serializer.save()


class TeamInvitationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing team invitations.
    """
    serializer_class = TeamInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        team_id = self.kwargs.get("team_pk")
        if self.request.user.is_staff:
            return TeamInvitation.objects.filter(team_id=team_id, status="pending")
            
        if not TeamMember.objects.filter(team_id=team_id, user=self.request.user, is_active=True).exists():
            return TeamInvitation.objects.none()
        return TeamInvitation.objects.filter(team_id=team_id, status="pending")

    def perform_create(self, serializer):
        team_id = self.kwargs.get("team_pk")
        email = serializer.validated_data.get("email")
        
        # Verify user has an account
        if not User.objects.filter(email=email).exists():
            raise ValidationError({"email": "User does not have an account. They must register first."})

        if not self.request.user.is_staff:
            current_member = TeamMember.objects.filter(team_id=team_id, user=self.request.user, is_active=True).first()
            if not current_member or not current_member.can_manage_members():
                raise PermissionDenied("You do not have permission to invite members.")
            if serializer.validated_data.get("role") == "owner" and not current_member.is_owner():
                raise PermissionDenied("Only team owners can invite other owners.")
            team = current_member.team
        else:
            team = Team.objects.get(id=team_id)
            
        if TeamMember.objects.filter(team=team, user__email=email, is_active=True).exists():
            raise ValidationError({"email": "User is already a member of this team."})
            
        if TeamInvitation.objects.filter(team=team, email=email, status="pending", expires_at__gt=timezone.now()).exists():
            raise ValidationError({"email": "A pending invitation already exists for this email."})
            
        invitation = serializer.save(team=team, invited_by=self.request.user)
        invitation.send_invitation_email()

    def perform_destroy(self, instance):
        if not self.request.user.is_staff:
            current_member = TeamMember.objects.filter(team=instance.team, user=self.request.user, is_active=True).first()
            if not current_member or not current_member.can_manage_members():
                raise PermissionDenied("You do not have permission to delete invitations.")
            
        instance.status = "declined"
        instance.save()


class MyInvitationsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    ViewSet for a user to see and interact with their pending invitations.
    """
    serializer_class = TeamInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return TeamInvitation.objects.filter(
            email=self.request.user.email, 
            status="pending",
            expires_at__gt=timezone.now()
        ).select_related("team")

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        invitation = self.get_object()
        if invitation.accept(request.user):
            return Response({"status": "accepted"})
        return Response({"error": "Failed to accept invitation"}, status=status.HTTP_400_BAD_REQUEST)
        
    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        invitation = self.get_object()
        invitation.decline()
        return Response({"status": "declined"})
