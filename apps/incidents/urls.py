from rest_framework.routers import DefaultRouter
from . import views

app_name = "incidents"

router = DefaultRouter()

router.register(r"", views.IncidentViewSet, basename="incidents")

urlpatterns = router.urls
