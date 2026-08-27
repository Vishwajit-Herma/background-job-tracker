import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.utils import timezone

from apps.projects.models import Project
from apps.teams.models import Team
from apps.users.models import User
from apps.jobs.models import Job
from apps.executions.models import Execution
from apps.incidents.models import Incident


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user1(db):
    return User.objects.create(email="user1@example.com", password="password")


@pytest.fixture
def team1(user1):
    return Team.objects.create(name="Team 1", slug="team-1", owner=user1)


@pytest.fixture
def project1(team1):
    return Project.objects.create(team=team1, name="Project 1")


@pytest.fixture
def job_with_data(project1):
    job_a = Job.objects.create(project=project1, name="Job A", task_identifier="task_a")

    now = timezone.now()
    # Job A executions: 3 SUCCESS, 1 FAILED
    Execution.objects.create(
        job=job_a, external_id="1", status=Execution.Status.SUCCESS, last_event_at=now
    )
    Execution.objects.create(
        job=job_a, external_id="2", status=Execution.Status.SUCCESS, last_event_at=now
    )
    Execution.objects.create(
        job=job_a, external_id="3", status=Execution.Status.SUCCESS, last_event_at=now
    )
    Execution.objects.create(
        job=job_a, external_id="4", status=Execution.Status.FAILED, last_event_at=now
    )

    return project1, job_a


@pytest.mark.django_db
class TestJobKPIs:
    def test_job_kpi_annotations_exact_values(self, api_client, user1, job_with_data):
        project, job_a = job_with_data

        api_client.force_authenticate(user=user1)
        url = reverse("api:jobs:job-detail", args=[job_a.id])
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        data = response.json()["data"]

        assert data["executions_count"] == 4
        assert data["success_rate"] == 75.0  # 3 success out of 4
        assert data["active_incidents_count"] == 0
        assert data["operational_status"] == "HEALTHY"

    def test_job_operational_status_degraded(self, api_client, user1, job_with_data):
        project, job_a = job_with_data

        Incident.objects.create(
            project=project,
            job=job_a,
            status=Incident.Status.OPEN,
            severity=Incident.Severity.DEGRADED,
        )

        api_client.force_authenticate(user=user1)
        url = reverse("api:jobs:job-detail", args=[job_a.id])
        response = api_client.get(url)

        data = response.json()["data"]
        assert data["active_incidents_count"] == 1
        assert data["operational_status"] == "DEGRADED"

    def test_job_operational_status_critical(self, api_client, user1, job_with_data):
        project, job_a = job_with_data

        Incident.objects.create(
            project=project,
            job=job_a,
            status=Incident.Status.OPEN,
            severity=Incident.Severity.CRITICAL,
        )

        api_client.force_authenticate(user=user1)
        url = reverse("api:jobs:job-detail", args=[job_a.id])
        response = api_client.get(url)

        data = response.json()["data"]
        assert data["active_incidents_count"] == 1
        assert data["operational_status"] == "CRITICAL"

    def test_zero_executions_behavior(self, api_client, user1, project1):
        job_b = Job.objects.create(project=project1, name="Job B", task_identifier="task_b")

        api_client.force_authenticate(user=user1)
        url = reverse("api:jobs:job-detail", args=[job_b.id])
        response = api_client.get(url)

        data = response.json()["data"]
        assert data["executions_count"] == 0
        assert data["success_rate"] is None
        assert data["active_incidents_count"] == 0
        assert data["operational_status"] == "HEALTHY"

    def test_no_n1_queries_on_list(
        self, api_client, user1, job_with_data, django_assert_num_queries
    ):
        project, job_a = job_with_data
        # Create a second job with executions
        job_b = Job.objects.create(project=project, name="Job B", task_identifier="task_b")
        now = timezone.now()
        Execution.objects.create(
            job=job_b, external_id="10", status=Execution.Status.SUCCESS, last_event_at=now
        )

        api_client.force_authenticate(user=user1)
        url = reverse("api:jobs:job-list")

        # Determine base number of queries
        with django_assert_num_queries(4):
            # Might be around 6-8 queries for auth, session, permissions, and the single select_related query + count
            response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert len(data) == 2
