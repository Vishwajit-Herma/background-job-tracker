import pytest
from django.urls import reverse
from rest_framework import status

from django.utils import timezone
from apps.jobs.models import Job
from apps.executions.models import Execution

pytestmark = pytest.mark.django_db


class TestExecutionAPI:
    @pytest.fixture
    def setup_data(self, project1, user1):
        job = Job.objects.create(project=project1, name="Test Job", task_identifier="tasks.test")
        exec1 = Execution.objects.create(
            job=job,
            external_id="exec_1",
            status=Execution.Status.SUCCESS,
            duration_ms=100,
            last_event_at=timezone.now(),
        )
        exec2 = Execution.objects.create(
            job=job,
            external_id="exec_2",
            status=Execution.Status.FAILED,
            error_message="Boom",
            last_event_at=timezone.now(),
        )
        return exec1, exec2

    def test_list_executions(self, api_client, user1, setup_data):
        exec1, exec2 = setup_data

        api_client.force_authenticate(user=user1)
        url = reverse("api:executions:execution-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        results = response.data.get("data", response.data)
        assert len(results) == 2

    def test_retrieve_execution(self, api_client, user1, setup_data):
        exec1, exec2 = setup_data

        api_client.force_authenticate(user=user1)
        url = reverse("api:executions:execution-detail", kwargs={"pk": exec1.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        item_data = response.data.get("data", response.data)
        assert item_data["external_id"] == "exec_1"
        assert item_data["duration_ms"] == 100

    def test_create_not_allowed(self, api_client, user1):
        api_client.force_authenticate(user=user1)
        url = reverse("api:executions:execution-list")
        response = api_client.post(url, {})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_tenant_isolation(self, api_client, user2, setup_data):
        exec1, exec2 = setup_data

        # user2 is not in the team for project1
        api_client.force_authenticate(user=user2)
        url = reverse("api:executions:execution-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        results = response.data.get("data", response.data)
        assert len(results) == 0  # Should see nothing

        url_detail = reverse("api:executions:execution-detail", kwargs={"pk": exec1.id})
        response_detail = api_client.get(url_detail)
        assert response_detail.status_code == status.HTTP_404_NOT_FOUND

    def test_cancel_running_execution(self, api_client, user1, project1):
        job = Job.objects.create(project=project1, name="Test Job Cancel", task_identifier="tasks.cancel")
        running_exec = Execution.objects.create(
            job=job,
            external_id="exec_running",
            status=Execution.Status.RUNNING,
            started_at=timezone.now(),
            last_event_at=timezone.now(),
        )

        api_client.force_authenticate(user=user1)
        url = reverse("api:executions:execution-cancel", kwargs={"pk": running_exec.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        running_exec.refresh_from_db()
        assert running_exec.status == Execution.Status.CANCELLED
        assert "Manually cancelled by user" in running_exec.error_message
