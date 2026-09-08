import pytest
from unittest.mock import patch
from django.db import transaction
from apps.notifications.services import dispatch_incident_event
from apps.notifications.models import (
    NotificationChannel,
    NotificationPolicy,
    InAppNotification,
    NotificationDelivery,
)
from apps.incidents.models import IncidentEvent

pytestmark = pytest.mark.django_db


@patch("apps.notifications.services.deliver_webhook_task.delay")
@patch("apps.notifications.services.deliver_email_task.delay")
def test_dispatch_incident_event(mock_email, mock_webhook, project, incident, team_member):
    # Ensure team member has user
    user = team_member.user

    channel_in_app = NotificationChannel.objects.create(
        project=project, type=NotificationChannel.ChannelType.IN_APP, name="In-App"
    )
    channel_webhook = NotificationChannel.objects.create(
        project=project, type=NotificationChannel.ChannelType.WEBHOOK, name="Webhook"
    )

    NotificationPolicy.objects.create(
        project=project,
        channel=channel_in_app,
        severity=incident.severity,
        event_types=[IncidentEvent.EventType.CREATED],
    )
    NotificationPolicy.objects.create(
        project=project,
        channel=channel_webhook,
        severity=incident.severity,
        event_types=[IncidentEvent.EventType.CREATED],
    )

    event = IncidentEvent.objects.create(
        incident=incident, event_type=IncidentEvent.EventType.CREATED
    )

    dispatch_incident_event(event.id)

    # Check IN_APP
    assert InAppNotification.objects.filter(recipient=user, incident_event=event).exists()

    # Check WEBHOOK
    delivery = NotificationDelivery.objects.get(incident_event=event, channel=channel_webhook)
    assert delivery.status == NotificationDelivery.DeliveryStatus.PENDING
    mock_webhook.assert_called_once_with(delivery.id)
    mock_email.assert_not_called()

    # Test duplicate dispatch doesn't duplicate in-app
    dispatch_incident_event(event.id)
    assert InAppNotification.objects.filter(recipient=user, incident_event=event).count() == 1


@patch("apps.notifications.services.deliver_webhook_task.delay")
def test_dispatch_inactive_policy_or_channel(mock_webhook, project, incident, team_member):
    channel = NotificationChannel.objects.create(
        project=project, type=NotificationChannel.ChannelType.WEBHOOK, name="Webhook"
    )
    policy = NotificationPolicy.objects.create(
        project=project,
        channel=channel,
        severity=incident.severity,
        event_types=[IncidentEvent.EventType.CREATED],
    )

    event = IncidentEvent.objects.create(
        incident=incident, event_type=IncidentEvent.EventType.CREATED
    )

    # Inactive policy
    policy.is_active = False
    policy.save()
    dispatch_incident_event(event.id)
    assert not NotificationDelivery.objects.filter(incident_event=event).exists()

    # Active policy, but inactive channel
    policy.is_active = True
    policy.save()
    channel.is_active = False
    channel.save()
    dispatch_incident_event(event.id)
    assert not NotificationDelivery.objects.filter(incident_event=event).exists()


@patch("apps.incidents.services.dispatch_incident_event_task.delay")
def test_transaction_rollback_no_dispatch(mock_dispatch_task, project, incident, user):
    from apps.incidents.services import acknowledge_incident

    NotificationChannel.objects.create(
        project=project, type=NotificationChannel.ChannelType.WEBHOOK, name="Webhook"
    )

    try:
        with transaction.atomic():
            acknowledge_incident(incident.id, user)
            # Force a rollback
            raise Exception("Force rollback")
    except Exception:
        pass

    assert IncidentEvent.objects.count() == 0
    mock_dispatch_task.assert_not_called()


@patch("apps.notifications.services.dispatch_incident_event")
def test_dispatch_incident_event_task(mock_dispatch):
    from apps.notifications.tasks import dispatch_incident_event_task

    dispatch_incident_event_task(42)
    mock_dispatch.assert_called_once_with(42)


@patch("apps.notifications.services.deliver_webhook_task.delay")
def test_dispatch_multiple_event_types_policy(mock_webhook, project, incident):
    channel = NotificationChannel.objects.create(
        project=project, type=NotificationChannel.ChannelType.WEBHOOK, name="Webhook"
    )
    # Policy with multiple types
    NotificationPolicy.objects.create(
        project=project,
        channel=channel,
        severity=incident.severity,
        event_types=[IncidentEvent.EventType.CREATED, IncidentEvent.EventType.MANUALLY_RESOLVED],
    )

    event = IncidentEvent.objects.create(
        incident=incident, event_type=IncidentEvent.EventType.MANUALLY_RESOLVED
    )

    dispatch_incident_event(event.id)

    # Should match because RESOLVED is in the event_types list
    assert NotificationDelivery.objects.filter(incident_event=event, channel=channel).exists()


@patch("apps.notifications.services.deliver_webhook_task.delay")
@patch("apps.notifications.services.deliver_email_task.delay")
def test_dispatch_all_channels_simultaneously(
    mock_email, mock_webhook, project, incident, team_member
):
    user = team_member.user

    channel_in_app = NotificationChannel.objects.create(
        project=project, type=NotificationChannel.ChannelType.IN_APP, name="In-App"
    )
    channel_webhook = NotificationChannel.objects.create(
        project=project, type=NotificationChannel.ChannelType.WEBHOOK, name="Webhook"
    )
    channel_email = NotificationChannel.objects.create(
        project=project, type=NotificationChannel.ChannelType.EMAIL, name="Email"
    )

    for ch in [channel_in_app, channel_webhook, channel_email]:
        NotificationPolicy.objects.create(
            project=project,
            channel=ch,
            severity=incident.severity,
            event_types=[IncidentEvent.EventType.CREATED],
        )

    event = IncidentEvent.objects.create(
        incident=incident, event_type=IncidentEvent.EventType.CREATED
    )

    dispatch_incident_event(event.id)

    # In-App created
    assert InAppNotification.objects.filter(recipient=user, incident_event=event).exists()

    # Webhook created and delayed
    webhook_deliv = NotificationDelivery.objects.get(incident_event=event, channel=channel_webhook)
    mock_webhook.assert_called_once_with(webhook_deliv.id)

    # Email created and delayed
    email_deliv = NotificationDelivery.objects.get(incident_event=event, channel=channel_email)
    mock_email.assert_called_once_with(email_deliv.id)
