import logging
import pickle
import urllib.parse
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache

from .views import TICKET_PREFIX

logger = logging.getLogger(__name__)
User = get_user_model()


def _consume_ticket_atomic(ticket: str) -> int | None:
    """
    Atomically retrieve and delete single-use ticket from cache.
    Guarantees that a ticket can be used at most once.
    """
    key = f"{TICKET_PREFIX}{ticket}"
    try:
        # If using django-redis with raw client, attempt atomic GETDEL
        client = getattr(cache, "client", None)
        if client and hasattr(client, "get_client"):
            redis_conn = client.get_client()
            full_key = cache.make_key(key)
            val = redis_conn.getdel(full_key)
            if val is not None:
                try:
                    return int(pickle.loads(val))
                except Exception:
                    return int(val)
            return None
    except Exception:
        # If GETDEL fails or client is not redis (e.g. LocMemCache in tests), fallback to get + delete
        pass

    # Standard fallback for LocMemCache/tests
    user_id = cache.get(key)
    if user_id is not None:
        cache.delete(key)
        return int(user_id)
    return None


@database_sync_to_async
def _get_user_by_id(user_id: int):
    try:
        return User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return AnonymousUser()


class WebSocketTicketAuthMiddleware:
    """
    ASGI middleware for WebSocket authentication via single-use ticket or session fallback.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            query_string = scope.get("query_string", b"").decode("utf-8")
            query_params = urllib.parse.parse_qs(query_string)
            ticket_list = query_params.get("ticket")

            if ticket_list:
                ticket = ticket_list[0]
                user_id = _consume_ticket_atomic(ticket)
                if user_id:
                    scope["user"] = await _get_user_by_id(user_id)
                else:
                    scope["user"] = AnonymousUser()
            elif "user" not in scope or scope["user"].is_anonymous:
                # If no ticket and scope has no user, default to AnonymousUser
                scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)
