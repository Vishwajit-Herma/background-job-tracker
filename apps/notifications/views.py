from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

from apps.teams.models import TeamMember
from apps.config_management.views import CustomBaseViewSet, BaseViewSetConfig
from apps.config_management.responses import CustomResponseMixin
from .models import NotificationChannel, NotificationPolicy, InAppNotification
from .serializers import (
    NotificationChannelSerializer,
    NotificationPolicySerializer,
    InAppNotificationSerializer,
)


class NotificationChannelViewSet(CustomBaseViewSet):
    """
    API endpoint that allows notification channels to be viewed or edited.
    Requires TeamAdmin or TeamOwner role for write operations.
    """

    serializer_class = NotificationChannelSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "type", "is_active"]
    search_fields = ["name", "project__name"]
    ordering_fields = ["name", "created_at", "updated_at"]

    def get_queryset(self):
        if self.request.user.is_staff:
            return NotificationChannel.objects.all()
        return NotificationChannel.objects.filter(
            project__team__members__user=self.request.user, project__team__members__is_active=True
        ).distinct()

    def check_admin_or_owner(self, project):
        if self.request.user.is_staff:
            return
        member = TeamMember.objects.filter(
            team_id=project.team_id, user=self.request.user, is_active=True
        ).first()
        if not member or not member.is_admin():
            self.permission_denied(
                self.request, message="Only team admins or owners can manage notification channels."
            )

    def perform_create(self, serializer):
        self.check_admin_or_owner(serializer.validated_data["project"])
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self.check_admin_or_owner(serializer.instance.project)
        # Handle secret masking logic. If the payload has secret='********', we ignore it.
        if (
            "config" in serializer.validated_data
            and serializer.instance.type == NotificationChannel.ChannelType.WEBHOOK
        ):
            config = serializer.validated_data["config"]
            if config.get("secret") == "********":
                config["secret"] = serializer.instance.config.get("secret")
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self.check_admin_or_owner(instance.project)
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


class NotificationPolicyViewSet(CustomBaseViewSet):
    """
    API endpoint that allows notification policies to be viewed or edited.
    Requires TeamAdmin or TeamOwner role for write operations.
    """

    serializer_class = NotificationPolicySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["project", "channel", "is_active"]
    search_fields = ["name", "project__name", "channel__name"]
    ordering_fields = ["name", "created_at", "updated_at"]

    def get_queryset(self):
        if self.request.user.is_staff:
            return NotificationPolicy.objects.all()
        return NotificationPolicy.objects.filter(
            project__team__members__user=self.request.user, project__team__members__is_active=True
        ).distinct()

    def check_admin_or_owner(self, project):
        if self.request.user.is_staff:
            return
        member = TeamMember.objects.filter(
            team_id=project.team_id, user=self.request.user, is_active=True
        ).first()
        if not member or not member.is_admin():
            self.permission_denied(
                self.request, message="Only team admins or owners can manage notification policies."
            )

    def perform_create(self, serializer):
        self.check_admin_or_owner(serializer.validated_data["project"])
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self.check_admin_or_owner(serializer.instance.project)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self.check_admin_or_owner(instance.project)
        super().perform_destroy(instance)


class InAppNotificationViewSet(
    BaseViewSetConfig, CustomResponseMixin, viewsets.ReadOnlyModelViewSet
):
    """
    API endpoint for viewing and managing in-app notifications for the logged-in user.
    """

    serializer_class = InAppNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["is_read"]
    search_fields = ["title", "message"]
    ordering_fields = ["created_at", "read_at"]

    def get_queryset(self):
        return InAppNotification.objects.filter(recipient=self.request.user)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        """
        Returns the count of unread notifications for the user.
        """
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread_count": count})

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        """
        Marks a specific notification as read.
        """
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
        return Response({"message": "Notification marked as read"})

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        """
        Marks all unread notifications for the user as read.
        """
        self.get_queryset().filter(is_read=False).update(is_read=True, read_at=timezone.now())
        return Response({"message": "All notifications marked as read"})
