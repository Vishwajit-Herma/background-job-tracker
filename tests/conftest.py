"""Pytest configuration and fixtures."""

import os
import pytest
from allauth.account.models import EmailAddress
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.cache import cache
from django.test import Client, RequestFactory
from rest_framework.test import APIClient

from apps.teams.models import Team, TeamInvitation, TeamMember
from apps.users.models import User


def pytest_load_initial_conftests(args, early_config, parser):
    """Override database to use in-memory SQLite for tests."""
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


class MessagesRequestFactory(RequestFactory):
    """RequestFactory whose requests support sessions and messages."""

    def request(self, **kwargs):
        request = super().request(**kwargs)
        request.session = {}
        request._messages = FallbackStorage(request)
        return request


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure in-memory cache is cleared between tests."""
    cache.clear()


@pytest.fixture
def rf():
    """Request factory with session and messages support."""
    return MessagesRequestFactory()


@pytest.fixture
def client():
    """Django test client."""
    return Client()


@pytest.fixture
def api_client():
    """DRF API client."""
    return APIClient()


@pytest.fixture
def authenticated_api_client(api_client, user):
    """API client authenticated with a regular user."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_api_client(api_client, admin_user):
    """API client authenticated with an admin user."""
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com", password="testpass123", first_name="Test", last_name="User"
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_superuser(email="admin@example.com", password="adminpass123")


@pytest.fixture
def multiple_users(db):
    """Create multiple test users."""
    users = []
    for i in range(3):
        user = User.objects.create_user(
            email=f"user{i}@example.com",
            password="testpass123",
            first_name=f"User{i}",
            last_name="Test",
        )
        users.append(user)
    return users


@pytest.fixture
def verified_user(db):
    """Create a verified user with email confirmation."""
    user = User.objects.create_user(email="verified@example.com", password="testpass123")
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    return user


@pytest.fixture
def staff_user(db):
    """Create a staff user."""
    return User.objects.create_user(
        email="staff@example.com", password="testpass123", is_staff=True
    )


@pytest.fixture
def team(db, user):
    """Create a test team with owner membership."""
    # Owner membership is created automatically by the post_save signal
    team = Team.objects.create(
        name="Test Team", slug="test-team", owner=user, description="A test team"
    )

    return team


@pytest.fixture
def team_member(db, team):
    """Create a team member."""
    member_user = User.objects.create_user(email="member@example.com", password="testpass123")

    return TeamMember.objects.create(team=team, user=member_user, role="member")


@pytest.fixture
def team_invitation(db, team, user):
    """Create a team invitation."""
    return TeamInvitation.objects.create(
        team=team, email="invitee@example.com", role="member", invited_by=user
    )
