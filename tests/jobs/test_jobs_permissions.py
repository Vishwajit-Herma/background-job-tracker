import pytest
from rest_framework import status
from django.urls import reverse

from apps.projects.models import Project
from apps.jobs.models import Job
from apps.teams.models import Team
from apps.users.models import User


@pytest.fixture
def user1(db):
    return User.objects.create(email="user1@example.com", password="password")


@pytest.fixture
def user2(db):
    return User.objects.create(email="user2@example.com", password="password")


@pytest.fixture
def team1(user1):
    return Team.objects.create(name="Team 1", slug="team-1", owner=user1)


@pytest.fixture
def team2(user2):
    return Team.objects.create(name="Team 2", slug="team-2", owner=user2)


@pytest.fixture
def project1(team1):
    return Project.objects.create(team=team1, name="Project 1")


@pytest.fixture
def project2(team2):
    return Project.objects.create(team=team2, name="Project 2")


@pytest.mark.django_db
class TestJobsPermissions:
    def test_tenant_isolation_list(self, api_client, user1, user2, project1, project2):
        Job.objects.create(project=project1, name="Job A", task_identifier="tasks.a")
        Job.objects.create(project=project2, name="Job B", task_identifier="tasks.b")

        # User A should only see Job A
        api_client.force_authenticate(user=user1)
        response = api_client.get(reverse("api:jobs:job-list"))
        assert response.status_code == status.HTTP_200_OK
        data = response.data.get("data", response.data.get("results", []))
        assert len(data) == 1
        assert data[0]["name"] == "Job A"

        # User B should only see Job B
        api_client.force_authenticate(user=user2)
        response = api_client.get(reverse("api:jobs:job-list"))
        assert response.status_code == status.HTTP_200_OK
        data = response.data.get("data", response.data.get("results", []))
        assert len(data) == 1
        assert data[0]["name"] == "Job B"

    def test_tenant_isolation_retrieve(self, api_client, user2, project1):
        job_a = Job.objects.create(project=project1, name="Job A", task_identifier="tasks.a")

        api_client.force_authenticate(user=user2)
        url = reverse("api:jobs:job-detail", kwargs={"pk": job_a.id})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_rbac_member_cannot_create(self, api_client, user1, user2, team1, project1):
        team1.add_user(user2, role="member")

        api_client.force_authenticate(user=user2)
        url = reverse("api:jobs:job-list")
        data = {"project": project1.id, "name": "New Job", "task_identifier": "tasks.new"}

        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_rbac_member_cannot_update_or_delete(self, api_client, user2, team1, project1):
        team1.add_user(user2, role="member")
        job = Job.objects.create(project=project1, name="Job", task_identifier="tasks.j")

        api_client.force_authenticate(user=user2)
        url = reverse("api:jobs:job-detail", kwargs={"pk": job.id})

        response = api_client.patch(url, {"name": "Changed"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

        response = api_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
