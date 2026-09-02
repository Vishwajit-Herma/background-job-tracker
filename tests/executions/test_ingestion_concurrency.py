import threading
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.executions.models import Execution, ExecutionEvent
from apps.jobs.models import Job
from apps.projects.models import APIKey, Project, Team

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


@pytest.fixture
def user1(db):
    return User.objects.create_user(email="concurrent_user@example.com", password="password")


@pytest.fixture
def project1(db, user1):
    team = Team.objects.create(name="Concurrent Team", owner=user1)
    return Project.objects.create(team=team, name="Concurrent Project")


class TestIngestionConcurrency:
    @pytest.fixture
    def api_key(self, project1, user1):
        key_record, raw_key = APIKey.create_key(project1, "Ingestion Key", user1)
        return key_record, raw_key

    def test_concurrent_ingestion_idempotency(self, api_key, project1):
        key_record, raw_key = api_key
        url = reverse("api:executions:ingestion-list")

        # Test data for the exact same event, sent concurrently
        data = {
            "event_id": "evt-concurrent-123",
            "external_id": "exec_concurrent",
            "task_identifier": "tasks.concurrent_task",
            "status": "success",
            "event_timestamp": "2026-08-20T10:00:00Z",
        }

        thread_count = 5
        barrier = threading.Barrier(thread_count)
        responses = []
        errors = []

        def make_request():
            try:
                client = APIClient()
                barrier.wait(timeout=5.0)
                response = client.post(url, data, HTTP_X_API_KEY=raw_key, format="json")
                responses.append(response.status_code)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=make_request) for _ in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(responses) == thread_count
        # All concurrent requests should return 202 Accepted
        for status_code in responses:
            assert status_code == status.HTTP_202_ACCEPTED

        # Verify idempotency
        job = Job.objects.get(project=project1, task_identifier="tasks.concurrent_task")

        # There should only be ONE Execution and ONE ExecutionEvent
        assert Execution.objects.filter(job=job, external_id="exec_concurrent").count() == 1
        assert ExecutionEvent.objects.filter(event_id="evt-concurrent-123").count() == 1

    def test_concurrent_batch_ingestion_idempotency(self, api_key, project1):
        key_record, raw_key = api_key
        url = reverse("api:executions:ingestion-batch")

        # Batch containing multiple events for the same execution
        batch_payload = {
            "executions": [
                {
                    "event_id": "evt-batch-race-1",
                    "external_id": "exec_batch_race",
                    "task_identifier": "tasks.batch_race_task",
                    "status": "running",
                    "event_timestamp": "2026-08-20T10:00:00Z",
                },
                {
                    "event_id": "evt-batch-race-2",
                    "external_id": "exec_batch_race",
                    "task_identifier": "tasks.batch_race_task",
                    "status": "success",
                    "event_timestamp": "2026-08-20T10:00:05Z",
                },
            ]
        }

        thread_count = 4
        barrier = threading.Barrier(thread_count)
        responses = []
        errors = []

        def make_batch_request():
            try:
                client = APIClient()
                barrier.wait(timeout=5.0)
                response = client.post(url, batch_payload, HTTP_X_API_KEY=raw_key, format="json")
                responses.append(response.status_code)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=make_batch_request) for _ in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(responses) == thread_count
        for status_code in responses:
            assert status_code == status.HTTP_202_ACCEPTED

        job = Job.objects.get(project=project1, task_identifier="tasks.batch_race_task")
        assert Execution.objects.filter(job=job, external_id="exec_batch_race").count() == 1
        assert ExecutionEvent.objects.filter(event_id="evt-batch-race-1").count() == 1
        assert ExecutionEvent.objects.filter(event_id="evt-batch-race-2").count() == 1
