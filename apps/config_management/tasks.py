import logging
from datetime import timedelta

from celery import shared_task
from django.apps import apps
from django.core.management import call_command
from django.utils import timezone

from apps.config_management.models import AuditModel

logger = logging.getLogger(__name__)


@shared_task(name="config_management.hard_delete_soft_deleted_records")
def hard_delete_soft_deleted_records():
    """
    Finds all models that inherit from AuditModel and permanently deletes
    records where `is_deleted=True` and `deleted_at` is older than 30 days.

    This helps keep the database clean while maintaining a 30-day grace period
    for accidental soft-deletes.
    """
    # Threshold is 30 days ago
    threshold_date = timezone.now() - timedelta(days=30)
    total_deleted = 0

    # Iterate over all registered Django models
    for model in apps.get_models():
        # Check if the model inherits from AuditModel and is not the abstract class itself
        if issubclass(model, AuditModel) and model is not AuditModel:
            # Use deleted_objects manager to reliably access soft-deleted records
            if hasattr(model, "deleted_objects"):
                qs = model.deleted_objects.filter(deleted_at__lte=threshold_date)
            elif hasattr(model, "all_objects"):
                qs = model.all_objects.filter(is_deleted=True, deleted_at__lte=threshold_date)
            else:
                # Fallback to the base manager if custom managers are missing
                qs = model._base_manager.filter(is_deleted=True, deleted_at__lte=threshold_date)

            try:
                count, _ = qs.delete()  # Hard delete them from the database

                if count > 0:
                    logger.info("Hard deleted %d records from %s.", count, model.__name__)
                    total_deleted += count
            except Exception:
                logger.exception("Failed to hard delete records for %s", model.__name__)

    logger.info("Total hard deleted records across all models: %d", total_deleted)
    return total_deleted


@shared_task(name="config_management.clear_expired_sessions")
def clear_expired_sessions():
    """
    Cleans up expired user sessions from the django_session database table.
    """
    try:
        call_command("clearsessions")
        logger.info("Expired sessions cleared successfully.")
    except Exception:
        logger.exception("Failed to clear expired sessions.")
