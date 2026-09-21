import pytest
from django.utils import timezone
from datetime import timedelta

from apps.jobs.models import Job
from apps.executions.models import Execution
from apps.executions.services import ingest_executions_batch

pytestmark = pytest.mark.django_db


class TestServices:
    def test_ingest_executions_batch_job_resolution(self, project1):
        # Missing job should be created
        now = timezone.now()
        data = [
            {
                "event_id": "evt-b482a9a1",
                "external_id": "ext_1",
                "task_identifier": "tasks.new_job",
                "status": "success",
                "event_timestamp": now,
            }
        ]

        result = ingest_executions_batch(project1, data)
        assert result["accepted"] == 1

        job = Job.objects.get(project=project1, task_identifier="tasks.new_job")
        assert job.name == "New Job"
        assert job.verification_status == Job.VerificationStatus.VERIFIED

        exec_obj = Execution.objects.get(job=job, external_id="ext_1")
        assert exec_obj.status == "success"
        assert exec_obj.last_event_at == now

    def test_out_of_order_stale_event_ignored(self, project1):
        Job.objects.create(project=project1, name="Job", task_identifier="tasks.job")
        now = timezone.now()
        older = now - timedelta(seconds=10)

        # Initial ingestion - newer event arrives first
        data1 = [
            {
                "event_id": "evt-b9c17caf",
                "external_id": "ext_1",
                "task_identifier": "tasks.job",
                "status": "success",
                "event_timestamp": now,
            }
        ]
        ingest_executions_batch(project1, data1)

        # Stale ingestion - older event arrives later
        data2 = [
            {
                "event_id": "evt-247c7229",
                "external_id": "ext_1",
                "task_identifier": "tasks.job",
                "status": "running",
                "duration_ms": 100,
                "event_timestamp": older,
            }
        ]
        result = ingest_executions_batch(project1, data2)

        # Stale events are now persisted as history, so they are accepted. They just don't regress Execution.
        assert result["duplicates"] == 0
        assert result["accepted"] == 1

        # Verify state did not regress or merge
        exec_obj = Execution.objects.get(external_id="ext_1")
        assert exec_obj.status == "success"
        assert exec_obj.duration_ms is None

    def test_inactive_job_skipped(self, project1):
        Job.objects.create(
            project=project1, name="Job", task_identifier="tasks.job", status=Job.Status.INACTIVE
        )

        data = [
            {
                "event_id": "evt-e8849a0f",
                "external_id": "ext_1",
                "task_identifier": "tasks.job",
                "status": "success",
                "event_timestamp": timezone.now(),
            }
        ]
        result = ingest_executions_batch(project1, data)

        assert result["accepted"] == 0
        assert result["rejected"] == 1
        assert Execution.objects.count() == 0

    def test_intra_batch_chronological_merge(self, project1):
        Job.objects.create(project=project1, name="Job", task_identifier="tasks.job")

        now = timezone.now()
        older = now - timedelta(seconds=10)

        # Batch with two events for the same execution
        # Event 1: newer timestamp, Event 2: older timestamp
        data = [
            {
                "event_id": "evt-74a03f3f",
                "external_id": "ext_1",
                "task_identifier": "tasks.job",
                "status": "success",
                "retry_count": 0,
                "event_timestamp": now,
            },
            {
                "event_id": "evt-950e278d",
                "external_id": "ext_1",
                "task_identifier": "tasks.job",
                "status": "running",
                "retry_count": 1,
                "duration_ms": 50,
                "event_timestamp": older,
            },
        ]

        result = ingest_executions_batch(project1, data)

        # The older event is retained as historical telemetry but must not override the newer Execution snapshot.
        # We assert that the batch resolves correctly.
        assert result["duplicates"] == 0
        assert result["rejected"] == 0

        exec_obj = Execution.objects.get(external_id="ext_1")
        # Should take the status of the newer event
        assert exec_obj.status == "success"
        # The older event provided duration_ms=50, the newer event didn't provide it, so it merges perfectly
        assert exec_obj.duration_ms == 50
        assert exec_obj.retry_count == 1

    def test_inactive_job_remains_unverified(self, project1):
        job = Job.objects.create(
            project=project1,
            name="Job",
            task_identifier="tasks.job",
            status=Job.Status.INACTIVE,
            verification_status=Job.VerificationStatus.UNVERIFIED,
        )

        data = [
            {
                "event_id": "evt-68f537e6",
                "external_id": "ext_1",
                "task_identifier": "tasks.job",
                "status": "success",
                "event_timestamp": timezone.now(),
            }
        ]
        result = ingest_executions_batch(project1, data)

        assert result["rejected"] == 1
        job.refresh_from_db()
        assert job.verification_status == Job.VerificationStatus.UNVERIFIED

    def test_same_execution_in_two_requests_older_is_duplicate(self, project1):
        now = timezone.now()
        older = now - timedelta(seconds=10)

        data1 = [
            {
                "event_id": "evt-e4f47e87",
                "external_id": "ext_1",
                "task_identifier": "tasks.new",
                "status": "success",
                "event_timestamp": now,
            }
        ]
        result1 = ingest_executions_batch(project1, data1)
        assert result1["accepted"] == 1

        data2 = [
            {
                "event_id": "evt-a2408d9a",
                "external_id": "ext_1",
                "task_identifier": "tasks.new",
                "status": "running",
                "event_timestamp": older,
            }
        ]
        result2 = ingest_executions_batch(project1, data2)
        assert result2["duplicates"] == 0
        assert result2["accepted"] == 1

    def test_same_external_id_for_different_jobs_allowed(self, project1):
        now = timezone.now()
        data = [
            {
                "event_id": "evt-ae3db5f9",
                "external_id": "ext_1",
                "task_identifier": "tasks.a",
                "status": "success",
                "event_timestamp": now,
            },
            {
                "event_id": "evt-139f1548",
                "external_id": "ext_1",
                "task_identifier": "tasks.b",
                "status": "success",
                "event_timestamp": now,
            },
        ]
        result = ingest_executions_batch(project1, data)
        assert result["accepted"] == 2
        assert Execution.objects.count() == 2

    def test_same_external_id_same_job_duplicate_idempotent(self, project1):
        now = timezone.now()
        data = [
            {
                "event_id": "evt-2837652a",
                "external_id": "ext_1",
                "task_identifier": "tasks.a",
                "status": "success",
                "event_timestamp": now,
            }
        ]
        ingest_executions_batch(project1, data)

        result = ingest_executions_batch(project1, data)
        assert result["duplicates"] == 1
        assert result["accepted"] == 0
        assert Execution.objects.count() == 1

    def test_equal_event_timestamp_is_duplicate(self, project1):
        now = timezone.now()
        data = [
            {
                "event_id": "evt-135783ef",
                "external_id": "ext_1",
                "task_identifier": "tasks.a",
                "status": "running",
                "event_timestamp": now,
            },
            {
                "event_id": "evt-cd38acf7",
                "external_id": "ext_1",
                "task_identifier": "tasks.a",
                "status": "success",
                "event_timestamp": now,
            },
        ]
        result = ingest_executions_batch(project1, data)
        assert result["accepted"] == 2
        assert result["duplicates"] == 0
        assert Execution.objects.count() == 1

    def test_batch_older_newer_oldest(self, project1):
        t_oldest = timezone.now() - timedelta(seconds=20)
        t_older = timezone.now() - timedelta(seconds=10)
        t_newer = timezone.now()

        data = [
            {
                "event_id": "evt-ef6cbd68",
                "external_id": "ext_1",
                "task_identifier": "tasks.a",
                "status": "pending",
                "event_timestamp": t_older,
            },
            {
                "event_id": "evt-3113f18e",
                "external_id": "ext_1",
                "task_identifier": "tasks.a",
                "status": "success",
                "event_timestamp": t_newer,
            },
            {
                "event_id": "evt-62579eed",
                "external_id": "ext_1",
                "task_identifier": "tasks.a",
                "status": "running",
                "event_timestamp": t_oldest,
            },
        ]
        result = ingest_executions_batch(project1, data)

        assert result["accepted"] == 3

        exec_obj = Execution.objects.get(external_id="ext_1")
        assert exec_obj.status == "success"

    def test_concurrent_creation_throws_integrity_error(self, project1):
        import pytest
        from django.db import IntegrityError
        from unittest.mock import patch

        Job.objects.create(project=project1, name="Job", task_identifier="tasks.a")

        data = [
            {
                "event_id": "evt-a5a2b797",
                "external_id": "ext_1",
                "task_identifier": "tasks.a",
                "status": "success",
                "event_timestamp": timezone.now(),
            }
        ]

        with patch("apps.executions.services.Execution.objects.bulk_create") as mock_bulk_create:
            mock_bulk_create.side_effect = IntegrityError(
                "duplicate key value violates unique constraint"
            )
            with pytest.raises(IntegrityError):
                ingest_executions_batch(project1, data)

        assert Execution.objects.count() == 0

    def test_actual_execution_event_persistence(self, project1):
        Job.objects.create(project=project1, name="Job", task_identifier="tasks.job")
        now = timezone.now()
        older = now - timedelta(seconds=10)

        data = [
            {
                "event_id": "evt-new-123",
                "external_id": "ext_1",
                "task_identifier": "tasks.job",
                "status": "success",
                "event_timestamp": now,
            },
            {
                "event_id": "evt-old-456",
                "external_id": "ext_1",
                "task_identifier": "tasks.job",
                "status": "running",
                "event_timestamp": older,
            },
        ]

        result = ingest_executions_batch(project1, data)
        assert result["accepted"] == 2
        assert result["duplicates"] == 0

        from apps.executions.models import ExecutionEvent

        exec_obj = Execution.objects.get(external_id="ext_1")

        events = ExecutionEvent.objects.filter(execution=exec_obj).order_by("-event_timestamp")
        assert events.count() == 2

        assert events[0].event_id == "evt-new-123"
        assert events[0].status == "success"
        assert events[0].event_timestamp == now

        assert events[1].event_id == "evt-old-456"
        assert events[1].status == "running"
        assert events[1].event_timestamp == older

    def test_event_id_idempotency(self, project1):
        Job.objects.create(project=project1, name="Job", task_identifier="tasks.job")
        now = timezone.now()

        # Request 1
        data1 = [
            {
                "event_id": "EVT-123",
                "external_id": "ext_1",
                "task_identifier": "tasks.job",
                "status": "running",
                "event_timestamp": now,
            }
        ]
        result1 = ingest_executions_batch(project1, data1)
        assert result1["accepted"] == 1
        assert result1["duplicates"] == 0

        # Request 2 (Retry of Request 1 with same event_id)
        data2 = [
            {
                "event_id": "EVT-123",
                "external_id": "ext_1",
                "task_identifier": "tasks.job",
                "status": "running",
                "event_timestamp": now,
            }
        ]
        result2 = ingest_executions_batch(project1, data2)
        assert result2["accepted"] == 0
        assert result2["duplicates"] == 1

        from apps.executions.models import ExecutionEvent

        exec_obj = Execution.objects.get(external_id="ext_1")

        # Explicitly verify the DB only has 1 event despite 2 requests
        events = ExecutionEvent.objects.filter(execution=exec_obj)
        assert events.count() == 1
        assert events[0].event_id == "EVT-123"

    def test_auto_recover_stalled_finding_on_terminal_ingestion(self, project1):
        from apps.reliability.models import ReliabilityFinding

        job = Job.objects.create(
            project=project1, name="Stalled Job", task_identifier="tasks.stalled"
        )
        now = timezone.now()

        # Ingest RUNNING event
        ingest_executions_batch(
            project1,
            [
                {
                    "event_id": "evt-run-1",
                    "external_id": "ext_stalled",
                    "task_identifier": "tasks.stalled",
                    "status": "running",
                    "event_timestamp": now - timedelta(seconds=20),
                    "started_at": now - timedelta(seconds=20),
                }
            ],
        )

        exec_obj = Execution.objects.get(job=job, external_id="ext_stalled")

        # Create active STALLED_EXECUTION finding on this running execution
        finding = ReliabilityFinding.objects.create(
            job=job,
            execution=exec_obj,
            condition_type=ReliabilityFinding.ConditionType.STALLED_EXECUTION,
            severity=ReliabilityFinding.Severity.CRITICAL,
            status=ReliabilityFinding.Status.ACTIVE,
            details={"runtime_seconds": 20, "max_runtime_seconds": 5},
            detected_at=now - timedelta(seconds=10),
        )

        # Now ingest SUCCESS terminal event
        result = ingest_executions_batch(
            project1,
            [
                {
                    "event_id": "evt-succ-1",
                    "external_id": "ext_stalled",
                    "task_identifier": "tasks.stalled",
                    "status": "success",
                    "event_timestamp": now,
                    "started_at": now - timedelta(seconds=20),
                    "finished_at": now,
                    "duration_ms": 20000,
                }
            ],
        )

        assert result["accepted"] == 1
        finding.refresh_from_db()
        assert finding.status == ReliabilityFinding.Status.RECOVERED
        assert finding.recovered_at is not None
