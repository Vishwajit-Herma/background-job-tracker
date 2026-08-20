from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet, APIKeyViewSet

app_name = "projects"

router = DefaultRouter()
router.register(r"", ProjectViewSet, basename="project")

api_key_list = APIKeyViewSet.as_view({"get": "list", "post": "create"})
api_key_detail = APIKeyViewSet.as_view({"get": "retrieve"})
api_key_revoke = APIKeyViewSet.as_view({"post": "revoke"})

urlpatterns = [
    path("<int:project_pk>/keys/", api_key_list, name="apikey-list"),
    path("<int:project_pk>/keys/<int:pk>/", api_key_detail, name="apikey-detail"),
    path("<int:project_pk>/keys/<int:pk>/revoke/", api_key_revoke, name="apikey-revoke"),
    path("", include(router.urls)),
]
