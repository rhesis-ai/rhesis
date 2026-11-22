"""Close open WebSockets once their user is no longer in the organization they joined with.

A socket authenticates once, at connect. Without a re-check it keeps the
organization it opened with after the user leaves it, is removed from it or is
deactivated.
"""

import asyncio
import logging
import os
from typing import Callable, Optional

import anyio
from fastapi import WebSocket

from rhesis.backend.app.auth.user_utils import _load_user_by_id

logger = logging.getLogger(__name__)

MEMBERSHIP_CHECK_INTERVAL_SECONDS = float(os.getenv("WS_MEMBERSHIP_CHECK_INTERVAL", "30"))
MEMBERSHIP_CLOSE_CODE = 1008
MEMBERSHIP_CLOSE_REASON = "Organization membership changed"


def _is_member(user_id: str, organization_id: str) -> bool:
    user = _load_user_by_id(user_id)
    return bool(user and user.is_active and str(user.organization_id) == organization_id)


async def membership_is_current(user_id: str, organization_id: str) -> bool:
    """True while the user is active and still in ``organization_id``.

    A failed lookup counts as current: a database hiccup should not drop every
    open socket, and the next check runs on the next interval.
    """
    try:
        return await anyio.to_thread.run_sync(_is_member, user_id, organization_id)
    except Exception as e:
        logger.warning("WebSocket membership check failed for user %s: %s", user_id, e)
        return True


async def close_for_membership(
    websocket: WebSocket, on_close: Optional[Callable[[], None]]
) -> None:
    """Drop the connection from its manager first, so no further events reach it."""
    if on_close is not None:
        on_close()
    try:
        await websocket.close(code=MEMBERSHIP_CLOSE_CODE, reason=MEMBERSHIP_CLOSE_REASON)
    except Exception:
        pass  # Already closed by the client.


async def watch_membership(
    websocket: WebSocket,
    user_id: str,
    organization_id: str,
    on_close: Optional[Callable[[], None]] = None,
    interval: Optional[float] = None,
) -> None:
    """Re-check membership every ``interval`` seconds and close the socket when it ends."""
    period = MEMBERSHIP_CHECK_INTERVAL_SECONDS if interval is None else interval
    while True:
        await asyncio.sleep(period)
        if not await membership_is_current(user_id, organization_id):
            logger.info(
                "Closing WebSocket for user %s: no longer in organization %s",
                user_id,
                organization_id,
            )
            await close_for_membership(websocket, on_close)
            return
