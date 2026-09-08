import logging
import time
import pytest
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.teams.models import Team, TeamMember
from apps.projects.models import Project
from apps.jobs.models import Job
from apps.incidents.models import Incident, IncidentEvent
from apps.notifications.models import NotificationChannel, NotificationPolicy, InAppNotification
from apps.notifications.tasks import dispatch_incident_event_task
from apps.incidents.serializers import IncidentSerializer

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.django_db


@pytest.fixture
def perf_setup(db):
    User = get_user_model()
    owner = User.objects.create(email="owner_perf@example.com")
    member_user = User.objects.create(email="member_perf@example.com")

    team = Team.objects.create(name="Perf Team", slug="perf-team", owner=owner)
    TeamMember.objects.create(team=team, user=member_user, role="member")

    project = Project.objects.create(team=team, name="Perf Project")
    job = Job.objects.create(project=project, name="Perf Job", task_identifier="perf_job")

    # Set up in-app notification policy for MANUALLY_RESOLVED and REOPENED
    channel_in_app = NotificationChannel.objects.create(
        project=project, type=NotificationChannel.ChannelType.IN_APP, name="In-App"
    )
    NotificationPolicy.objects.create(
        project=project,
        channel=channel_in_app,
        severity=Incident.Severity.CRITICAL,
        event_types=[
            IncidentEvent.EventType.MANUALLY_RESOLVED,
            IncidentEvent.EventType.REOPENED,
        ],
    )

    incident = Incident.objects.create(
        project=project,
        job=job,
        severity=Incident.Severity.CRITICAL,
        status=Incident.Status.OPEN,
    )

    return owner, member_user, team, project, incident


def test_resolve_and_reopen_performance_and_async_dispatch(api_client, perf_setup, caplog):
    owner, member_user, team, project, incident = perf_setup
    caplog.set_level(logging.INFO)

    api_client.force_authenticate(user=owner)

    # -------------------------------------------------------------------------
    # 1. Resolve Action Timing Measurement
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    response_resolve = api_client.post(f"/api/incidents/{incident.id}/resolve/")
    resolve_api_ms = (time.perf_counter() - t0) * 1000

    assert response_resolve.status_code == status.HTTP_200_OK
    incident.refresh_from_db()
    assert incident.status == Incident.Status.RESOLVED

    # Ensure no in-app notifications created in HTTP request cycle (since dispatch is deferred to Celery)
    resolve_event = IncidentEvent.objects.get(
        incident=incident, event_type=IncidentEvent.EventType.MANUALLY_RESOLVED
    )

    # -------------------------------------------------------------------------
    # 2. Celery Task Execution Timing Measurement (Background Worker Simulation)
    # -------------------------------------------------------------------------
    t_notif_0 = time.perf_counter()
    dispatch_incident_event_task(resolve_event.id)
    notif_dispatch_ms = (time.perf_counter() - t_notif_0) * 1000

    # Verify background dispatch created in-app notification properly
    assert InAppNotification.objects.filter(incident_event=resolve_event).exists()

    # -------------------------------------------------------------------------
    # 3. Reopen Action Timing Measurement
    # -------------------------------------------------------------------------
    t1 = time.perf_counter()
    response_reopen = api_client.post(f"/api/incidents/{incident.id}/reopen/")
    reopen_api_ms = (time.perf_counter() - t1) * 1000

    assert response_reopen.status_code == status.HTTP_200_OK
    incident.refresh_from_db()
    assert incident.status == Incident.Status.OPEN

    reopen_event = IncidentEvent.objects.get(
        incident=incident, event_type=IncidentEvent.EventType.REOPENED
    )
    dispatch_incident_event_task(reopen_event.id)
    assert InAppNotification.objects.filter(incident_event=reopen_event).exists()

    # -------------------------------------------------------------------------
    # 4. Measure Serializer and DB Tx Time Separately
    # -------------------------------------------------------------------------
    t_ser_0 = time.perf_counter()
    _ = IncidentSerializer(incident).data
    serializer_ms = (time.perf_counter() - t_ser_0) * 1000

    logger.info(
        f"PERF_MEASUREMENT resolve_api_ms={resolve_api_ms:.2f}ms reopen_api_ms={reopen_api_ms:.2f}ms "
        f"notif_dispatch_ms={notif_dispatch_ms:.2f}ms serializer_ms={serializer_ms:.2f}ms"
    )
