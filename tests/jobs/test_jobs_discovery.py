import pytest
from rest_framework import status
from django.urls import reverse

from apps.projects.models import Project
from apps.jobs.models import Job, TaskRegistry
from apps.jobs.services import sync_task_registry
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
def project1(team1):
    return Project.objects.create(team=team1, name="Project 1")


@pytest.mark.django_db
class TestJobsDiscovery:
    def test_sync_task_registry_creates_new_jobs(self, project1):
        tasks = ["tasks.send_email", "tasks.generate_report"]
        sync_task_registry(project1, tasks)

        assert TaskRegistry.objects.count() == 2
        assert Job.objects.count() == 2
        job1 = Job.objects.get(task_identifier="tasks.send_email")
        assert job1.name == "Send Email"
        assert job1.verification_status == Job.VerificationStatus.VERIFIED
        assert job1.status == Job.Status.ACTIVE

    def test_sync_task_registry_updates_unverified_jobs(self, project1):
        job = Job.objects.create(
            project=project1,
            name="Manual Job",
            task_identifier="tasks.manual",
            verification_status=Job.VerificationStatus.UNVERIFIED,
        )
        assert job.last_verified_at is None

        sync_task_registry(project1, ["tasks.manual"])

        job.refresh_from_db()
        assert job.verification_status == Job.VerificationStatus.VERIFIED
        assert job.last_verified_at is not None
        assert Job.objects.count() == 1

    def test_sync_api_endpoint(self, api_client, user1, project1):
        from apps.projects.models import APIKey

        api_key_obj, api_key_str = APIKey.create_key(project1, "test_key", user1)
        api_client.credentials(HTTP_X_API_KEY=api_key_str)

        url = reverse("api:jobs:job-sync")
        data = {"tasks": ["tasks.a", "tasks.b", "tasks.a"]}

        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK

        assert Job.objects.filter(project=project1).count() == 2
        assert TaskRegistry.objects.filter(project=project1).count() == 2

    def test_sync_api_endpoint_permission(self, api_client, user2, project1):
        url = reverse("api:jobs:job-sync")
        data = {"tasks": ["tasks.a"]}

        # Unauthenticated
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Authenticated but wrong key
        api_client.credentials(HTTP_X_API_KEY="sk_wrong_key")
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
