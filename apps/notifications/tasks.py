import hmac
import hashlib
import json
import logging
import requests
import smtplib
from requests.exceptions import RequestException
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q
from django.db import transaction

from apps.notifications.models import NotificationDelivery, NotificationChannel, InAppNotification

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5)
def deliver_webhook_task(self, delivery_id):
    """
    Delivers a webhook notification for a given NotificationDelivery.
    Handles signing the payload with HMAC-SHA256, sending the HTTP POST,
    and managing retry logic for rate limits and server errors.
    """
    try:
        delivery = NotificationDelivery.objects.select_related(
            "channel",
            "incident_event__incident",
            "incident_event__incident__job",
            "incident_event__incident__project",
        ).get(id=delivery_id)
    except NotificationDelivery.DoesNotExist:
        return

    if delivery.status != NotificationDelivery.DeliveryStatus.PENDING:
        logger.info(
            f"Delivery {delivery_id} already processed (status: {delivery.status}). Skipping."
        )
        return

    # Update attempt tracking
    delivery.attempt_count += 1
    delivery.last_attempt_at = timezone.now()
    delivery.save(update_fields=["attempt_count", "last_attempt_at"])

    event = delivery.incident_event
    incident = event.incident

    payload = {
        "event": event.event_type,
        "timestamp": event.event_time.isoformat(),
        "incident": {
            "id": incident.id,
            "project_id": incident.project_id,
            "job_id": incident.job_id,
            "severity": incident.severity,
            "status": incident.status,
        },
        "trigger": incident.trigger_metadata,
    }

    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    secret = delivery.channel.config.get("secret", "")
    url = delivery.channel.config.get("url", "")
    timestamp_str = timezone.now().isoformat()

    signed_payload = f"{timestamp_str}." + payload_bytes.decode("utf-8")
    signature = hmac.new(
        secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-BJT-Event": event.event_type,
        "X-BJT-Timestamp": timestamp_str,
        "X-BJT-Signature": signature,
        "X-BJT-Delivery-ID": str(delivery.id),
    }

    try:
        response = requests.post(url, data=payload_bytes, headers=headers, timeout=10)

        if response.status_code == 429:
            # Rate limited, respect Retry-After header if present
            retry_after = response.headers.get("Retry-After")
            countdown = (
                int(retry_after)
                if retry_after and retry_after.isdigit()
                else 2**self.request.retries
            )
            try:
                raise self.retry(exc=Exception("HTTP 429 Rate Limited"), countdown=countdown)
            except self.MaxRetriesExceededError:
                delivery.status = NotificationDelivery.DeliveryStatus.FAILED
                delivery.error = "Max retries exceeded. Last error: HTTP 429 Rate Limited"
                delivery.save(update_fields=["status", "error"])
                return

        elif 500 <= response.status_code < 600:
            # Server errors - retryable
            countdown = 2**self.request.retries
            try:
                raise self.retry(
                    exc=Exception(f"HTTP {response.status_code} Server Error"), countdown=countdown
                )
            except self.MaxRetriesExceededError:
                delivery.status = NotificationDelivery.DeliveryStatus.FAILED
                delivery.error = (
                    f"Max retries exceeded. Last error: HTTP {response.status_code} Server Error"
                )
                delivery.save(update_fields=["status", "error"])
                return

        elif 400 <= response.status_code < 500:
            # Permanent client errors
            delivery.status = NotificationDelivery.DeliveryStatus.FAILED
            delivery.error = f"Permanent Error: HTTP {response.status_code} - {response.text}"
            delivery.save(update_fields=["status", "error"])
            return

        response.raise_for_status()

        # Success
        delivery.status = NotificationDelivery.DeliveryStatus.SENT
        delivery.delivered_at = timezone.now()
        delivery.save(update_fields=["status", "delivered_at"])

    except RequestException as e:
        # Network errors, timeouts - retryable
        countdown = 2**self.request.retries
        try:
            self.retry(exc=e, countdown=countdown)
        except self.MaxRetriesExceededError:
            delivery.status = NotificationDelivery.DeliveryStatus.FAILED
            delivery.error = f"Max retries exceeded. Last error: {str(e)}"
            delivery.save(update_fields=["status", "error"])


@shared_task(bind=True, max_retries=5)
def deliver_email_task(self, delivery_id):
    """
    Delivers an email notification for a given NotificationDelivery.
    Handles categorizing smtplib exceptions for retry logic.
    """
    try:
        delivery = NotificationDelivery.objects.select_related(
            "channel", "incident_event__incident"
        ).get(id=delivery_id)
    except NotificationDelivery.DoesNotExist:
        return

    if delivery.status != NotificationDelivery.DeliveryStatus.PENDING:
        logger.info(
            f"Delivery {delivery_id} already processed (status: {delivery.status}). Skipping."
        )
        return

    delivery.attempt_count += 1
    delivery.last_attempt_at = timezone.now()
    delivery.save(update_fields=["attempt_count", "last_attempt_at"])

    event = delivery.incident_event
    incident = event.incident
    recipients = delivery.channel.config.get("recipients", [])

    if not recipients:
        delivery.status = NotificationDelivery.DeliveryStatus.FAILED
        delivery.error = "Permanent Error: No recipients configured."
        delivery.save(update_fields=["status", "error"])
        return

    actor_name = (
        event.actor.get_full_name() or event.actor.email
        if event.actor
        else event.metadata.get("resolved_by_name")
        or event.metadata.get("acknowledged_by_name")
        or event.metadata.get("reopened_by_name")
        or "System"
    )
    job_name = incident.job.name if incident.job else "Project-level"

    subject = f"[{incident.get_severity_display()}] Incident #{incident.id} - {event.get_event_type_display()} ({incident.project.name})"
    message = f"""Incident Notification

Incident: #{incident.id}
Event: {event.get_event_type_display()}
Project: {incident.project.name}
Job: {job_name}
Severity: {incident.get_severity_display()}
Status: {incident.get_status_display()}
Action by: {actor_name}
Timestamp: {event.event_time.strftime("%Y-%m-%d %H:%M:%S UTC")}
"""
    if event.event_type == "ASSIGNED" and event.metadata.get("new_assignee_name"):
        message += f"Assigned to: {event.metadata.get('new_assignee_name')}\n"

    try:
        sent = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )

        if sent:
            delivery.status = NotificationDelivery.DeliveryStatus.SENT
            delivery.delivered_at = timezone.now()
            delivery.save(update_fields=["status", "delivered_at"])
        else:
            # Permanent failure assuming invalid config
            delivery.status = NotificationDelivery.DeliveryStatus.FAILED
            delivery.error = "Permanent Error: send_mail returned 0."
            delivery.save(update_fields=["status", "error"])

    except Exception as e:
        # Categorize email exceptions
        error_msg = str(e)
        if isinstance(
            e,
            (
                smtplib.SMTPAuthenticationError,
                smtplib.SMTPRecipientsRefused,
                smtplib.SMTPDataError,
                smtplib.SMTPSenderRefused,
            ),
        ):
            delivery.status = NotificationDelivery.DeliveryStatus.FAILED
            delivery.error = f"Permanent Error: {error_msg}"
            delivery.save(update_fields=["status", "error"])
            return

        # Temporary failure, let's assume SMTP connection issues are retryable
        countdown = 2**self.request.retries
        try:
            self.retry(exc=e, countdown=countdown)
        except self.MaxRetriesExceededError:
            delivery.status = NotificationDelivery.DeliveryStatus.FAILED
            delivery.error = f"Max retries exceeded. Last error: {str(e)}"
            delivery.save(update_fields=["status", "error"])


@shared_task(name="notifications.recover_orphaned_deliveries")
def recover_orphaned_deliveries():
    """
    Finds PENDING NotificationDeliveries older than 15 minutes and
    requeues them for delivery. This handles cases where the worker
    crashed before or during the initial queue dispatch.
    """
    threshold = timezone.now() - timezone.timedelta(minutes=15)

    with transaction.atomic():
        orphans = list(
            NotificationDelivery.objects.filter(
                Q(status=NotificationDelivery.DeliveryStatus.PENDING)
                & (
                    Q(last_attempt_at__lt=threshold)
                    | Q(last_attempt_at__isnull=True, created_at__lt=threshold)
                )
            )
            .select_related("channel")
            .select_for_update(skip_locked=True)
        )

        if not orphans:
            return

        # Prevent concurrent recovery tasks from picking these up immediately
        now = timezone.now()
        NotificationDelivery.objects.filter(id__in=[d.id for d in orphans]).update(
            last_attempt_at=now
        )

        for delivery in orphans:
            if delivery.channel.type == NotificationChannel.ChannelType.WEBHOOK:
                deliver_webhook_task.delay(delivery.id)
            elif delivery.channel.type == NotificationChannel.ChannelType.EMAIL:
                deliver_email_task.delay(delivery.id)


@shared_task(name="notifications.cleanup_old_notifications")
def cleanup_old_notifications():
    """
    Hard deletes notifications (InApp, Delivery) that are older than 30 days
    to prevent database bloat over time.
    """
    cutoff = timezone.now() - timezone.timedelta(days=30)

    deleted_deliveries, _ = NotificationDelivery.objects.filter(created_at__lt=cutoff).delete()
    deleted_in_app, _ = InAppNotification.objects.filter(created_at__lt=cutoff).delete()

    logger.info(
        f"Cleanup old notifications: deleted {deleted_deliveries} deliveries "
        f"and {deleted_in_app} in-app notifications."
    )
    return deleted_deliveries + deleted_in_app
