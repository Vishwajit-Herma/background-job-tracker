import asyncio
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Pre-warmed background thread pool for zero-blocking realtime WebSocket delivery
_REALTIME_THREAD_POOL = ThreadPoolExecutor(
    max_workers=8, thread_name_prefix="bjt_realtime_publisher"
)

# Persistent background event loop for preserving channels_redis TLS/TCP connection pools
_LOOP: asyncio.AbstractEventLoop | None = None
_LOOP_THREAD: threading.Thread | None = None
_LOOP_PID: int | None = None
_LOOP_LOCK = threading.Lock()


def _run_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    global _LOOP, _LOOP_THREAD, _LOOP_PID
    current_pid = os.getpid()
    with _LOOP_LOCK:
        if (
            current_pid != _LOOP_PID
            or _LOOP is None
            or _LOOP.is_closed()
            or _LOOP_THREAD is None
            or not _LOOP_THREAD.is_alive()
        ):
            _LOOP_PID = current_pid
            _LOOP = asyncio.new_event_loop()
            _LOOP_THREAD = threading.Thread(
                target=_run_event_loop,
                args=(_LOOP,),
                name=f"bjt_realtime_loop_{current_pid}",
                daemon=True,
            )
            _LOOP_THREAD.start()
        return _LOOP


# ---------------------------------------------------------------------------
# Internal helpers & Celery Tasks
# ---------------------------------------------------------------------------


def _build_message(
    event_type: str,
    project_id: int | None,
    team_id: int | None,
    user_id: int | None,
    payload: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    """Build the channel-layer message envelope and target group list."""
    data: dict[str, Any] = {
        "type": event_type,
        "timestamp": timezone.now().isoformat(),
        **(payload or {}),
    }
    if project_id is not None:
        data["project_id"] = project_id
    if team_id is not None:
        data["team_id"] = team_id
    if user_id is not None:
        data["user_id"] = user_id

    groups: list[str] = []
    if project_id is not None:
        groups.append(f"project_{project_id}")
    if team_id is not None:
        groups.append(f"team_{team_id}")
    if user_id is not None:
        groups.append(f"user_{user_id}")

    return {"type": "realtime.event", "payload": data}, groups


def _send_realtime_direct(message: dict[str, Any], groups: list[str]) -> None:
    """
    Directly publish channel-layer message to Redis channel groups concurrently.
    Uses a persistent background asyncio event loop to preserve channels_redis
    connection pools and avoid TLS handshake overhead (~700ms -> <10ms).
    Executed in a background thread — never blocks HTTP response threads.
    """

    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        async def _send_all():
            await asyncio.gather(
                *(channel_layer.group_send(group, message) for group in groups),
                return_exceptions=True,
            )

        loop = _get_or_create_event_loop()
        future = asyncio.run_coroutine_threadsafe(_send_all(), loop)
        future.result(timeout=5.0)
    except Exception as exc:
        # Redis/WebSocket failures must never propagate to business operations or task failure.
        logger.warning("Failed to publish realtime event: %s", exc)


@shared_task(name="realtime.publish_event", ignore_result=True)
def publish_realtime_event_task(message: dict[str, Any], groups: list[str]) -> None:
    """
    Celery task wrapper for background/eager test execution.
    """
    _send_realtime_direct(message, groups)


def _dispatch_realtime_callback(message: dict[str, Any], groups: list[str]) -> None:
    """
    Post-commit callback handler:
    Offloads publishing to a background thread pool in production (0ms HTTP blocking),
    or executes synchronously in test/eager environments.
    """
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        _send_realtime_direct(message, groups)
    else:
        _REALTIME_THREAD_POOL.submit(_send_realtime_direct, message, groups)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def publish_realtime_event(
    event_type: str,
    project_id: int | None = None,
    team_id: int | None = None,
    user_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """
    Publish a compact realtime event to all authorized channel groups.

    Events are registered with ``transaction.on_commit()`` so they are never
    dispatched before the surrounding DB transaction commits, and are silently
    dropped on rollback. In autocommit mode (Celery tasks, views without an
    explicit ``atomic()`` block) the callback fires immediately after the call.

    Post-commit, the event dispatch is offloaded to a background thread pool
    so synchronous HTTP response threads return immediately without waiting on Redis I/O.
    """
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    message, groups = _build_message(event_type, project_id, team_id, user_id, payload)
    if not groups:
        return

    transaction.on_commit(lambda: _dispatch_realtime_callback(message, groups))


def publish_execution_batch(
    project_id: int,
    count: int,
    job_ids: list[int] | None = None,
    statuses: list[str] | None = None,
) -> None:
    """
    Publish a coalesced execution batch event.

    Convenience wrapper around ``publish_realtime_event`` for the high-volume
    ingestion path; inherits the same ``transaction.on_commit`` semantics.
    """
    publish_realtime_event(
        event_type="execution.batch",
        project_id=project_id,
        payload={
            "count": count,
            "job_ids": sorted(set(job_ids or [])),
            "statuses": sorted(set(statuses or [])),
        },
    )
