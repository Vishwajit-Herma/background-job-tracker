"""API URLs."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


router = DefaultRouter()
# Register your viewsets here
# router.register(r'items', views.ItemViewSet)

app_name = "api"

urlpatterns = [
    # OpenAPI schema
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
    path("schema/swagger/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="swagger"),
    path("schema/redoc/", SpectacularRedocView.as_view(url_name="api:schema"), name="redoc"),
    path("projects/", include("apps.projects.urls")),
    path("", include(router.urls)),
]
