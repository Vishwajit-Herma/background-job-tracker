from rest_framework.routers import DefaultRouter
from .views import (
    NotificationChannelViewSet,
    NotificationPolicyViewSet,
    InAppNotificationViewSet,
)

app_name = "notifications"

router = DefaultRouter()
router.register(r"channels", NotificationChannelViewSet, basename="channel")
router.register(r"policies", NotificationPolicyViewSet, basename="policy")
router.register(r"in-app", InAppNotificationViewSet, basename="inapp")

urlpatterns = router.urls
