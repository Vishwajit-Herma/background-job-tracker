import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.db.models import Q

from .models import AlertRule
from apps.executions.analytics import get_job_analytics, get_project_analytics
from apps.incidents.models import Incident, IncidentEvent
from apps.incidents.services import auto_resolve_incident

logger = logging.getLogger(__name__)


@shared_task(name="alerts.evaluate_alert_rules")
def evaluate_alert_rules():
    """
    Evaluates all active AlertRules and manages the Incident lifecycle.
    """
    rules = (
        AlertRule.objects.filter(
            is_active=True, project__is_deleted=False, project__status="active"
        )
        .filter(Q(job__isnull=True) | Q(job__is_deleted=False, job__status="active"))
        .values_list("id", flat=True)
    )

    for rule_id in rules:
        _evaluate_single_rule_task.delay(rule_id)


@shared_task(name="alerts.evaluate_single_rule")
def _evaluate_single_rule_task(rule_id):
    try:
        rule = AlertRule.objects.get(id=rule_id, is_active=True)
    except AlertRule.DoesNotExist:
        return
    _evaluate_single_rule(rule)


def _evaluate_single_rule(rule):
    end_dt = timezone.now()
    start_dt = end_dt - timedelta(minutes=rule.window_minutes)

    # Calculate metrics
    if rule.job_id:
        metrics = get_job_analytics(rule.job_id, start_dt, end_dt)
    else:
        metrics = get_project_analytics(rule.project_id, start_dt, end_dt)

    exec_val = metrics.get("executions", 0)
    total_executions = exec_val.get("current", 0) if isinstance(exec_val, dict) else (exec_val or 0)

    # Unknown should not mean healthy. If there's no data, we don't trigger or recover.
    if total_executions == 0:
        return

    # Extract the relevant metric value
    metric_val = None
    if rule.metric == AlertRule.MetricType.FAILURE_RATE:
        val = metrics.get("failure_rate", 0.0)
        metric_val = val.get("current", 0.0) if isinstance(val, dict) else (val or 0.0)
    elif rule.metric == AlertRule.MetricType.RETRY_RATE:
        val = metrics.get("retry_rate", 0.0)
        metric_val = val.get("current", 0.0) if isinstance(val, dict) else (val or 0.0)
    elif rule.metric == AlertRule.MetricType.P95_DURATION:
        val = metrics.get("p95_duration_ms")
        p95 = val.get("current") if isinstance(val, dict) else val
        if p95 is not None:
            metric_val = p95

    # If we don't have enough data to calculate P95 (e.g. no successes), skip
    if metric_val is None:
        return

    condition_active = metric_val >= rule.threshold

    trigger_metadata = {
        "metric_type": rule.metric,
        "metric_value": metric_val,
        "threshold": rule.threshold,
        "window_minutes": rule.window_minutes,
        "evaluated_at": end_dt.isoformat(),
        "total_executions": total_executions,
    }

    with transaction.atomic():
        # Lock the alert rule row to prevent concurrent evaluations of the same rule
        locked_rule = AlertRule.objects.select_for_update().get(id=rule.id)

        # Find any existing active incident for this exact scope
        active_incident = Incident.objects.filter(
            alert_rule=locked_rule,
            project=locked_rule.project,
            job=locked_rule.job,
            status__in=[Incident.Status.OPEN, Incident.Status.ACKNOWLEDGED],
        ).first()

        if condition_active:
            if not active_incident:
                try:
                    # CREATE new incident
                    with transaction.atomic():
                        incident = Incident.objects.create(
                            alert_rule=locked_rule,
                            project=locked_rule.project,
                            job=locked_rule.job,
                            severity=locked_rule.severity,
                            trigger_metadata=trigger_metadata,
                        )
                        IncidentEvent.objects.create(
                            incident=incident,
                            event_type=IncidentEvent.EventType.CREATED,
                            metadata={"trigger_metadata": trigger_metadata},
                        )
                except IntegrityError:
                    # Another process created the incident right after we checked. That's fine.
                    pass
            else:
                # UPDATE existing incident metadata (optional, keep it fresh)
                incident = Incident.objects.select_for_update().get(id=active_incident.id)
                if incident.status in [Incident.Status.OPEN, Incident.Status.ACKNOWLEDGED]:
                    incident.trigger_metadata = trigger_metadata
                    incident.save(update_fields=["trigger_metadata", "updated_at"])
        else:
            if active_incident:
                # RECOVER / AUTO RESOLVE
                auto_resolve_incident(active_incident.id, recovery_metadata=trigger_metadata)
