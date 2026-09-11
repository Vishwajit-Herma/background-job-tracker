from django.conf import settings
from django.core.management.base import BaseCommand

from apps.executions.services import prune_old_executions


class Command(BaseCommand):
    help = "Hard delete old execution records beyond the retention threshold."

    def add_arguments(self, parser):
        default_days = getattr(settings, "EXECUTIONS_RETENTION_DAYS", 30)
        default_batch_size = getattr(settings, "EXECUTIONS_PURGE_BATCH_SIZE", 5000)

        parser.add_argument(
            "--days",
            type=int,
            default=default_days,
            help=f"Number of retention days (default: {default_days}). Executions older than this are deleted.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=default_batch_size,
            help=f"Number of executions to delete per transaction batch (default: {default_batch_size}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the deletion and output how many records would be pruned without deleting.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]

        if days < 1:
            self.stderr.write(self.style.ERROR("Error: --days must be at least 1."))
            return

        if batch_size < 1:
            self.stderr.write(self.style.ERROR("Error: --batch-size must be at least 1."))
            return

        mode_str = " (DRY RUN)" if dry_run else ""
        self.stdout.write(
            self.style.NOTICE(
                f"Starting execution pruning{mode_str} for records older than {days} days "
                f"(batch size: {batch_size})..."
            )
        )

        result = prune_old_executions(
            retention_days=days,
            batch_size=batch_size,
            dry_run=dry_run,
        )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[DRY RUN] {result['total_eligible']} execution(s) eligible for deletion "
                    f"(created before {result['cutoff'].strftime('%Y-%m-%d %H:%M:%S UTC')}). "
                    f"No records were deleted."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully hard-deleted {result['total_deleted']} execution(s) "
                    f"across {result['batches']} batch(es) "
                    f"(cutoff: {result['cutoff'].strftime('%Y-%m-%d %H:%M:%S UTC')})."
                )
            )
