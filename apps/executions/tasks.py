import logging
from celery import shared_task
from django.conf import settings

from .services import prune_old_executions

logger = logging.getLogger(__name__)


@shared_task(name="executions.prune_old_executions")
def prune_old_executions_task(
    retention_days: int | None = None, batch_size: int | None = None
) -> dict:
    """
    Scheduled Celery task that permanently deletes historical executions older than the
    configured retention threshold (default: 30 days).
    """
    days = (
        retention_days
        if retention_days is not None
        else getattr(settings, "EXECUTIONS_RETENTION_DAYS", 30)
    )
    chunk_size = (
        batch_size
        if batch_size is not None
        else getattr(settings, "EXECUTIONS_PURGE_BATCH_SIZE", 5000)
    )

    logger.info(
        "Starting executions pruning (retention_days=%d, batch_size=%d)...", days, chunk_size
    )
    result = prune_old_executions(retention_days=days, batch_size=chunk_size, dry_run=False)
    logger.info("Executions pruning finished: %s", result)
    return result
