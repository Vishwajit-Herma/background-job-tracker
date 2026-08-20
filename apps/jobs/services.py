from django.utils import timezone
from django.db import transaction
from .models import Job, TaskRegistry


def sync_task_registry(project, task_identifiers):
    """
    Synchronizes a batch of discovered Celery tasks from the SDK.
    - Upserts TaskRegistry records for the discovered tasks.
    - Idempotently creates Jobs for new tasks.
    - Updates verification status for existing unverified Jobs.
    """
    # 1. Deduplicate identifiers
    unique_identifiers = list(set(task_identifiers))
    if not unique_identifiers:
        return

    now = timezone.now()

    with transaction.atomic():
        # 2. Upsert TaskRegistry records (Optimized: 1 query)
        registry_records = [
            TaskRegistry(project=project, task_identifier=identifier, last_seen_at=now)
            for identifier in unique_identifiers
        ]

        # update_conflicts=True maps to Postgres ON CONFLICT DO UPDATE
        TaskRegistry.objects.bulk_create(
            registry_records,
            update_conflicts=True,
            unique_fields=["project", "task_identifier"],
            update_fields=["last_seen_at"],
        )

        # 3. Update existing Jobs that were UNVERIFIED to VERIFIED (Optimized: 1 query)
        Job.objects.filter(
            project=project,
            task_identifier__in=unique_identifiers,
            verification_status=Job.VerificationStatus.UNVERIFIED,
        ).update(verification_status=Job.VerificationStatus.VERIFIED, last_verified_at=now)

        # 4. Find which tasks don't have a Job yet (Optimized: 1 query)
        existing_job_identifiers = set(
            Job.objects.filter(project=project, task_identifier__in=unique_identifiers).values_list(
                "task_identifier", flat=True
            )
        )

        new_identifiers = set(unique_identifiers) - existing_job_identifiers

        # 5. Bulk create new jobs (Optimized: 1 query)
        if new_identifiers:
            new_jobs = [
                Job(
                    project=project,
                    task_identifier=identifier,
                    name=identifier.split(".")[-1].replace("_", " ").title(),
                    status=Job.Status.ACTIVE,
                    verification_status=Job.VerificationStatus.VERIFIED,
                    last_verified_at=now,
                )
                for identifier in new_identifiers
            ]

            # ignore_conflicts=True handles race conditions safely (ON CONFLICT DO NOTHING)
            Job.objects.bulk_create(new_jobs, ignore_conflicts=True)
