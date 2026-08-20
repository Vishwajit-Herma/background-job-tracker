import pytest
from django.urls import reverse
from rest_framework import status

from apps.projects.models import APIKey
from apps.jobs.models import Job
from apps.executions.models import Execution

pytestmark = pytest.mark.django_db


class TestIngestionAPI:
    @pytest.fixture
    def api_key(self, project1, user1):
        key_record, raw_key = APIKey.create_key(project1, "Ingestion Key", user1)
        return key_record, raw_key

    def test_missing_api_key(self, api_client):
        url = reverse("api:executions:ingestion-list")
        response = api_client.post(url, {})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_api_key(self, api_client):
        url = reverse("api:executions:ingestion-list")
        response = api_client.post(url, {}, HTTP_X_API_KEY="rk_live_invalidkey")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_revoked_api_key(self, api_client, api_key, user1):
        key_record, raw_key = api_key
        key_record.revoked_at = "2026-01-01T00:00:00Z"
        key_record.save()

        url = reverse("api:executions:ingestion-list")
        response = api_client.post(url, {}, HTTP_X_API_KEY=raw_key)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_single_ingestion(self, api_client, api_key, project1):
        key_record, raw_key = api_key
        url = reverse("api:executions:ingestion-list")

        data = {
            "event_id": "evt-28f60f40",
            "external_id": "exec_1",
            "task_identifier": "tasks.test_task",
            "status": "success",
            "started_at": "2026-08-20T10:00:00Z",
            "finished_at": "2026-08-20T10:00:05Z",
            "event_timestamp": "2026-08-20T10:00:05Z",
            "queue": "default",
        }

        response = api_client.post(url, data, HTTP_X_API_KEY=raw_key, format="json")
        assert response.status_code == status.HTTP_202_ACCEPTED

        # Verify job was automatically created
        job = Job.objects.get(project=project1, task_identifier="tasks.test_task")
        assert job.verification_status == Job.VerificationStatus.VERIFIED

        # Verify execution was created
        exec_obj = Execution.objects.get(job=job, external_id="exec_1")
        assert exec_obj.status == "success"
        assert exec_obj.duration_ms == 5000  # Calculated automatically

    def test_batch_ingestion(self, api_client, api_key, project1):
        key_record, raw_key = api_key
        url = reverse("api:executions:ingestion-batch")

        data = {
            "executions": [
                {
                    "event_id": "evt-dfb0cd85",
                    "external_id": "exec_1",
                    "task_identifier": "tasks.test_task",
                    "status": "running",
                    "event_timestamp": "2026-08-20T10:00:00Z",
                },
                {
                    "event_id": "evt-1c4fbbe3",
                    "external_id": "exec_2",
                    "task_identifier": "tasks.test_task_2",
                    "status": "pending",
                    "event_timestamp": "2026-08-20T10:00:00Z",
                },
                # Duplicate ID to test batch idempotency
                {
                    "event_id": "evt-6bf4f02b",
                    "external_id": "exec_1",
                    "task_identifier": "tasks.test_task",
                    "status": "success",
                    "duration_ms": 1500,
                    "event_timestamp": "2026-08-20T10:00:05Z",
                },
            ]
        }

        response = api_client.post(url, data, HTTP_X_API_KEY=raw_key, format="json")
        assert response.status_code == status.HTTP_202_ACCEPTED

        # Verify response counts
        assert (
            response.data["data"]["accepted"] == 3
        )  # All 3 events were successfully merged into 2 Executions
        assert response.data["data"]["duplicates"] == 0

        assert Job.objects.filter(project=project1).count() == 2
        assert Execution.objects.filter(job__project=project1).count() == 2

        # Exec 1 should be success (merged out the running state)
        exec1 = Execution.objects.get(external_id="exec_1")
        assert exec1.status == "success"
        assert exec1.duration_ms == 1500

    def test_inactive_project_rejected(self, api_client, api_key, project1):
        key_record, raw_key = api_key
        project1.status = "inactive"
        project1.save()

        url = reverse("api:executions:ingestion-list")
        response = api_client.post(url, {}, HTTP_X_API_KEY=raw_key, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_api_retry_on_integrity_error(self, api_client, api_key, project1):
        from unittest.mock import patch
        from django.utils import timezone

        key_record, raw_key = api_key
        url = reverse("api:executions:ingestion-list")

        job = Job.objects.create(project=project1, name="Job", task_identifier="tasks.test_retry")
        now = timezone.now()

        data = {
            "event_id": "evt-e1995590",
            "external_id": "exec_retry",
            "task_identifier": "tasks.test_retry",
            "status": "success",
            "event_timestamp": now.isoformat(),
        }

        # We pre-create the Execution in the DB to represent what Request A does concurrently
        Execution.objects.create(
            job=job, external_id="exec_retry", status="running", last_event_at=now
        )

        real_sfu = Execution.objects.select_for_update

        def mock_sfu(*args, **kwargs):
            if mock_sfu.called:
                # Retry attempt: act normally, row is found, it falls back to update
                return real_sfu(*args, **kwargs)
            mock_sfu.called = True

            # First attempt: hide the row to force it into the bulk_create path
            return Execution.objects.none()

        mock_sfu.called = False

        # When it tries to bulk_create, the DB will organically throw an IntegrityError
        # because the row actually exists!
        with patch(
            "apps.executions.services.Execution.objects.select_for_update", side_effect=mock_sfu
        ):
            response = api_client.post(url, data, HTTP_X_API_KEY=raw_key, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED

        # Because Request A only created the Execution and no ExecutionEvent,
        # Request B's completely fresh event_id is accepted as historical telemetry.
        assert response.data["data"]["duplicates"] == 0
        assert response.data["data"]["accepted"] == 1

        exec_obj = Execution.objects.get(job=job, external_id="exec_retry")
        # Ensure it didn't overwrite status because timestamp was equal
        assert exec_obj.status == "running"
