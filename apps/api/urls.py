"""API URLs."""

from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

app_name = "api"

urlpatterns = [
    # OpenAPI schema
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
    path("schema/swagger/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="swagger"),
    path("schema/redoc/", SpectacularRedocView.as_view(url_name="api:schema"), name="redoc"),
    path("projects/", include("apps.projects.urls")),
    path("jobs/", include("apps.jobs.urls")),
    path("alerts/", include("apps.alerts.urls")),
    path("incidents/", include("apps.incidents.urls")),
    path("", include("apps.executions.urls")),
]
