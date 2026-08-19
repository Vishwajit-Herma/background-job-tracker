from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet

app_name = "projects"

router = DefaultRouter()
router.register(r"", ProjectViewSet, basename="project")

urlpatterns = router.urls
