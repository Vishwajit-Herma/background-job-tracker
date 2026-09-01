"""URL routing for AI Reliability Assistant."""

from django.urls import path
from . import views

app_name = "ai"

urlpatterns = [
    path(
        "<int:incident_id>/ai/investigate/",
        views.IncidentAIInvestigateView.as_view(),
        name="incident-ai-investigate",
    ),
]
