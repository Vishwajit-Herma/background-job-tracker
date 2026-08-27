from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.reliability.views import (
    ReliabilityFindingViewSet,
    JobReliabilityViewSet,
    ProjectReliabilityViewSet,
)

app_name = "reliability"

router = DefaultRouter()
router.register(r"findings", ReliabilityFindingViewSet, basename="reliability-findings")
router.register(r"jobs", JobReliabilityViewSet, basename="job-reliability")
router.register(r"projects", ProjectReliabilityViewSet, basename="project-reliability")

urlpatterns = [
    path("", include(router.urls)),
]
