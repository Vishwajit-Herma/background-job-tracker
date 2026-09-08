import secrets
import uuid
from unittest.mock import patch
import pytest
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from channels.testing import WebsocketCommunicator

from apps.core.realtime.publisher import publish_realtime_event
from apps.core.realtime.middleware import _consume_ticket_atomic
from apps.core.realtime.views import TICKET_PREFIX
from apps.executions.services import ingest_executions_batch
from apps.incidents.models import Incident
from apps.incidents.services import add_incident_note
from apps.jobs.models import Job
from apps.projects.models import Project
from apps.teams.models import Team
from apps.users.models import User
from config.asgi import application


# ---------------------------------------------------------------------------
# Test-local helper: inject a realtime event directly via the channel layer.
#
# Tests cannot use publish_realtime_event() from an async context because
# transaction.on_commit() is sync-only (raises SynchronousOnlyOperation).
# The channel layer's group_send is a plain coroutine and is safe to await
# directly in tests — there is no surrounding DB transaction to respect.
# ---------------------------------------------------------------------------


async def _send_test_event(
    event_type: str,
    project_id: int | None = None,
    team_id: int | None = None,
    user_id: int | None = None,
    payload: dict | None = None,
) -> None:
    """
    Push a realtime event directly into the channel layer for test assertions.

    This bypasses transaction.on_commit intentionally — tests have no open DB
    transaction, so immediate delivery is both correct and necessary.
    Do NOT use this helper in production code.
    """
    from django.utils import timezone as _tz

    channel_layer = get_channel_layer()
    data = {
        "type": event_type,
        "timestamp": _tz.now().isoformat(),
        **(payload or {}),
    }
    if project_id is not None:
        data["project_id"] = project_id
    if team_id is not None:
        data["team_id"] = team_id
    if user_id is not None:
        data["user_id"] = user_id

    message = {"type": "realtime.event", "payload": data}
    groups = []
    if project_id is not None:
        groups.append(f"project_{project_id}")
    if team_id is not None:
        groups.append(f"team_{team_id}")
    if user_id is not None:
        groups.append(f"user_{user_id}")

    for group in groups:
        await channel_layer.group_send(group, message)


async def _send_test_batch(
    project_id: int,
    count: int,
    job_ids: list[int] | None = None,
    statuses: list[str] | None = None,
) -> None:
    """Convenience wrapper for execution.batch test events."""
    await _send_test_event(
        "execution.batch",
        project_id=project_id,
        payload={
            "count": count,
            "job_ids": sorted(set(job_ids or [])),
            "statuses": sorted(set(statuses or [])),
        },
    )


# ---------------------------------------------------------------------------
# Ticket tests (sync)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ticket_generation_and_atomic_consumption(authenticated_api_client, user):
    """
    POST /api/realtime/ticket/ generates a 60s single-use ticket.
    Consuming it once succeeds; consuming it twice returns None.
    """
    response = authenticated_api_client.post("/api/realtime/ticket/")
    assert response.status_code == 200
    data = response.json()
    assert "ticket" in data
    assert data["expires_in"] == 60

    ticket = data["ticket"]
    cache_key = f"{TICKET_PREFIX}{ticket}"
    # Ensure only the minimal identity (user.id) was saved
    assert cache.get(cache_key) == user.id

    # First consumption: succeeds atomically
    consumed_user_id = _consume_ticket_atomic(ticket)
    assert consumed_user_id == user.id

    # Second consumption: fails immediately (single-use)
    assert _consume_ticket_atomic(ticket) is None


@pytest.mark.django_db
def test_unauthenticated_ticket_request(api_client):
    """
    Unauthenticated requests cannot create WebSocket tickets.
    """
    response = api_client.post("/api/realtime/ticket/")
    assert response.status_code in [401, 403]


# ---------------------------------------------------------------------------
# WebSocket connection tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_websocket_rejects_unauthenticated():
    """
    Unauthenticated WebSocket connection without ticket or session is rejected with 4001.
    """
    communicator = WebsocketCommunicator(application, "ws/realtime/")
    connected, close_code = await communicator.connect()
    assert not connected
    assert close_code == 4001
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_websocket_accepts_valid_ticket_and_receives_events():
    """
    WebSocket connection with a valid ticket succeeds, receives handshake,
    handles ping/pong, and receives published events.
    """
    user = await User.objects.acreate(
        email="ws_user@example.com", first_name="Realtime", last_name="User"
    )
    team = await Team.objects.acreate(name="Realtime Team", slug="realtime-team", owner=user)
    project = await Project.objects.acreate(name="Realtime Project", team=team)

    ticket = secrets.token_urlsafe(32)
    cache.set(f"{TICKET_PREFIX}{ticket}", user.id, timeout=60)

    communicator = WebsocketCommunicator(application, f"ws/realtime/?ticket={ticket}")
    connected, _ = await communicator.connect()
    assert connected

    response = await communicator.receive_json_from()
    assert response["type"] == "connection.ready"
    assert response["user_id"] == user.id
    assert team.id in response["team_ids"]
    assert project.id in response["project_ids"]

    # Heartbeat ping
    await communicator.send_json_to({"action": "ping"})
    pong = await communicator.receive_json_from()
    assert pong == {"action": "pong"}

    # Broadcast event to project group
    await _send_test_event(
        "incident.updated",
        project_id=project.id,
        payload={"incident_id": 99, "status": "OPEN"},
    )
    event_msg = await communicator.receive_json_from()
    assert event_msg["type"] == "incident.updated"
    assert event_msg["project_id"] == project.id
    assert event_msg["incident_id"] == 99

    # Execution batch event to project group
    await _send_test_batch(project_id=project.id, count=5, job_ids=[10, 11])
    batch_msg = await communicator.receive_json_from()
    assert batch_msg["type"] == "execution.batch"
    assert batch_msg["project_id"] == project.id
    assert batch_msg["count"] == 5
    assert batch_msg["job_ids"] == [10, 11]

    # User notification event to user group
    await _send_test_event(
        "notification.created",
        user_id=user.id,
        payload={"title": "High CPU"},
    )
    notif_msg = await communicator.receive_json_from()
    assert notif_msg["type"] == "notification.created"
    assert notif_msg["user_id"] == user.id
    assert notif_msg["title"] == "High CPU"

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_websocket_multi_tenant_isolation():
    """
    Ensure zero event leakage across teams:
    User A (Team A) cannot receive events published to Team B or Project B.
    """
    user_a = await User.objects.acreate(email="user_a@example.com")
    team_a = await Team.objects.acreate(name="Team A", slug="team-a", owner=user_a)
    project_a = await Project.objects.acreate(name="Project A", team=team_a)

    user_b = await User.objects.acreate(email="user_b@example.com")
    team_b = await Team.objects.acreate(name="Team B", slug="team-b", owner=user_b)
    project_b = await Project.objects.acreate(name="Project B", team=team_b)

    ticket_a = secrets.token_urlsafe(32)
    cache.set(f"{TICKET_PREFIX}{ticket_a}", user_a.id, timeout=60)

    communicator_a = WebsocketCommunicator(application, f"ws/realtime/?ticket={ticket_a}")
    connected_a, _ = await communicator_a.connect()
    assert connected_a
    await communicator_a.receive_json_from()  # consume connection.ready

    # Publish events to Team B / Project B / User B — must not reach User A
    await _send_test_event(
        "incident.updated", project_id=project_b.id, payload={"incident_id": 101, "status": "OPEN"}
    )
    await _send_test_event("team.updated", team_id=team_b.id, payload={"action": "updated"})
    await _send_test_event(
        "notification.created", user_id=user_b.id, payload={"title": "Secret alert for B"}
    )

    assert await communicator_a.receive_nothing(timeout=0.2)

    # Publish event to Project A — must arrive at User A
    await _send_test_event(
        "incident.updated",
        project_id=project_a.id,
        payload={"incident_id": 202, "status": "RESOLVED"},
    )
    event_msg = await communicator_a.receive_json_from()
    assert event_msg["type"] == "incident.updated"
    assert event_msg["incident_id"] == 202

    await communicator_a.disconnect()


# ---------------------------------------------------------------------------
# Production service integration (sync)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_incident_note_deduplication_emits_only_note_created(user, team):
    """
    Adding an incident note emits incident.note.created and strictly does NOT emit incident.updated.
    """
    project = Project.objects.create(name="Note Project", team=team)
    incident = Incident.objects.create(project=project, severity=Incident.Severity.DEGRADED)

    with patch("apps.incidents.services.publish_realtime_event") as mock_publish:
        add_incident_note(incident.id, user, "Investigating high latency.")

        assert mock_publish.call_count == 1
        call_args = mock_publish.call_args
        assert call_args.args[0] == "incident.note.created"
        assert call_args.kwargs["project_id"] == project.id
        assert call_args.kwargs["payload"]["incident_id"] == incident.id


@pytest.mark.django_db
def test_execution_batch_emits_coalesced_event(team):
    """
    Ingesting execution batch emits execution.batch with count and job_ids.
    """
    project = Project.objects.create(name="Exec Project", team=team)
    job = Job.objects.create(name="Batch Job", task_identifier="batch.job", project=project)

    now = timezone.now()
    exec_data = [
        {
            "external_id": str(uuid.uuid4()),
            "event_id": str(uuid.uuid4()),
            "event_timestamp": now,
            "task_identifier": job.task_identifier,
            "status": "SUCCESS",
            "started_at": now,
            "finished_at": now,
            "duration_ms": 1000,
        }
    ]

    with patch("apps.executions.services.publish_execution_batch") as mock_publish:
        result = ingest_executions_batch(project, exec_data)
        assert result["accepted"] == 1
        assert mock_publish.call_count == 1
        mock_publish.assert_called_once_with(
            project_id=project.id,
            count=1,
            job_ids=[job.id],
        )


# ---------------------------------------------------------------------------
# Authorization-revocation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_resync_scopes_discards_revoked_project():
    """
    When a user loses access to a project (project deleted/deactivated) and
    triggers resync_scopes, the consumer must leave that group and must no longer
    receive events published to it.
    """
    user = await User.objects.acreate(email="revoke_proj@example.com")
    team = await Team.objects.acreate(name="Revoke Team", slug="revoke-team", owner=user)
    project = await Project.objects.acreate(name="Soon Deleted", team=team)

    ticket = secrets.token_urlsafe(32)
    cache.set(f"{TICKET_PREFIX}{ticket}", user.id, timeout=60)

    communicator = WebsocketCommunicator(application, f"ws/realtime/?ticket={ticket}")
    connected, _ = await communicator.connect()
    assert connected

    ready = await communicator.receive_json_from()
    assert ready["type"] == "connection.ready"
    assert project.id in ready["project_ids"]

    # Deactivate the project so it will no longer appear in authorized scopes
    await Project.objects.filter(pk=project.id).aupdate(status=Project.Status.INACTIVE)

    await communicator.send_json_to({"action": "resync_scopes"})
    resynced = await communicator.receive_json_from()
    assert resynced["type"] == "scopes.resynced"
    assert project.id not in resynced["project_ids"]

    # Event published to the now-revoked project group must NOT arrive
    await _send_test_event(
        "incident.updated",
        project_id=project.id,
        payload={"incident_id": 555, "status": "OPEN"},
    )
    assert await communicator.receive_nothing(timeout=0.3)

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_resync_scopes_discards_revoked_team():
    """
    When a user is removed from a team and triggers resync_scopes, the consumer
    must leave the team group and no longer receive team-level events.
    """
    from apps.teams.models import TeamMember

    user = await User.objects.acreate(email="revoke_team@example.com")
    team = await Team.objects.acreate(name="Leave Team", slug="leave-team", owner=user)

    ticket = secrets.token_urlsafe(32)
    cache.set(f"{TICKET_PREFIX}{ticket}", user.id, timeout=60)

    communicator = WebsocketCommunicator(application, f"ws/realtime/?ticket={ticket}")
    connected, _ = await communicator.connect()
    assert connected

    ready = await communicator.receive_json_from()
    assert ready["type"] == "connection.ready"
    assert team.id in ready["team_ids"]

    await TeamMember.objects.filter(user=user, team=team).aupdate(is_active=False)

    await communicator.send_json_to({"action": "resync_scopes"})
    resynced = await communicator.receive_json_from()
    assert resynced["type"] == "scopes.resynced"
    assert team.id not in resynced["team_ids"]

    # Team-level event must NOT arrive after revocation
    await _send_test_event(
        "team.updated",
        team_id=team.id,
        payload={"action": "settings_changed"},
    )
    assert await communicator.receive_nothing(timeout=0.3)

    # Personal user-group event must still arrive (user group is never revoked)
    await _send_test_event(
        "notification.created",
        user_id=user.id,
        payload={"title": "Still mine"},
    )
    notif = await communicator.receive_json_from()
    assert notif["type"] == "notification.created"
    assert notif["user_id"] == user.id

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_resync_joins_newly_added_project():
    """
    When a new project is added to the user's team and they trigger resync_scopes,
    the consumer must join the new group and start receiving its events.
    """
    user = await User.objects.acreate(email="new_proj@example.com")
    team = await Team.objects.acreate(name="Growing Team", slug="growing-team", owner=user)
    await Project.objects.acreate(name="Project A", team=team)

    ticket = secrets.token_urlsafe(32)
    cache.set(f"{TICKET_PREFIX}{ticket}", user.id, timeout=60)

    communicator = WebsocketCommunicator(application, f"ws/realtime/?ticket={ticket}")
    connected, _ = await communicator.connect()
    assert connected
    await communicator.receive_json_from()  # connection.ready

    project_b = await Project.objects.acreate(name="Project B", team=team)

    await communicator.send_json_to({"action": "resync_scopes"})
    resynced = await communicator.receive_json_from()
    assert project_b.id in resynced["project_ids"]

    await _send_test_event(
        "execution.batch",
        project_id=project_b.id,
        payload={"count": 3, "job_ids": [1], "statuses": ["SUCCESS"]},
    )
    event = await communicator.receive_json_from()
    assert event["type"] == "execution.batch"
    assert event["project_id"] == project_b.id

    await communicator.disconnect()


# ---------------------------------------------------------------------------
# Reconnect / security tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_expired_ticket_is_rejected():
    """
    A ticket that has already expired from the cache is rejected with 4001.
    """
    expired_ticket = secrets.token_urlsafe(32)
    communicator = WebsocketCommunicator(application, f"ws/realtime/?ticket={expired_ticket}")
    connected, close_code = await communicator.connect()
    assert not connected
    assert close_code == 4001
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_second_use_of_single_use_ticket_is_rejected():
    """
    After a ticket has been consumed by one successful connection, attempting
    to open a second connection with the same ticket is rejected with 4001.
    """
    user = await User.objects.acreate(email="reuse_ticket@example.com")
    await Team.objects.acreate(name="Reuse Team", slug="reuse-team", owner=user)

    ticket = secrets.token_urlsafe(32)
    cache.set(f"{TICKET_PREFIX}{ticket}", user.id, timeout=60)

    comm1 = WebsocketCommunicator(application, f"ws/realtime/?ticket={ticket}")
    connected1, _ = await comm1.connect()
    assert connected1
    await comm1.receive_json_from()  # connection.ready

    comm2 = WebsocketCommunicator(application, f"ws/realtime/?ticket={ticket}")
    connected2, close_code = await comm2.connect()
    assert not connected2
    assert close_code == 4001

    await comm1.disconnect()
    await comm2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_reconnect_restores_full_scope():
    """
    After a disconnection, reconnecting with a fresh ticket restores the complete
    scope (team + project groups) and the client receives events on all groups.
    """
    user = await User.objects.acreate(email="reconnect@example.com")
    team = await Team.objects.acreate(name="Reconnect Team", slug="reconnect-team", owner=user)
    project = await Project.objects.acreate(name="Reconnect Project", team=team)

    def _make_ticket():
        t = secrets.token_urlsafe(32)
        cache.set(f"{TICKET_PREFIX}{t}", user.id, timeout=60)
        return t

    comm1 = WebsocketCommunicator(application, f"ws/realtime/?ticket={_make_ticket()}")
    c1, _ = await comm1.connect()
    assert c1
    ready1 = await comm1.receive_json_from()
    assert ready1["type"] == "connection.ready"
    await comm1.disconnect()

    comm2 = WebsocketCommunicator(application, f"ws/realtime/?ticket={_make_ticket()}")
    c2, _ = await comm2.connect()
    assert c2
    ready2 = await comm2.receive_json_from()
    assert ready2["type"] == "connection.ready"
    assert team.id in ready2["team_ids"]
    assert project.id in ready2["project_ids"]

    await _send_test_event(
        "incident.updated",
        project_id=project.id,
        payload={"incident_id": 777, "status": "RESOLVED"},
    )
    event = await comm2.receive_json_from()
    assert event["type"] == "incident.updated"
    assert event["project_id"] == project.id

    await comm2.disconnect()


# ---------------------------------------------------------------------------
# Transaction semantics — sync publish_realtime_event
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_sync_event_is_NOT_sent_inside_open_transaction():
    """
    publish_realtime_event() must NOT fire channel-layer sends while a
    surrounding atomic() block is still open.  The callback is registered with
    transaction.on_commit(), so nothing should reach the channel layer until
    the transaction commits.
    """
    send_calls: list = []

    real_channel_layer = get_channel_layer()

    async def _fake_group_send(group, message):
        send_calls.append((group, message))

    with patch.object(real_channel_layer, "group_send", side_effect=_fake_group_send):
        with transaction.atomic():
            publish_realtime_event(
                "incident.updated",
                project_id=1,
                payload={"incident_id": 42},
            )
            assert send_calls == [], "Event fired inside open transaction (on_commit bypassed)"

        assert len(send_calls) == 1
        assert send_calls[0][0] == "project_1"
        assert send_calls[0][1]["payload"]["type"] == "incident.updated"


@pytest.mark.django_db(transaction=True)
def test_sync_event_is_dropped_on_rollback():
    """
    If the surrounding atomic() block rolls back, on_commit callbacks are
    discarded — the channel-layer send must never be called.
    """
    send_calls: list = []

    real_channel_layer = get_channel_layer()

    async def _fake_group_send(group, message):  # pragma: no cover
        send_calls.append((group, message))

    with patch.object(real_channel_layer, "group_send", side_effect=_fake_group_send):
        try:
            with transaction.atomic():
                publish_realtime_event(
                    "incident.updated",
                    project_id=2,
                    payload={"incident_id": 99},
                )
                raise RuntimeError("simulated rollback")
        except RuntimeError:
            pass

        assert send_calls == [], "Event was sent despite transaction rollback"


@pytest.mark.django_db(transaction=True)
def test_sync_event_is_sent_after_nested_savepoint_commit():
    """
    publish_realtime_event() inside a nested savepoint (inner atomic()) must
    still fire only after the outermost transaction commits.
    """
    send_calls: list = []

    real_channel_layer = get_channel_layer()

    async def _fake_group_send(group, message):
        send_calls.append(group)

    with patch.object(real_channel_layer, "group_send", side_effect=_fake_group_send):
        with transaction.atomic():  # outer transaction
            with transaction.atomic():  # inner savepoint
                publish_realtime_event(
                    "job.updated",
                    project_id=3,
                    payload={"job_id": 7},
                )
            assert send_calls == [], "Fired after savepoint but before outer commit"

        assert send_calls == ["project_3"]


# ---------------------------------------------------------------------------
# Deactivated-user regression — resync_scopes closes socket
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_resync_closes_socket_for_deactivated_user():
    """
    If the authenticated user's account is deactivated while a WebSocket
    session is live, the next resync_scopes must close the connection with
    4001 rather than retaining any group memberships.
    """
    user = await User.objects.acreate(email="deactivated@example.com", is_active=True)
    await Team.objects.acreate(name="Deact Team", slug="deact-team", owner=user)

    ticket = secrets.token_urlsafe(32)
    cache.set(f"{TICKET_PREFIX}{ticket}", user.id, timeout=60)

    communicator = WebsocketCommunicator(application, f"ws/realtime/?ticket={ticket}")
    connected, _ = await communicator.connect()
    assert connected
    await communicator.receive_json_from()  # connection.ready

    await User.objects.filter(pk=user.pk).aupdate(is_active=False)

    await communicator.send_json_to({"action": "resync_scopes"})

    output = await communicator.receive_output()
    assert output["type"] == "websocket.close"
    assert output.get("code") == 4001

    await communicator.disconnect()
