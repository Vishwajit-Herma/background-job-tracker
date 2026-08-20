from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ExecutionViewSet, IngestionViewSet

app_name = "executions"

router = DefaultRouter()
router.register(r"executions", ExecutionViewSet, basename="execution")
router.register(r"ingestion/executions", IngestionViewSet, basename="ingestion")

urlpatterns = [
    path("", include(router.urls)),
]
