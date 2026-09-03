import pytest
import hmac
import hashlib
import json
from unittest.mock import patch, MagicMock
from apps.notifications.tasks import deliver_webhook_task
from apps.notifications.models import NotificationChannel, NotificationDelivery
from apps.incidents.models import IncidentEvent

pytestmark = pytest.mark.django_db


@patch("apps.notifications.tasks.requests.post")
def test_deliver_webhook_success(mock_post, project, incident):
    channel = NotificationChannel.objects.create(
        project=project,
        type=NotificationChannel.ChannelType.WEBHOOK,
        name="Webhook",
        config={"url": "https://example.com/webhook", "secret": "mysecret12345678"},
    )
    event = IncidentEvent.objects.create(
        incident=incident, event_type=IncidentEvent.EventType.CREATED
    )
    delivery = NotificationDelivery.objects.create(incident_event=event, channel=channel)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    deliver_webhook_task(delivery.id)

    delivery.refresh_from_db()
    assert delivery.status == NotificationDelivery.DeliveryStatus.SENT
    assert delivery.attempt_count == 1
    assert delivery.delivered_at is not None

    # Verify signature format in request
    args, kwargs = mock_post.call_args
    headers = kwargs["headers"]
    assert "X-BJT-Signature" in headers
    assert "X-BJT-Delivery-ID" in headers
    assert headers["X-BJT-Delivery-ID"] == str(delivery.id)
    assert "X-BJT-Timestamp" in headers

    # Calculate expected signature
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
    timestamp_str = headers["X-BJT-Timestamp"]
    signed_payload = f"{timestamp_str}." + payload_bytes.decode("utf-8")
    expected_sig = hmac.new(
        b"mysecret12345678", signed_payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert headers["X-BJT-Signature"] == expected_sig


@patch("apps.notifications.tasks.requests.post")
def test_deliver_webhook_permanent_error(mock_post, project, incident):
    channel = NotificationChannel.objects.create(
        project=project,
        type=NotificationChannel.ChannelType.WEBHOOK,
        name="Webhook",
        config={"url": "https://example.com/webhook", "secret": "mysecret12345678"},
    )
    event = IncidentEvent.objects.create(
        incident=incident, event_type=IncidentEvent.EventType.CREATED
    )
    delivery = NotificationDelivery.objects.create(incident_event=event, channel=channel)

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_post.return_value = mock_response

    deliver_webhook_task(delivery.id)

    delivery.refresh_from_db()
    assert delivery.status == NotificationDelivery.DeliveryStatus.FAILED
    assert "Permanent Error: HTTP 400" in delivery.error


@patch("apps.notifications.tasks.requests.post")
@patch("apps.notifications.tasks.deliver_webhook_task.retry")
def test_deliver_webhook_429_retry(mock_retry, mock_post, project, incident):
    mock_retry.side_effect = Exception("Retry")
    channel = NotificationChannel.objects.create(
        project=project,
        type=NotificationChannel.ChannelType.WEBHOOK,
        config={"url": "https://example.com/webhook", "secret": "mysecret12345678"},
    )
    event = IncidentEvent.objects.create(
        incident=incident, event_type=IncidentEvent.EventType.CREATED
    )
    delivery = NotificationDelivery.objects.create(incident_event=event, channel=channel)

    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "120"}
    mock_post.return_value = mock_response

    with pytest.raises(Exception, match="Retry"):
        deliver_webhook_task(delivery.id)

    mock_retry.assert_called_once()
    assert mock_retry.call_args.kwargs["countdown"] == 120


@patch("apps.notifications.tasks.requests.post")
@patch("apps.notifications.tasks.deliver_webhook_task.retry")
def test_deliver_webhook_500_retry(mock_retry, mock_post, project, incident):
    mock_retry.side_effect = Exception("Retry")
    channel = NotificationChannel.objects.create(
        project=project,
        type=NotificationChannel.ChannelType.WEBHOOK,
        config={"url": "https://example.com/webhook", "secret": "mysecret12345678"},
    )
    event = IncidentEvent.objects.create(
        incident=incident, event_type=IncidentEvent.EventType.CREATED
    )
    delivery = NotificationDelivery.objects.create(incident_event=event, channel=channel)

    mock_response = MagicMock()
    mock_response.status_code = 502
    mock_post.return_value = mock_response

    with pytest.raises(Exception, match="Retry"):
        deliver_webhook_task(delivery.id)

    mock_retry.assert_called_once()
    assert mock_retry.call_args.kwargs["countdown"] > 0


@patch("apps.notifications.tasks.send_mail")
def test_deliver_email_task_dynamic_recipients(mock_send_mail, project, incident, user):
    from apps.notifications.tasks import deliver_email_task

    channel = NotificationChannel.objects.create(
        project=project,
        type=NotificationChannel.ChannelType.EMAIL,
        name="Email Channel",
        config={"recipient_target": "ALL", "recipients": []},
    )
    event = IncidentEvent.objects.create(
        incident=incident, event_type=IncidentEvent.EventType.CREATED
    )
    delivery = NotificationDelivery.objects.create(incident_event=event, channel=channel)

    deliver_email_task(delivery.id)

    delivery.refresh_from_db()
    assert delivery.status == NotificationDelivery.DeliveryStatus.SENT
    mock_send_mail.assert_called_once()
    assert user.email in mock_send_mail.call_args.kwargs["recipient_list"]

