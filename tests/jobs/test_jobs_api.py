import pytest
from rest_framework import status
from django.urls import reverse

from apps.projects.models import Project
from apps.jobs.models import Job, TaskRegistry
from apps.teams.models import Team
from apps.users.models import User


@pytest.fixture
def user1(db):
    return User.objects.create(email="user1@example.com", password="password")


@pytest.fixture
def team1(user1):
    return Team.objects.create(name="Team 1", slug="team-1", owner=user1)


@pytest.fixture
def project1(team1):
    return Project.objects.create(team=team1, name="Project 1")


@pytest.mark.django_db
class TestJobsAPI:
    def test_list_jobs(self, api_client, user1, project1):
        Job.objects.create(project=project1, name="Test Job 1", task_identifier="tasks.job1")
        Job.objects.create(project=project1, name="Test Job 2", task_identifier="tasks.job2")

        api_client.force_authenticate(user=user1)
        url = reverse("api:jobs:job-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get("data", response.data.get("results", []))) == 2

    def test_create_job_admin(self, api_client, user1, project1):
        api_client.force_authenticate(user=user1)
        url = reverse("api:jobs:job-list")

        data = {"project": project1.id, "name": "New Job", "task_identifier": "tasks.new"}

        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED

        # Depending on if they wrap in {"data": ...}
        resp_data = response.data.get("data", response.data)
        assert resp_data["name"] == "New Job"
        assert resp_data["verification_status"] == "unverified"

    def test_create_job_in_registry_verified(self, api_client, user1, project1):
        TaskRegistry.objects.create(project=project1, task_identifier="tasks.verified_task")

        api_client.force_authenticate(user=user1)
        url = reverse("api:jobs:job-list")
        data = {
            "project": project1.id,
            "name": "Verified Job",
            "task_identifier": "tasks.verified_task",
        }

        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        resp_data = response.data.get("data", response.data)
        assert resp_data["verification_status"] == "verified"
        assert resp_data["last_verified_at"] is not None

    def test_create_job_duplicate(self, api_client, user1, project1):
        Job.objects.create(project=project1, name="Existing Job", task_identifier="tasks.existing")

        api_client.force_authenticate(user=user1)
        url = reverse("api:jobs:job-list")
        data = {
            "project": project1.id,
            "name": "Duplicate Job",
            "task_identifier": "tasks.existing",
        }

        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_job_inactive_project(self, api_client, user1, project1):
        project1.status = Project.Status.INACTIVE
        project1.save()

        api_client.force_authenticate(user=user1)
        url = reverse("api:jobs:job-list")
        data = {"project": project1.id, "name": "New Job", "task_identifier": "tasks.new"}

        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_soft_delete_and_restore_job(self, api_client, user1, project1):
        job = Job.objects.create(project=project1, name="To Delete", task_identifier="tasks.delete")

        api_client.force_authenticate(user=user1)

        url_detail = reverse("api:jobs:job-detail", kwargs={"pk": job.id})
        response = api_client.delete(url_detail)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        job.refresh_from_db()
        assert job.is_deleted is True

        url_restore = reverse("api:jobs:job-restore", kwargs={"pk": job.id})
        response = api_client.post(url_restore)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        job.refresh_from_db()
        assert job.is_deleted is False

    def test_deleted_job_cannot_change_status(self, api_client, user1, project1):
        job = Job.objects.create(
            project=project1, name="To Edit", task_identifier="tasks.edit", is_deleted=True
        )

        api_client.force_authenticate(user=user1)
        url_detail = reverse("api:jobs:job-detail", kwargs={"pk": job.id})

        data = {"status": "inactive"}
        response = api_client.patch(url_detail, data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
