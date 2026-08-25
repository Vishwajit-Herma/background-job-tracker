from django.urls import path, include
from rest_framework_nested import routers

from . import views

app_name = "teams_api"

router = routers.SimpleRouter()
router.register(r"my-invitations", views.MyInvitationsViewSet, basename="my-invitations")
router.register(r"", views.TeamViewSet, basename="team")

# Nested router for team members and invitations
teams_router = routers.NestedSimpleRouter(router, r"", lookup="team")
teams_router.register(r"members", views.TeamMemberViewSet, basename="team-members")
teams_router.register(r"invitations", views.TeamInvitationViewSet, basename="team-invitations")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(teams_router.urls)),
]
