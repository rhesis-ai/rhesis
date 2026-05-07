"""Live progress events for tasks awaited by an architect chat session.

Background workers (e.g. ``run_exploration_task``) call
:func:`publish_task_progress` to surface per-step status to the user
who is watching the architect chat.  The helper looks up the
architect session that is awaiting the given Celery task via the
``arch:task:<id>`` Redis key set by ``register_awaiting_tasks`` and
publishes a ``ARCHITECT_TASK_PROGRESS`` event onto the architect
session's WebSocket channel.

If the task is not currently awaited (e.g. invoked outside an
architect session), the helper is a silent no-op so the worker
continues to function normally for non-architect callers.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from rhesis.backend.app.schemas.websocket import (
    ChannelTarget,
    EventType,
    WebSocketMessage,
)
from rhesis.backend.app.services.websocket.publisher import publish_event
from rhesis.backend.tasks.architect_monitor import _get_redis

logger = logging.getLogger(__name__)


def lookup_session_for_task(task_id: str) -> Optional[str]:
    """Return the architect session_id awaiting ``task_id``, or ``None``.

    Reads ``arch:task:<task_id>`` (set by ``register_awaiting_tasks``)
    and decodes the JSON to extract ``session_id``.  Returns ``None``
    when the key is absent — i.e. when the task wasn't dispatched
    from an architect session, or has already been resolved.
    """
    try:
        r = _get_redis()
        raw = r.get(f"arch:task:{task_id}")
    except Exception:
        logger.debug("Failed to look up arch:task:%s", task_id, exc_info=True)
        return None
    if raw is None:
        return None
    try:
        ctx = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(ctx, dict):
        return None
    sid = ctx.get("session_id")
    return str(sid) if sid else None


def publish_task_progress(
    *,
    task_id: str,
    status: str,
    label: str,
    session_id: Optional[str] = None,
    step: Optional[int] = None,
    total: Optional[int] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """Publish one ``ARCHITECT_TASK_PROGRESS`` event for an awaited task.

    Args:
        task_id: Celery task id of the running task.
        status: ``"started"``, ``"progress"``, ``"completed"`` or
            ``"failed"``.
        label: Short human-readable label, e.g. ``"Running domain
            probing strategy"`` or ``"Penelope turn 3"``.
        session_id: Architect session id.  When omitted, looked up
            from ``arch:task:<task_id>``.  Pass it explicitly when
            already known to skip the Redis read.
        step: 1-based step number, optional.
        total: Total number of steps, optional.
        duration_ms: Step duration in milliseconds, optional.

    Silently no-ops if no architect session is awaiting this task or
    if publishing fails.
    """
    sid = session_id or lookup_session_for_task(task_id)
    if not sid:
        return

    payload: dict = {
        "session_id": sid,
        "task_id": task_id,
        "status": status,
        "label": label,
    }
    if step is not None:
        payload["step"] = step
    if total is not None:
        payload["total"] = total
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms

    try:
        publish_event(
            WebSocketMessage(
                type=EventType.ARCHITECT_TASK_PROGRESS,
                payload=payload,
            ),
            ChannelTarget(channel=f"architect:{sid}"),
        )
    except Exception:
        logger.debug(
            "Failed to publish ARCHITECT_TASK_PROGRESS for %s",
            task_id,
            exc_info=True,
        )


__all__ = ["lookup_session_for_task", "publish_task_progress"]
