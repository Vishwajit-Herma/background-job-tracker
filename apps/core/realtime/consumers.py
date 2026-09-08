import logging
from typing import Any
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.projects.models import Project
from apps.teams.models import TeamMember

logger = logging.getLogger(__name__)


@database_sync_to_async
def _get_user_authorized_scopes(user):
    """
    Look up all active teams and active projects the user belongs to.
    Also re-checks ``User.is_active`` so callers can react to account deactivation.

    Returns: ``(team_ids, project_ids, user_is_active)``
    """
    from apps.users.models import User  # noqa: F401 — local import avoids circular deps

    user_is_active = User.objects.filter(pk=user.pk, is_active=True).exists()

    team_ids = list(
        TeamMember.objects.filter(
            user=user,
            is_active=True,
            team__is_active=True,
        ).values_list("team_id", flat=True)
    )

    project_ids = list(
        Project.objects.filter(
            team_id__in=team_ids,
            is_deleted=False,
            status=Project.Status.ACTIVE,
        ).values_list("id", flat=True)
    )

    return team_ids, project_ids, user_is_active


class RealtimeConsumer(AsyncJsonWebsocketConsumer):
    """
    Centralized authenticated WebSocket consumer with strict multi-tenant authorization.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.joined_groups: set[str] = set()

    async def connect(self):
        user = self.scope.get("user")
        if not user or user.is_anonymous:
            # 4001: Custom WS close code for Unauthorized
            await self.close(code=4001)
            return

        await self.accept()

        user_group = f"user_{user.id}"
        await self.channel_layer.group_add(user_group, self.channel_name)
        self.joined_groups.add(user_group)

        team_ids, project_ids, _ = await _get_user_authorized_scopes(user)

        for team_id in team_ids:
            group = f"team_{team_id}"
            await self.channel_layer.group_add(group, self.channel_name)
            self.joined_groups.add(group)

        for project_id in project_ids:
            group = f"project_{project_id}"
            await self.channel_layer.group_add(group, self.channel_name)
            self.joined_groups.add(group)

        # Send initial handshake acknowledgement
        await self.send_json(
            {
                "type": "connection.ready",
                "user_id": user.id,
                "team_ids": team_ids,
                "project_ids": project_ids,
            }
        )

    async def disconnect(self, close_code):
        for group in self.joined_groups:
            try:
                await self.channel_layer.group_discard(group, self.channel_name)
            except Exception as e:
                logger.warning("Error discarding group %s: %s", group, e)
        self.joined_groups.clear()

    async def receive_json(self, content: dict[str, Any], **kwargs):
        action = content.get("action")
        if action == "ping":
            await self.send_json({"action": "pong"})
        elif action == "resync_scopes":
            await self._resync_scopes()

    async def _resync_scopes(self) -> None:
        """
        Re-evaluate the authenticated user's authorized channel groups and:
          1. Close the WebSocket with 4001 if the user account is now inactive.
          2. Join any newly authorized groups.
          3. Discard any previously joined groups that are no longer authorized.

        The per-user group (user_{id}) is always preserved unless the user
        account itself is deactivated, in which case the socket is closed.
        """
        user = self.scope.get("user")
        if not user or user.is_anonymous:
            return

        team_ids, project_ids, user_is_active = await _get_user_authorized_scopes(user)

        if not user_is_active:
            # The account was deactivated while the socket was open.
            # Tear down cleanly so the client reconnects and gets a fresh 4001.
            logger.info("Closing WebSocket for deactivated user %s during scope resync.", user.pk)
            await self.close(code=4001)
            return

        authorized_groups: set[str] = {f"user_{user.id}"}
        for team_id in team_ids:
            authorized_groups.add(f"team_{team_id}")
        for project_id in project_ids:
            authorized_groups.add(f"project_{project_id}")

        # Join newly authorized groups
        for group in authorized_groups - self.joined_groups:
            await self.channel_layer.group_add(group, self.channel_name)
            self.joined_groups.add(group)

        # Discard groups that are no longer authorized (except the user group)
        revoked_groups = self.joined_groups - authorized_groups
        for group in revoked_groups:
            try:
                await self.channel_layer.group_discard(group, self.channel_name)
            except Exception as exc:
                logger.warning("Error discarding revoked group %s: %s", group, exc)
            self.joined_groups.discard(group)

        await self.send_json(
            {
                "type": "scopes.resynced",
                "team_ids": team_ids,
                "project_ids": project_ids,
            }
        )

    async def realtime_event(self, event: dict[str, Any]):
        """
        Handler for messages broadcast to channel groups by publish_realtime_event().
        """
        payload = event.get("payload")
        if payload:
            await self.send_json(payload)
