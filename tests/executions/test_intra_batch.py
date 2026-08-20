import pytest
from datetime import datetime, UTC
from apps.executions.models import Execution
from apps.executions.services import ingest_executions_batch
from apps.jobs.models import Job


@pytest.mark.django_db
def test_intra_batch_merging(project1):
    """
    If a batch contains multiple events for the same execution (e.g. RUNNING then SUCCESS),
    the attributes from both events should be merged, not overwritten.
    """
    job = Job.objects.create(project=project1, name="Job", task_identifier="tasks.job")

    start_time = datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC)
    finish_time = datetime(2023, 1, 1, 10, 5, 0, tzinfo=UTC)

    payload = [
        {
            "task_identifier": job.task_identifier,
            "event_id": "evt-5b4f3f9e",
            "external_id": "exec_batch_1",
            "status": "running",
            "worker": "worker-A",
            "started_at": start_time,
            "metadata": {"foo": "bar"},
            "event_timestamp": start_time.isoformat(),
        },
        {
            "task_identifier": job.task_identifier,
            "event_id": "evt-e1543021",
            "external_id": "exec_batch_1",
            "status": "success",
            "finished_at": finish_time,
            "metadata": {"baz": "qux"},
            "event_timestamp": finish_time.isoformat(),
        },
    ]

    ingest_executions_batch(project1, payload)

    exec_obj = Execution.objects.get(external_id="exec_batch_1")

    # Bug check: Worker should be retained from the first event!
    assert exec_obj.worker == "worker-A"
    # Started at should be retained!
    assert exec_obj.started_at == start_time
    # Finished at should be recorded!
    assert exec_obj.finished_at == finish_time
    # Duration should be calculated (5 minutes = 300 seconds = 300,000 ms)
    assert exec_obj.duration_ms == 300000
    assert exec_obj.status == Execution.Status.SUCCESS
    assert exec_obj.metadata == {"foo": "bar", "baz": "qux"}
