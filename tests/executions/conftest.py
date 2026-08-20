import pytest
from apps.users.models import User
from apps.teams.models import Team
from apps.projects.models import Project


@pytest.fixture
def user1(db):
    return User.objects.create(email="user1@example.com", password="password")


@pytest.fixture
def user2(db):
    return User.objects.create(email="user2@example.com", password="password")


@pytest.fixture
def team1(user1):
    # This also auto-creates the owner TeamMember for user1
    return Team.objects.create(name="Team 1", slug="team-1", owner=user1)


@pytest.fixture
def project1(team1):
    return Project.objects.create(team=team1, name="Project 1")
