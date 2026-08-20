from django.db import transaction
from django.utils import timezone

from apps.jobs.models import Job
from .models import Execution


def ingest_executions_batch(project, executions_data):
    """
    Idempotent, highly-optimized batch ingestion pipeline using strict event chronology.
    """
    if not executions_data:
        return {"accepted": 0, "duplicates": 0, "rejected": 0}

    now = timezone.now()

    # 1. Group events by (task_identifier, external_id)
    # The SDK may send multiple events for the same execution.
    grouped_events = {}
    for item in executions_data:
        key = (item["task_identifier"], item["external_id"])
        if key not in grouped_events:
            grouped_events[key] = []
        grouped_events[key].append(item)

    unique_items = []
    duplicates = 0
    accepted = 0
    rejected = 0

    # 2. Sort intra-batch and deduplicate
    for _key, items in grouped_events.items():
        items.sort(key=lambda x: x["event_timestamp"])

        merged_item = dict(items[0])
        merged_item["_event_count"] = 1
        for idx in range(1, len(items)):
            item = items[idx]
            if item["event_timestamp"] <= merged_item["event_timestamp"]:
                duplicates += 1
                continue

            merged_item["_event_count"] += 1

            # Chronologically newer item overwrites fields
            for k, val in item.items():
                if k == "metadata":
                    merged_item["metadata"] = {**merged_item.get("metadata", {}), **(val or {})}
                elif k == "retry_count" and val is not None:
                    merged_item["retry_count"] = max(merged_item.get("retry_count", 0), val)
                else:
                    if val not in (None, ""):
                        merged_item[k] = val
        unique_items.append(merged_item)

    # 3. Extract unique task identifiers
    task_identifiers = list({item["task_identifier"] for item in unique_items})

    with transaction.atomic():
        # 4. Bulk resolve Jobs
        existing_jobs = list(
            Job.objects.filter(project=project, task_identifier__in=task_identifiers)
        )

        existing_job_ids = {job.task_identifier: job for job in existing_jobs}
        missing_identifiers = set(task_identifiers) - set(existing_job_ids.keys())

        # 5. Create missing Jobs
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

        # 6. Bulk resolve existing Executions
        job_ids = [job.id for job in job_map.values()]
        external_ids = [item["external_id"] for item in unique_items]

        existing_executions = Execution.objects.select_for_update().filter(
            job_id__in=job_ids, external_id__in=external_ids
        )

        existing_exec_map = {(exec.job_id, exec.external_id): exec for exec in existing_executions}

        executions_to_create = []
        executions_to_update = []

        update_fields = {
            "status",
            "started_at",
            "finished_at",
            "duration_ms",
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

        verified_job_ids = set()

        # 7. Merge state and build create/update lists
        for item in unique_items:
            event_count = item.pop("_event_count", 1)
            ext_id = item["external_id"]
            job = job_map.get(item["task_identifier"])

            if not job or job.status != Job.Status.ACTIVE or job.is_deleted:
                rejected += event_count
                continue

            exec_key = (job.id, ext_id)
            if exec_key in existing_exec_map:
                exec_obj = existing_exec_map[exec_key]

                # Check chronological ordering
                if item["event_timestamp"] <= exec_obj.last_event_at:
                    duplicates += event_count
                    continue

                exec_obj.last_event_at = item["event_timestamp"]
                exec_obj.status = item["status"]

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

                exec_obj.updated_at = now
                executions_to_update.append(exec_obj)
                accepted += event_count
                verified_job_ids.add(job.id)
            else:
                duration_ms = item.get("duration_ms")
                if duration_ms is None and item.get("started_at") and item.get("finished_at"):
                    duration_ms = max(
                        0, int((item["finished_at"] - item["started_at"]).total_seconds() * 1000)
                    )

                exec_obj = Execution(
                    job=job,
                    external_id=ext_id,
                    status=item["status"],
                    last_event_at=item["event_timestamp"],
                    started_at=item.get("started_at"),
                    finished_at=item.get("finished_at"),
                    duration_ms=duration_ms,
                    queue=item.get("queue", ""),
                    worker=item.get("worker", ""),
                    retry_count=item.get("retry_count", 0),
                    error_type=item.get("error_type", ""),
                    error_message=item.get("error_message", ""),
                    traceback=item.get("traceback", ""),
                    metadata=item.get("metadata", {}),
                )
                executions_to_create.append(exec_obj)
                accepted += event_count
                verified_job_ids.add(job.id)

        # 8. Bulk Commit
        if executions_to_create:
            # We explicitly do NOT use ignore_conflicts=True here.
            # If a concurrent request created the Execution, we WANT an IntegrityError
            # to roll back the transaction. The SDK will retry, and on retry, it will
            # follow the safe update path which respects chronological last_event_at.
            executions_to_create.sort(key=lambda x: x.external_id)
            Execution.objects.bulk_create(executions_to_create)

        if executions_to_update:
            executions_to_update.sort(key=lambda x: x.external_id)
            Execution.objects.bulk_update(executions_to_update, fields=list(update_fields))

        # Optional: ensure verification status is updated if any jobs were originally UNVERIFIED
        if verified_job_ids:
            Job.objects.filter(
                id__in=verified_job_ids, verification_status=Job.VerificationStatus.UNVERIFIED
            ).update(verification_status=Job.VerificationStatus.VERIFIED, last_verified_at=now)

    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}
