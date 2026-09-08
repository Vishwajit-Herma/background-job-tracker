from rest_framework.permissions import IsAuthenticated
from apps.config_management.views import CustomBaseViewSet
from apps.core.realtime import publish_realtime_event

from .models import AlertRule
from .serializers import AlertRuleSerializer
from .permissions import AlertRulePermission


class AlertRuleViewSet(CustomBaseViewSet):
    """
    API endpoints for managing AlertRules.
    """

    serializer_class = AlertRuleSerializer
    permission_classes = [IsAuthenticated, AlertRulePermission]
    filterset_fields = ["project", "job", "metric", "severity", "is_active"]
    search_fields = ["project__name", "job__name"]
    ordering_fields = ["created_at", "updated_at", "severity", "metric"]

    def get_queryset(self):
        """
        Filter alert rules to those belonging to teams where the user is an active member.
        """
        if not self.request.user.is_authenticated:
            return AlertRule.objects.none()

        return (
            AlertRule.objects.filter(
                project__team__members__user=self.request.user,
                project__team__members__is_active=True,
                project__is_deleted=False,
            )
            .select_related("project", "job")
            .distinct()
        )

    def perform_create(self, serializer):
        super().perform_create(serializer)
        rule = serializer.instance
        publish_realtime_event(
            "alert_rule.updated",
            project_id=rule.project_id,
            payload={"rule_id": rule.id, "action": "created"},
        )

    def perform_update(self, serializer):
        super().perform_update(serializer)
        rule = serializer.instance
        publish_realtime_event(
            "alert_rule.updated",
            project_id=rule.project_id,
            payload={"rule_id": rule.id, "action": "updated"},
        )

    def perform_destroy(self, instance):
        project_id = instance.project_id
        rule_id = instance.id
        super().perform_destroy(instance)
        publish_realtime_event(
            "alert_rule.updated",
            project_id=project_id,
            payload={"rule_id": rule_id, "action": "deleted"},
        )
