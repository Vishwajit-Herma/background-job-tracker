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
def project_with_data(team1):
    project = Project.objects.create(team=team1, name="KPI Project")
    job_a = Job.objects.create(project=project, name="Job A", task_identifier="task_a")
    job_b = Job.objects.create(project=project, name="Job B", task_identifier="task_b")

    now = timezone.now()
    # Job A executions: 2 SUCCESS, 1 FAILED
    Execution.objects.create(
        job=job_a, external_id="1", status=Execution.Status.SUCCESS, last_event_at=now
    )
    Execution.objects.create(
        job=job_a, external_id="2", status=Execution.Status.SUCCESS, last_event_at=now
    )
    Execution.objects.create(
        job=job_a, external_id="3", status=Execution.Status.FAILED, last_event_at=now
    )

    # Job B executions: 1 SUCCESS, 1 FAILED
    Execution.objects.create(
        job=job_b, external_id="4", status=Execution.Status.SUCCESS, last_event_at=now
    )
    Execution.objects.create(
        job=job_b, external_id="5", status=Execution.Status.FAILED, last_event_at=now
    )

    return project, job_a, job_b


@pytest.mark.django_db
class TestProjectKPIs:
    def test_project_kpi_annotations_exact_values(self, api_client, user1, project_with_data):
        project, job_a, job_b = project_with_data

        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-detail", args=[project.id])
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        data = response.json()["data"]

        assert data["jobs_count"] == 2
        assert data["executions_count"] == 5
        assert data["success_rate"] == 60.0  # 3 success out of 5
        assert data["active_incidents_count"] == 0
        assert data["operational_status"] == "HEALTHY"

    def test_project_operational_status_degraded(self, api_client, user1, project_with_data):
        project, job_a, job_b = project_with_data

        # Create an OPEN DEGRADED incident
        Incident.objects.create(
            project=project,
            job=job_a,
            status=Incident.Status.OPEN,
            severity=Incident.Severity.DEGRADED,
        )

        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-detail", args=[project.id])
        response = api_client.get(url)

        data = response.json()["data"]
        assert data["active_incidents_count"] == 1
        assert data["operational_status"] == "DEGRADED"

    def test_project_operational_status_critical(self, api_client, user1, project_with_data):
        project, job_a, job_b = project_with_data

        # Create an OPEN CRITICAL incident
        Incident.objects.create(
            project=project,
            job=job_a,
            status=Incident.Status.OPEN,
            severity=Incident.Severity.CRITICAL,
        )
        # And a DEGRADED incident
        Incident.objects.create(
            project=project,
            job=job_b,
            status=Incident.Status.ACKNOWLEDGED,
            severity=Incident.Severity.DEGRADED,
        )

        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-detail", args=[project.id])
        response = api_client.get(url)

        data = response.json()["data"]
        assert data["active_incidents_count"] == 2
        assert data["operational_status"] == "CRITICAL"

    def test_resolved_incidents_ignored_for_status(self, api_client, user1, project_with_data):
        project, job_a, job_b = project_with_data

        # Create a RESOLVED CRITICAL incident
        Incident.objects.create(
            project=project,
            job=job_a,
            status=Incident.Status.RESOLVED,
            severity=Incident.Severity.CRITICAL,
        )

        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-detail", args=[project.id])
        response = api_client.get(url)

        data = response.json()["data"]
        assert data["active_incidents_count"] == 0
        assert data["operational_status"] == "HEALTHY"

    def test_zero_executions_behavior(self, api_client, user1, project1):
        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-detail", args=[project1.id])
        response = api_client.get(url)

        data = response.json()["data"]
        assert data["jobs_count"] == 0
        assert data["executions_count"] == 0
        assert data["success_rate"] is None
        assert data["active_incidents_count"] == 0
        assert data["operational_status"] == "HEALTHY"

    def test_archived_projects_excluded(self, api_client, user1, project_with_data):
        project, _, _ = project_with_data
        project.soft_delete(user=user1)

        api_client.force_authenticate(user=user1)
        url = reverse("api:projects:project-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        # Verify list doesn't include the archived project
        data = response.json()["data"]
        assert len(data) == 0

    def test_tenant_isolation_kpis(self, api_client, user1, project_with_data):
        project, _, _ = project_with_data

        # user2 should not see user1's project or its KPIs
        user2 = User.objects.create(email="user2@example.com", password="password")
        api_client.force_authenticate(user=user2)

        url = reverse("api:projects:project-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["data"]) == 0
