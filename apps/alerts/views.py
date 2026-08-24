from rest_framework.permissions import IsAuthenticated
from apps.config_management.views import CustomBaseViewSet

from .models import AlertRule
from .serializers import AlertRuleSerializer
from .permissions import AlertRulePermission


class AlertRuleViewSet(CustomBaseViewSet):
    """
    API endpoints for managing AlertRules.
    """

    serializer_class = AlertRuleSerializer
    permission_classes = [IsAuthenticated, AlertRulePermission]

    def get_queryset(self):
        """
        Filter alert rules to those belonging to teams where the user is an active member.
        """
        if not self.request.user.is_authenticated:
            return AlertRule.objects.none()

        return AlertRule.objects.filter(
            project__team__members__user=self.request.user,
            project__team__members__is_active=True,
            project__is_deleted=False,
        ).distinct()
