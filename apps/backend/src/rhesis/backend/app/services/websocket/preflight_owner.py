"""Bind a preflight correlation id to the user who first uses it.

The client picks the id and subscribes to ``preflight:{id}`` before it starts
the run, so either step can come first. Whichever comes first claims the id;
afterwards only that user may subscribe to the channel or start a run on it.
"""

import logging
import time

logger = logging.getLogger(__name__)

# Covers the 120s background timeout plus the time a dialog stays open.
PREFLIGHT_OWNER_TTL_SECONDS = 600
_KEY_PREFIX = "preflight_owner:"

# Used only while Redis is unreachable; Redis is the cross-process store.
_local_owners: dict[str, tuple[str, float]] = {}


def _claim_locally(correlation_id: str, user_id: str) -> bool:
    now = time.monotonic()
    for key, (_, expires_at) in list(_local_owners.items()):
        if expires_at <= now:
            del _local_owners[key]
    owner, _ = _local_owners.setdefault(
        correlation_id, (user_id, now + PREFLIGHT_OWNER_TTL_SECONDS)
    )
    return owner == user_id


async def claim_preflight_channel(correlation_id: str, user_id: str) -> bool:
    """Return True if ``user_id`` owns ``correlation_id`` (claiming it if unclaimed).

    The per-process store is used only while Redis is down. If Redis is up but a
    call fails, the claim is refused: the local store cannot see Redis claims.
    """
    from rhesis.backend.app.services.connector.redis_client import redis_manager

    await redis_manager.initialize()
    if not redis_manager.is_available:
        return _claim_locally(correlation_id, user_id)

    key = f"{_KEY_PREFIX}{correlation_id}"
    try:
        client = redis_manager.client
        # Two tries: the key can expire between a refused SET NX and the GET.
        for _ in range(2):
            if await client.set(key, user_id, nx=True, ex=PREFLIGHT_OWNER_TTL_SECONDS):
                return True
            owner = await client.get(key)
            if owner is not None:
                return owner == user_id
    except Exception as e:
        logger.warning("Preflight owner claim failed: %s", type(e).__name__)
    return False
