from rest_framework.routers import DefaultRouter
from . import views

app_name = "alerts"

router = DefaultRouter()

router.register(r"rules", views.AlertRuleViewSet, basename="alert-rules")

urlpatterns = router.urls
