import pytest
from django.urls import reverse
from rest_framework import status
from django.utils import timezone

from apps.jobs.models import Job
from apps.executions.models import Execution, ExecutionEvent

pytestmark = pytest.mark.django_db


class TestExecutionEventsAPI:
    def test_list_events(self, api_client, user1, project1):
        job = Job.objects.create(project=project1, name="Job", task_identifier="tasks.job")
        execution = Execution.objects.create(
            job=job, external_id="ext_1", status="success", last_event_at=timezone.now()
        )

        ExecutionEvent.objects.create(
            execution=execution,
            event_id="evt_1",
            status="running",
            event_timestamp=timezone.now() - timezone.timedelta(seconds=10),
        )
        ExecutionEvent.objects.create(
            execution=execution, event_id="evt_2", status="success", event_timestamp=timezone.now()
        )

        api_client.force_authenticate(user=user1)
        url = reverse("api:executions:execution-events", kwargs={"pk": execution.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # Order should be descending by event_timestamp
        print(response.data)
        assert "data" in response.data or "results" in response.data
        if "results" in response.data:
            events = response.data["results"]
        elif "data" in response.data and "results" in response.data["data"]:
            events = response.data["data"]["results"]
        else:
            events = response.data["data"]

        assert len(events) == 2
        assert events[0]["event_id"] == "evt_2"
        assert events[1]["event_id"] == "evt_1"

    def test_tenant_isolation(self, api_client, user2, project1):
        # user2 does not have access to project1
        job = Job.objects.create(project=project1, name="Job", task_identifier="tasks.job")
        execution = Execution.objects.create(
            job=job, external_id="ext_1", status="success", last_event_at=timezone.now()
        )

        ExecutionEvent.objects.create(
            execution=execution, event_id="evt_1", status="running", event_timestamp=timezone.now()
        )

        api_client.force_authenticate(user=user2)
        url = reverse("api:executions:execution-events", kwargs={"pk": execution.id})
        response = api_client.get(url)

        # ExecutionViewSet raises 404 for objects outside of tenant access
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated(self, api_client, project1):
        job = Job.objects.create(project=project1, name="Job", task_identifier="tasks.job")
        execution = Execution.objects.create(
            job=job, external_id="ext_1", status="success", last_event_at=timezone.now()
        )

        url = reverse("api:executions:execution-events", kwargs={"pk": execution.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
