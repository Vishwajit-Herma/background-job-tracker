import pytest
from rest_framework.test import APIClient
from apps.notifications.models import NotificationChannel, InAppNotification
from apps.incidents.models import IncidentEvent

pytestmark = pytest.mark.django_db


def test_webhook_secret_is_masked(project, user, team_member):
    client = APIClient()
    client.force_authenticate(user=user)

    channel = NotificationChannel.objects.create(
        project=project,
        type=NotificationChannel.ChannelType.WEBHOOK,
        name="Webhook",
        config={"url": "https://example.com/webhook", "secret": "mysecret12345678"},
    )

    response = client.get(f"/api/notifications/channels/{channel.id}/")
    assert response.status_code == 200
    assert response.data["data"]["config"]["secret"] == "********"


def test_cannot_read_another_users_notification(
    project, user, team_member, django_user_model, incident
):
    other_user = django_user_model.objects.create_user(
        email="other@example.com", password="password"
    )

    event = IncidentEvent.objects.create(
        incident=incident, event_type=IncidentEvent.EventType.CREATED
    )

    notification = InAppNotification.objects.create(
        recipient=other_user, incident_event=event, title="Title", message="Message"
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(f"/api/notifications/in-app/{notification.id}/read/")
    assert response.status_code == 404
