import pytest
from django.core.exceptions import ValidationError
from apps.notifications.models import NotificationChannel, NotificationPolicy
from apps.incidents.models import IncidentEvent

pytestmark = pytest.mark.django_db


def test_webhook_config_validation(project):
    channel = NotificationChannel(
        project=project,
        type=NotificationChannel.ChannelType.WEBHOOK,
        name="Webhook",
        config={"url": "invalid"},
    )
    with pytest.raises(ValidationError):
        channel.clean()

    # HTTPS always allowed
    channel.config = {"url": "https://example.com/webhook", "secret": "sec1234567890123"}
    channel.clean()  # Should not raise

    # HTTPS with flag true allowed
    channel.config = {
        "url": "https://example.com/webhook",
        "secret": "sec1234567890123",
        "allow_insecure_http": True,
    }
    channel.clean()

    # HTTP with flag false rejected
    channel.config = {
        "url": "http://example.com/webhook",
        "secret": "sec1234567890123",
        "allow_insecure_http": False,
    }
    with pytest.raises(ValidationError):
        channel.clean()

    # HTTP with flag true allowed
    channel.config = {
        "url": "http://example.com/webhook",
        "secret": "sec1234567890123",
        "allow_insecure_http": True,
    }
    channel.clean()


def test_policy_event_type_validation(project):
    channel = NotificationChannel.objects.create(
        project=project,
        type=NotificationChannel.ChannelType.IN_APP,
        name="In-App",
    )
    policy = NotificationPolicy(
        project=project, channel=channel, severity="CRITICAL", event_types=["INVALID_EVENT"]
    )
    with pytest.raises(ValidationError):
        policy.clean()

    policy.event_types = [IncidentEvent.EventType.CREATED]
    policy.clean()  # Should not raise
