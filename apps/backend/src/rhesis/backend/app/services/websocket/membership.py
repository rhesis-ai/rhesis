"""Close open WebSockets once their user is no longer in the organization they joined with.

A socket authenticates once, at connect. Without a re-check it keeps the
organization it opened with after the user leaves it, is removed from it or is
deactivated.
"""

import asyncio
import logging
import math
import os
import random
from typing import Callable

import anyio
from fastapi import WebSocket

from rhesis.backend.app.auth.user_utils import _load_user_by_id

logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL_SECONDS = 30.0
_MIN_INTERVAL_SECONDS = 1.0


def _interval_from_env() -> float:
    raw = os.getenv("WS_MEMBERSHIP_CHECK_INTERVAL", "")
    try:
        value = float(raw) if raw else _DEFAULT_INTERVAL_SECONDS
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        logger.warning("Ignoring invalid WS_MEMBERSHIP_CHECK_INTERVAL=%r", raw)
        value = _DEFAULT_INTERVAL_SECONDS
    # A zero or tiny interval would turn every open socket into a DB polling loop.
    return max(value, _MIN_INTERVAL_SECONDS)


MEMBERSHIP_CHECK_INTERVAL_SECONDS = _interval_from_env()
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


async def close_for_membership(websocket: WebSocket, on_close: Callable[[], None]) -> None:
    """Drop the connection from its manager first, so no further events reach it."""
    on_close()
    try:
        await websocket.close(code=MEMBERSHIP_CLOSE_CODE, reason=MEMBERSHIP_CLOSE_REASON)
    except Exception:
        pass  # Already closed by the client.


async def watch_membership(
    websocket: WebSocket,
    user_id: str,
    organization_id: str,
    on_close: Callable[[], None],
) -> None:
    """Re-check membership every interval and close the socket when it ends."""
    period = MEMBERSHIP_CHECK_INTERVAL_SECONDS
    # Spread the first check so sockets reconnecting after a deploy don't poll in lockstep.
    await asyncio.sleep(random.uniform(0, period))
    while True:
        if not await membership_is_current(user_id, organization_id):
            logger.info(
                "Closing WebSocket for user %s: no longer in organization %s",
                user_id,
                organization_id,
            )
            await close_for_membership(websocket, on_close)
            return
        await asyncio.sleep(period)
