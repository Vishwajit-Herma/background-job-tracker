import io
from datetime import timedelta
import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.executions.models import Execution, ExecutionEvent
from apps.executions.services import prune_old_executions
from apps.executions.tasks import prune_old_executions_task
from apps.jobs.models import Job
from apps.reliability.models import ReliabilityFinding


@pytest.fixture
def test_job(project1):
    return Job.objects.create(
        project=project1,
        task_identifier="tasks.test_task",
        name="Test Task",
    )


@pytest.mark.django_db
def test_prune_old_executions_deletes_records_older_than_retention(test_job):
    now = timezone.now()

    # Create 3 old executions (older than 30 days)
    old_execs = []
    for i in range(3):
        t = now - timedelta(days=35 + i)
        old_execs.append(
            Execution.objects.create(
                job=test_job,
                external_id=f"exec-old-{i}",
                status=Execution.Status.SUCCESS,
                last_event_at=t,
                created_at=t,
            )
        )
        # Update created_at in DB since auto_now_add overrides during initial create
        Execution.objects.filter(id=old_execs[-1].id).update(created_at=t)

    # Create 2 recent executions (younger than 30 days)
    recent_execs = []
    for i in range(2):
        t = now - timedelta(days=5 + i)
        recent_execs.append(
            Execution.objects.create(
                job=test_job,
                external_id=f"exec-recent-{i}",
                status=Execution.Status.SUCCESS,
                last_event_at=t,
                created_at=t,
            )
        )
        Execution.objects.filter(id=recent_execs[-1].id).update(created_at=t)

    assert Execution.objects.count() == 5

    result = prune_old_executions(retention_days=30, batch_size=100)

    assert result["total_deleted"] == 3
    assert result["total_eligible"] == 3
    assert result["batches"] == 1

    # Only recent executions should remain
    remaining_ids = list(Execution.objects.values_list("id", flat=True))
    assert len(remaining_ids) == 2
    for r in recent_execs:
        assert r.id in remaining_ids
    for o in old_execs:
        assert o.id not in remaining_ids


@pytest.mark.django_db
def test_prune_executions_cascades_events_and_preserves_findings(test_job):
    now = timezone.now()
    old_time = now - timedelta(days=40)

    old_exec = Execution.objects.create(
        job=test_job,
        external_id="exec-cascade-test",
        status=Execution.Status.FAILED,
        last_event_at=old_time,
    )
    Execution.objects.filter(id=old_exec.id).update(created_at=old_time)

    # Create 2 child ExecutionEvents
    event1 = ExecutionEvent.objects.create(
        execution=old_exec,
        event_id="evt-1",
        status=Execution.Status.RUNNING,
        event_timestamp=old_time,
    )
    event2 = ExecutionEvent.objects.create(
        execution=old_exec,
        event_id="evt-2",
        status=Execution.Status.FAILED,
        event_timestamp=old_time + timedelta(seconds=2),
    )

    # Create a ReliabilityFinding linked to this execution
    finding = ReliabilityFinding.objects.create(
        job=test_job,
        execution=old_exec,
        condition_type=ReliabilityFinding.ConditionType.STALLED_EXECUTION,
        status=ReliabilityFinding.Status.RECOVERED,
        details={"reason": "test"},
    )

    assert ExecutionEvent.objects.count() == 2
    assert finding.execution_id == old_exec.id

    result = prune_old_executions(retention_days=30)
    assert result["total_deleted"] == 1

    # Execution deleted
    assert not Execution.objects.filter(id=old_exec.id).exists()
    # Child events cascade-deleted
    assert not ExecutionEvent.objects.filter(id__in=[event1.id, event2.id]).exists()

    # ReliabilityFinding preserved, execution FK set to NULL
    finding.refresh_from_db()
    assert finding.execution is None
    assert finding.status == ReliabilityFinding.Status.RECOVERED


@pytest.mark.django_db
def test_prune_executions_dry_run(test_job):
    now = timezone.now()
    old_time = now - timedelta(days=45)

    old_exec = Execution.objects.create(
        job=test_job,
        external_id="exec-dry-run",
        status=Execution.Status.SUCCESS,
        last_event_at=old_time,
    )
    Execution.objects.filter(id=old_exec.id).update(created_at=old_time)

    result = prune_old_executions(retention_days=30, dry_run=True)

    assert result["total_eligible"] == 1
    assert result["total_deleted"] == 0
    assert result["batches"] == 0
    # Record must still exist
    assert Execution.objects.filter(id=old_exec.id).exists()


@pytest.mark.django_db
def test_prune_executions_batching(test_job):
    now = timezone.now()
    old_time = now - timedelta(days=35)

    # Create 11 old executions
    for i in range(11):
        e = Execution.objects.create(
            job=test_job,
            external_id=f"exec-batch-{i}",
            status=Execution.Status.SUCCESS,
            last_event_at=old_time,
        )
        Execution.objects.filter(id=e.id).update(created_at=old_time)

    assert Execution.objects.count() == 11

    # Batch size = 3 -> Should require 4 batches (3 + 3 + 3 + 2)
    result = prune_old_executions(retention_days=30, batch_size=3)

    assert result["total_deleted"] == 11
    assert result["total_eligible"] == 11
    assert result["batches"] == 4
    assert Execution.objects.count() == 0


@pytest.mark.django_db
def test_prune_executions_invalid_args():
    with pytest.raises(ValueError, match="retention_days must be at least 1"):
        prune_old_executions(retention_days=0)

    with pytest.raises(ValueError, match="batch_size must be at least 1"):
        prune_old_executions(retention_days=30, batch_size=0)


@pytest.mark.django_db
def test_prune_executions_celery_task(test_job):
    now = timezone.now()
    old_time = now - timedelta(days=20)

    e = Execution.objects.create(
        job=test_job,
        external_id="exec-celery-task",
        status=Execution.Status.SUCCESS,
        last_event_at=old_time,
    )
    Execution.objects.filter(id=e.id).update(created_at=old_time)

    # Run Celery task with 15 days retention
    result = prune_old_executions_task(retention_days=15, batch_size=50)

    assert result["total_deleted"] == 1
    assert Execution.objects.count() == 0


@pytest.mark.django_db
def test_prune_executions_management_command(test_job):
    now = timezone.now()
    old_time = now - timedelta(days=50)

    e = Execution.objects.create(
        job=test_job,
        external_id="exec-cmd-test",
        status=Execution.Status.SUCCESS,
        last_event_at=old_time,
    )
    Execution.objects.filter(id=e.id).update(created_at=old_time)

    # 1. Test Dry Run Command
    out_dry = io.StringIO()
    call_command("prune_executions", "--days=30", "--dry-run", stdout=out_dry)
    assert "[DRY RUN] 1 execution(s) eligible for deletion" in out_dry.getvalue()
    assert Execution.objects.count() == 1

    # 2. Test Real Pruning Command
    out_real = io.StringIO()
    call_command("prune_executions", "--days=30", "--batch-size=10", stdout=out_real)
    assert "Successfully hard-deleted 1 execution(s)" in out_real.getvalue()
    assert Execution.objects.count() == 0
