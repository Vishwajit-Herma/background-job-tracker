import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.realtime import publish_execution_batch
from apps.jobs.models import Job
from .models import Execution, ExecutionEvent

logger = logging.getLogger(__name__)


def ingest_executions_batch(project, executions_data):
    """
    Idempotent, highly-optimized batch ingestion pipeline using strict event chronology.

    Equal Timestamp Policy:
    When two events for the same Execution have identical `event_timestamp`, persist both
    events as history, but use deterministic input/event ordering to determine the snapshot.
    `event_id` is not inherently chronological unless the SDK guarantees it.

    Metrics Note:
    `accepted/duplicates` counts are request-level processing metrics and may not precisely
    reflect cross-request race outcomes under concurrent ingestion. Accepted counts successfully
    persisted telemetry events, not Execution rows updated.
    """
    if not executions_data:
        return {"accepted": 0, "duplicates": 0, "rejected": 0}

    now = timezone.now()

    # 1. Extract unique task identifiers
    task_identifiers = list({item["task_identifier"] for item in executions_data})

    with transaction.atomic():
        # 2. Bulk resolve Jobs
        existing_jobs = list(
            Job.objects.filter(project=project, task_identifier__in=task_identifiers)
        )

        existing_job_ids = {job.task_identifier: job for job in existing_jobs}
        missing_identifiers = set(task_identifiers) - set(existing_job_ids.keys())

        # 3. Create missing Jobs
        if missing_identifiers:
            sorted_identifiers = sorted(missing_identifiers)
            new_jobs = [
                Job(
                    project=project,
                    task_identifier=identifier,
                    name=identifier.split(".")[-1].replace("_", " ").title(),
                    status=Job.Status.ACTIVE,
                    verification_status=Job.VerificationStatus.VERIFIED,
                    last_verified_at=now,
                )
                for identifier in sorted_identifiers
            ]
            Job.objects.bulk_create(new_jobs, ignore_conflicts=True)

            # Fetch all required Jobs to get their DB IDs
            all_jobs = Job.objects.filter(project=project, task_identifier__in=task_identifiers)
            job_map = {job.task_identifier: job for job in all_jobs}
        else:
            job_map = existing_job_ids

        rejected = 0
        valid_events = []
        for item in executions_data:
            job = job_map.get(item["task_identifier"])
            if not job or job.status != Job.Status.ACTIVE or job.is_deleted:
                rejected += 1
            else:
                valid_events.append((job, item))

        if not valid_events:
            return {"accepted": 0, "duplicates": 0, "rejected": rejected}

        job_ids = list({job.id for job, _ in valid_events})
        external_ids = list({item["external_id"] for _, item in valid_events})

        # 4. Bulk resolve existing Executions
        existing_executions = Execution.objects.select_for_update().filter(
            job_id__in=job_ids, external_id__in=external_ids
        )
        existing_exec_map = {(exec.job_id, exec.external_id): exec for exec in existing_executions}
        existing_exec_ids = [exec.id for exec in existing_executions]

        # 5. Fetch existing event IDs to count HTTP retry duplicates
        event_ids = [item["event_id"] for _, item in valid_events]
        existing_event_ids = set(
            ExecutionEvent.objects.filter(
                execution_id__in=existing_exec_ids, event_id__in=event_ids
            ).values_list("execution_id", "event_id")
        )

        executions_to_create = []
        executions_to_update = []

        # Group valid events by (job.id, external_id)
        exec_grouped_events = {}
        for job, item in valid_events:
            key = (job.id, item["external_id"])
            if key not in exec_grouped_events:
                exec_grouped_events[key] = []
            exec_grouped_events[key].append(item)

        accepted = 0
        duplicates = 0
        verified_job_ids = set()

        events_to_create_later = []

        update_fields = {
            "status",
            "started_at",
            "finished_at",
            "duration_ms",
            "framework",
            "queue",
            "worker",
            "retry_count",
            "error_type",
            "error_message",
            "traceback",
            "metadata",
            "last_event_at",
            "updated_at",
        }

        # 6. Group -> sort -> remove repeated event_id -> process chronologically
        for key, items in exec_grouped_events.items():
            job_id, ext_id = key
            job = job_map[items[0]["task_identifier"]]

            existing_exec = existing_exec_map.get(key)
            exec_id = existing_exec.id if existing_exec else None

            items.sort(key=lambda x: x["event_timestamp"])

            seen_in_batch = set()
            unique_items = []
            for item in items:
                if (exec_id and (exec_id, item["event_id"]) in existing_event_ids) or item[
                    "event_id"
                ] in seen_in_batch:
                    duplicates += 1
                else:
                    seen_in_batch.add(item["event_id"])
                    unique_items.append(item)
                    accepted += 1
                    verified_job_ids.add(job.id)

            if not unique_items:
                continue

            if key in existing_exec_map:
                exec_obj = existing_exec_map[key]
                has_updates = False

                for item in unique_items:
                    events_to_create_later.append((exec_obj, item))

                    if item["event_timestamp"] > exec_obj.last_event_at:
                        exec_obj.last_event_at = item["event_timestamp"]
                        exec_obj.status = item["status"]
                        has_updates = True

                        duration_ms = item.get("duration_ms")
                        if duration_ms is None:
                            start = item.get("started_at") or exec_obj.started_at
                            finish = item.get("finished_at") or exec_obj.finished_at
                            if start and finish:
                                duration_ms = max(0, int((finish - start).total_seconds() * 1000))

                        if item.get("started_at"):
                            exec_obj.started_at = item["started_at"]
                        if item.get("finished_at"):
                            exec_obj.finished_at = item["finished_at"]
                        if duration_ms is not None:
                            exec_obj.duration_ms = duration_ms
                        if item.get("framework"):
                            exec_obj.framework = item["framework"]
                        if item.get("queue"):
                            exec_obj.queue = item["queue"]
                        if item.get("worker"):
                            exec_obj.worker = item["worker"]
                        if item.get("retry_count") is not None:
                            exec_obj.retry_count = max(exec_obj.retry_count, item["retry_count"])

                        if exec_obj.status == Execution.Status.SUCCESS:
                            exec_obj.error_type = ""
                            exec_obj.error_message = ""
                            exec_obj.traceback = ""
                        else:
                            if item.get("error_type"):
                                exec_obj.error_type = item["error_type"]
                            if item.get("error_message"):
                                exec_obj.error_message = item["error_message"]
                            if item.get("traceback"):
                                exec_obj.traceback = item["traceback"]

                        if item.get("metadata"):
                            exec_obj.metadata = {**exec_obj.metadata, **item["metadata"]}

                    elif item["event_timestamp"] == exec_obj.last_event_at:
                        # Equal timestamp: preserve snapshot status, but merge metadata/retry_counts
                        if (
                            item.get("retry_count") is not None
                            and item["retry_count"] > exec_obj.retry_count
                        ):
                            exec_obj.retry_count = item["retry_count"]
                            has_updates = True
                        if item.get("metadata"):
                            exec_obj.metadata = {**exec_obj.metadata, **item["metadata"]}
                            has_updates = True

                if has_updates:
                    exec_obj.updated_at = now
                    executions_to_update.append(exec_obj)
            else:
                # Build the initial execution state sequentially
                merged_item = dict(unique_items[0])
                for item in unique_items[1:]:
                    if item["event_timestamp"] > merged_item["event_timestamp"]:
                        for k, val in item.items():
                            if k == "metadata":
                                merged_item["metadata"] = {
                                    **merged_item.get("metadata", {}),
                                    **(val or {}),
                                }
                            elif k == "retry_count" and val is not None:
                                merged_item["retry_count"] = max(
                                    merged_item.get("retry_count", 0), val
                                )
                            else:
                                if val not in (None, ""):
                                    merged_item[k] = val
                    else:
                        # Older events cannot change the snapshot's chronological state,
                        # but retry_count and metadata are retained as aggregate telemetry.
                        merged_item["retry_count"] = max(
                            merged_item.get("retry_count", 0), item.get("retry_count", 0)
                        )
                        merged_item["metadata"] = {
                            **merged_item.get("metadata", {}),
                            **(item.get("metadata") or {}),
                        }

                duration_ms = merged_item.get("duration_ms")
                if (
                    duration_ms is None
                    and merged_item.get("started_at")
                    and merged_item.get("finished_at")
                ):
                    duration_ms = max(
                        0,
                        int(
                            (merged_item["finished_at"] - merged_item["started_at"]).total_seconds()
                            * 1000
                        ),
                    )

                exec_obj = Execution(
                    job=job,
                    external_id=ext_id,
                    status=merged_item["status"],
                    last_event_at=merged_item["event_timestamp"],
                    started_at=merged_item.get("started_at"),
                    finished_at=merged_item.get("finished_at"),
                    duration_ms=duration_ms,
                    framework=merged_item.get("framework", ""),
                    queue=merged_item.get("queue", ""),
                    worker=merged_item.get("worker", ""),
                    retry_count=merged_item.get("retry_count", 0),
                    error_type=merged_item.get("error_type", ""),
                    error_message=merged_item.get("error_message", ""),
                    traceback=merged_item.get("traceback", ""),
                    metadata=merged_item.get("metadata", {}),
                )
                executions_to_create.append(exec_obj)

                for item in unique_items:
                    events_to_create_later.append((exec_obj, item))

        # 7. Bulk Commit Executions
        if executions_to_create:
            executions_to_create.sort(key=lambda x: x.external_id)
            Execution.objects.bulk_create(executions_to_create)

        if executions_to_update:
            executions_to_update.sort(key=lambda x: x.external_id)
            Execution.objects.bulk_update(executions_to_update, fields=list(update_fields))

        # 8. Create ExecutionEvents
        new_events = []
        for exec_obj, item in events_to_create_later:
            duration_ms = item.get("duration_ms")
            if duration_ms is None and item.get("started_at") and item.get("finished_at"):
                duration_ms = max(
                    0, int((item["finished_at"] - item["started_at"]).total_seconds() * 1000)
                )

            new_events.append(
                ExecutionEvent(
                    execution=exec_obj,
                    event_id=item["event_id"],
                    status=item["status"],
                    event_timestamp=item["event_timestamp"],
                    received_at=now,
                    started_at=item.get("started_at"),
                    finished_at=item.get("finished_at"),
                    duration_ms=duration_ms,
                    framework=item.get("framework", ""),
                    queue=item.get("queue", ""),
                    worker=item.get("worker", ""),
                    retry_count=item.get("retry_count", 0),
                    error_type=item.get("error_type", ""),
                    error_message=item.get("error_message", ""),
                    traceback=item.get("traceback", ""),
                    metadata=item.get("metadata", {}),
                )
            )

        if new_events:
            ExecutionEvent.objects.bulk_create(new_events, ignore_conflicts=True)

        if verified_job_ids:
            Job.objects.filter(
                id__in=verified_job_ids, verification_status=Job.VerificationStatus.UNVERIFIED
            ).update(verification_status=Job.VerificationStatus.VERIFIED, last_verified_at=now)

        # Auto-recover active STALLED_EXECUTION findings for executions that reached a terminal status
        terminal_exec_ids = [
            e.id
            for e in (executions_to_update + executions_to_create)
            if getattr(e, "id", None)
            and e.status
            in [Execution.Status.SUCCESS, Execution.Status.FAILED, Execution.Status.CANCELLED]
        ]
        if terminal_exec_ids:
            try:
                from apps.reliability.evaluators import _recover_finding
                from apps.reliability.models import ReliabilityFinding

                stalled_findings = ReliabilityFinding.objects.filter(
                    execution_id__in=terminal_exec_ids,
                    condition_type=ReliabilityFinding.ConditionType.STALLED_EXECUTION,
                    status=ReliabilityFinding.Status.ACTIVE,
                ).select_related("execution")
                for sf in stalled_findings:
                    _recover_finding(
                        sf,
                        {
                            "condition_type": ReliabilityFinding.ConditionType.STALLED_EXECUTION,
                            "recovered_at": now.isoformat(),
                            "execution_id": sf.execution_id,
                            "final_status": sf.execution.status if sf.execution else None,
                            "auto_recovered_on_ingest": True,
                        },
                    )
            except Exception:
                logger.exception("Failed to auto-recover stalled findings during ingestion")

        if accepted > 0:
            affected_job_ids = list(job_ids)
            publish_execution_batch(
                project_id=project.id,
                count=accepted,
                job_ids=affected_job_ids,
            )

    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}


def prune_old_executions(
    retention_days: int = 30,
    batch_size: int = 5000,
    dry_run: bool = False,
) -> dict:
    """
    Hard deletes Execution records older than `retention_days`.
    Cascades automatically to child ExecutionEvent records.

    To prevent PostgreSQL table locks and memory exhaustion under high volume,
    deletion is processed in transactional chunks of size `batch_size`.
    """
    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    cutoff = timezone.now() - timedelta(days=retention_days)
    total_eligible = Execution.objects.filter(created_at__lt=cutoff).count()

    if dry_run or total_eligible == 0:
        logger.info(
            "Prune executions (dry_run=%s): %d executions eligible for deletion (older than %s).",
            dry_run,
            total_eligible,
            cutoff.isoformat(),
        )
        return {
            "total_deleted": 0,
            "total_eligible": total_eligible,
            "cutoff": cutoff,
            "batches": 0,
        }

    total_deleted = 0
    batches = 0

    while True:
        batch_ids = list(
            Execution.objects.filter(created_at__lt=cutoff).values_list("id", flat=True)[
                :batch_size
            ]
        )
        if not batch_ids:
            break

        with transaction.atomic():
            _, breakdown = Execution.objects.filter(id__in=batch_ids).delete()
            execs_deleted = breakdown.get("executions.Execution", len(batch_ids))
            total_deleted += execs_deleted
            batches += 1

    logger.info(
        "Prune executions completed: hard-deleted %d executions across %d batch(es) (cutoff=%s).",
        total_deleted,
        batches,
        cutoff.isoformat(),
    )

    return {
        "total_deleted": total_deleted,
        "total_eligible": total_eligible,
        "cutoff": cutoff,
        "batches": batches,
    }
