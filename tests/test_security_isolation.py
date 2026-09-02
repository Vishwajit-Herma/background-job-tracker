import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.ai.services import build_ai_context
from apps.executions.models import Execution
from apps.incidents.models import Incident
from apps.jobs.models import Job
from apps.projects.models import APIKey, Project, Team

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def user_a(db):
    return User.objects.create_user(email="user_a@example.com", password="password_a")


@pytest.fixture
def project_a(db, user_a):
    team = Team.objects.create(name="Team A", slug="team-a", owner=user_a)
    return Project.objects.create(team=team, name="Project A")


@pytest.fixture
def user_b(db):
    return User.objects.create_user(email="user_b@example.com", password="password_b")


@pytest.fixture
def project_b(db, user_b):
    team = Team.objects.create(name="Team B", slug="team-b", owner=user_b)
    return Project.objects.create(team=team, name="Project B")


class TestSecurityIsolation:
    def test_tenant_isolation_executions_list(self, api_client, user_a, project_a, user_b):
        """User B must not be able to view executions belonging to Project A."""
        job_a = Job.objects.create(project=project_a, name="Job A", task_identifier="task.job_a")
        Execution.objects.create(
            job=job_a,
            external_id="exec_a_1",
            status=Execution.Status.SUCCESS,
            last_event_at="2026-08-20T10:00:00Z",
        )

        api_client.force_authenticate(user=user_b)
        url = reverse("api:executions:execution-list") + f"?job={job_a.id}"
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # User B should see 0 executions for Project A's job
        assert len(response.data["data"]) == 0

    def test_tenant_isolation_incidents_access(self, api_client, user_a, project_a, user_b):
        """User B must not see or access incidents belonging to Project A."""
        incident_a = Incident.objects.create(
            project=project_a,
            status=Incident.Status.OPEN,
            severity=Incident.Severity.CRITICAL,
        )

        api_client.force_authenticate(user=user_b)
        # List incidents
        url_list = reverse("api:incidents:incidents-list")
        response_list = api_client.get(url_list)
        assert response_list.status_code == status.HTTP_200_OK
        assert not any(inc["id"] == incident_a.id for inc in response_list.data["data"])

        # Detail incident
        url_detail = reverse("api:incidents:incidents-detail", args=[incident_a.id])
        response_detail = api_client.get(url_detail)
        assert response_detail.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN)

    def test_tenant_isolation_project_analytics(self, api_client, user_a, project_a, user_b):
        """User B must not be allowed to access analytics for Project A."""
        api_client.force_authenticate(user=user_b)
        url = f"/api/projects/{project_a.id}/analytics/"
        response = api_client.get(url)
        assert response.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN)

    def test_tenant_isolation_api_key_management(self, api_client, user_a, project_a, user_b):
        """User B must not manage or list API keys belonging to Project A."""
        APIKey.create_key(project_a, "Key A", user_a)

        api_client.force_authenticate(user=user_b)
        url = reverse("api:projects:apikey-list", kwargs={"project_pk": project_a.id})
        response = api_client.get(url)
        assert response.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN)

    def test_tenant_isolation_ingestion_scoping(self, api_client, user_a, project_a, project_b):
        """Ingestion using Project A's API Key strictly associates records with Project A only."""
        key_a, raw_key_a = APIKey.create_key(project_a, "Key A", user_a)

        url = reverse("api:executions:ingestion-list")
        data = {
            "event_id": "evt-isolation-1",
            "external_id": "exec-isolation-1",
            "task_identifier": "tasks.scoped_task",
            "status": "success",
            "event_timestamp": "2026-08-20T10:00:00Z",
        }

        response = api_client.post(url, data, HTTP_X_API_KEY=raw_key_a, format="json")
        assert response.status_code == status.HTTP_202_ACCEPTED

        # Job must belong to Project A, not Project B
        assert Job.objects.filter(project=project_a, task_identifier="tasks.scoped_task").exists()
        assert not Job.objects.filter(
            project=project_b, task_identifier="tasks.scoped_task"
        ).exists()

    def test_api_key_not_leaked_in_list(self, api_client, project_a, user_a):
        """API key listing must only return key_prefix and never the raw secret or full hash."""
        api_client.force_authenticate(user=user_a)
        APIKey.create_key(project_a, "Test Key", user_a)

        url = reverse("api:projects:apikey-list", kwargs={"project_pk": project_a.id})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

        data = response.data["data"]
        assert len(data) >= 1
        key_data = data[0]

        assert "key_prefix" in key_data
        assert "key" not in key_data
        assert "key_hash" not in key_data

    def test_api_key_str_representation(self, project_a, user_a):
        """The string representation of APIKey must never leak the raw token."""
        key_record, raw_key = APIKey.create_key(project_a, "Test Key 2", user_a)

        str_repr = str(key_record)
        assert raw_key not in str_repr
        assert key_record.key_prefix in str_repr

    def test_ai_context_does_not_expose_credentials_or_unbounded_secrets(self, project_a, user_a):
        """Incident AI context should not include raw passwords or API key tokens."""
        key_record, raw_key = APIKey.create_key(project_a, "Sensitive Key", user_a)
        job_a = Job.objects.create(
            project=project_a, name="Secret Job", task_identifier="tasks.secret_task"
        )
        Execution.objects.create(
            job=job_a,
            external_id="exec_err_1",
            status=Execution.Status.FAILED,
            error_message="Authentication failed for db_user",
            last_event_at="2026-08-20T10:00:00Z",
        )

        incident = Incident.objects.create(
            project=project_a,
            job=job_a,
            status=Incident.Status.OPEN,
            severity=Incident.Severity.CRITICAL,
        )

        context = build_ai_context(incident)
        context_str = str(context)

        # Ensure raw API secret is nowhere in context
        assert raw_key not in context_str
        assert user_a.password not in context_str
