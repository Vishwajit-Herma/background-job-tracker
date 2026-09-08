import logging
from datetime import timedelta
from celery import shared_task
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from apps.core.realtime import publish_realtime_event
from apps.incidents.intelligence import compute_and_save_incident_intelligence
from apps.incidents.models import Incident

logger = logging.getLogger(__name__)

STALE_MINUTES = 5
MAX_REFRESH_BATCH = 50
LOCK_TIMEOUT = 300


@shared_task(name="incidents.calculate_incident_intelligence")
def calculate_incident_intelligence_task(incident_id):
    """
    Asynchronously computes and persists IncidentIntelligence for an incident.
    Cleans up any pending in-flight lock key in cache.
    """
    try:
        intelligence = compute_and_save_incident_intelligence(incident_id)
        if intelligence:
            incident = Incident.objects.filter(id=incident_id).only("project_id").first()
            if incident:
                publish_realtime_event(
                    "incident.intelligence.updated",
                    project_id=incident.project_id,
                    payload={"incident_id": incident_id},
                )
        return bool(intelligence)
    finally:
        cache.delete(f"intelligence_calculating_{incident_id}")


@shared_task(name="incidents.refresh_active_incidents_intelligence")
def refresh_active_incidents_intelligence_task():
    """
    Periodically refreshes intelligence for open and acknowledged incidents
    whose intelligence is stale (calculated > 5m ago or missing).
    Processes in bounded batches to avoid Celery queue storms.
    """
    stale_cutoff = timezone.now() - timedelta(minutes=STALE_MINUTES)

    stale_incidents = (
        Incident.objects.filter(status__in=[Incident.Status.OPEN, Incident.Status.ACKNOWLEDGED])
        .filter(Q(intelligence__isnull=True) | Q(intelligence__calculated_at__lt=stale_cutoff))
        .values_list("id", flat=True)[:MAX_REFRESH_BATCH]
    )

    for inc_id in stale_incidents:
        # Avoid queueing duplicate if currently calculating
        lock_key = f"intelligence_calculating_{inc_id}"
        if cache.add(lock_key, True, timeout=LOCK_TIMEOUT):
            calculate_incident_intelligence_task.delay(inc_id)
