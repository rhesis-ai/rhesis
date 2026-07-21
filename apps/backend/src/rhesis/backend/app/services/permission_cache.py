"""Permission decision cache — Redis DB 5.

Wraps the authorization PDP result cache so that ``authorize()`` in
``app/auth/rbac.py`` avoids a DB round-trip on every request.

Cache key format::

    perm:v1:{user_id}:{org_id}:{project_id_or_None}:{permission}:{scope_fp}

``scope_fp`` is a fingerprint of the authenticating token's explicit scopes
(``"*"`` for a session / unscoped token that inherits the owner's full access).
It is part of the key because the EE provider's decision branches on the
token's scope set (``scopes ∩ role_permissions``); without it a wide,
unscoped decision could be served from cache to a narrowly-scoped token,
silently defeating SP9 token scoping.

Design decisions (plan §1.6 / §8b):

* **Own DB.** Redis DB 5 is dedicated so a ``FLUSHDB`` (e.g. in tests) only
  affects permission entries, not Celery jobs or telemetry.
* **Short TTL (45 s).** Sits in the plan-specified 30–60 s window and caps the
  revocation-to-enforcement window even without an explicit bust.
* **In-process fallback.** Inherits ``RedisBackedCache`` semantics: if Redis is
  unreachable, the same API transparently uses an in-memory LRU-with-TTL.
  Authorization still works; it just hits the DB more often.
* **Never cross-org.** The cache key includes both ``user_id`` **and**
  ``org_id``, so a lookup for principal A in org-A can never collide with a key
  for principal A in org-B.
* **Bust by user+org.** ``bust_user(user_id, org_id)`` deletes all cached
  decisions for a user within an org in one Redis ``SCAN`` + ``DEL`` (or an
  in-memory key prefix scan).  Called by
  ``enroll_user_in_project`` / ``unenroll_user_from_project`` for near-instant
  revocation (plan §8b cache-bust requirement).

Usage::

    from rhesis.backend.app.services.permission_cache import get_permission_cache

    cache = get_permission_cache()
    cached = cache.get(user_id, org_id, project_id, "test_set:read")
    if cached is None:
        result = provider.is_authorized(...)
        cache.set(user_id, org_id, project_id, "test_set:read", result)
"""

import logging
from typing import Optional
from uuid import UUID

from rhesis.backend.app.services.cache import RedisBackedCache
from rhesis.backend.app.services.redis_constants import RedisDatabase

logger = logging.getLogger(__name__)

_PERMISSION_CACHE_TTL = 45  # seconds; plan §1.6 specifies 30–60 s
_KEY_PREFIX = "perm:v1"
#: Separate prefix (same Redis DB/TTL) for rbac_active_for()'s org-level
#: "is RBAC licensed/active" flag — cheap to share the connection, distinct
#: key shape (no user_id/project_id/permission) so it can't collide with
#: per-decision keys or get swept by bust_user's per-user prefix scan.
_RBAC_ACTIVE_KEY_PREFIX = "rbac_active:v1"


class PermissionCache(RedisBackedCache):
    """Redis-backed permission-decision cache with in-memory fallback.

    Stores boolean authorization results keyed by
    ``(user_id, org_id, project_id, permission)``.  Falls back to an in-memory
    dict with TTL eviction when Redis is unavailable.
    """

    def __init__(self) -> None:
        super().__init__(
            redis_db=RedisDatabase.PERMISSION_CACHE,
            cache_name="PermissionCache",
            ttl=_PERMISSION_CACHE_TTL,
        )

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(
        user_id: UUID,
        org_id: UUID,
        project_id: Optional[UUID],
        permission: str,
        scope_fingerprint: str = "*",
    ) -> str:
        proj_str = str(project_id) if project_id is not None else "None"
        return f"{_KEY_PREFIX}:{user_id}:{org_id}:{proj_str}:{permission}:{scope_fingerprint}"

    @staticmethod
    def _make_user_org_prefix(user_id: UUID, org_id: UUID) -> str:
        return f"{_KEY_PREFIX}:{user_id}:{org_id}:"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(
        self,
        user_id: UUID,
        org_id: UUID,
        project_id: Optional[UUID],
        permission: str,
        scope_fingerprint: str = "*",
    ) -> Optional[bool]:
        """Return cached decision (``True``/``False``) or ``None`` on miss.

        ``scope_fingerprint`` must identify the authenticating token's scope set
        (``"*"`` for session / unscoped tokens) so a scoped principal never reads
        a decision computed for a differently-scoped one.
        """
        key = self._make_key(user_id, org_id, project_id, permission, scope_fingerprint)
        val = self._get(key)
        if val is None:
            return None
        return val == "1"

    def set(
        self,
        user_id: UUID,
        org_id: UUID,
        project_id: Optional[UUID],
        permission: str,
        result: bool,
        scope_fingerprint: str = "*",
    ) -> None:
        """Store a permission decision in the cache."""
        key = self._make_key(user_id, org_id, project_id, permission, scope_fingerprint)
        self._set(key, "1" if result else "0")

    def get_rbac_active(self, org_id: UUID) -> Optional[bool]:
        """Return the cached "is RBAC active for this org" flag, or ``None`` on miss.

        Used by :func:`~rhesis.backend.app.auth.rbac.rbac_active_for`, which is
        called on every ``authorize()``/``get_effective_permissions()`` call —
        without this, each call re-runs the org lookup just to answer a flag
        that changes only on a plan/license change.
        """
        val = self._get(f"{_RBAC_ACTIVE_KEY_PREFIX}:{org_id}")
        if val is None:
            return None
        return val == "1"

    def set_rbac_active(self, org_id: UUID, result: bool) -> None:
        """Cache the "is RBAC active for this org" flag."""
        self._set(f"{_RBAC_ACTIVE_KEY_PREFIX}:{org_id}", "1" if result else "0")

    def bust_user(self, user_id: UUID, org_id: UUID) -> None:
        """Bust all cached permissions for *user_id* within *org_id*.

        Called after any membership change affecting the user so the next
        ``authorize()`` call re-evaluates against the database.  Handles both
        Redis (SCAN + DEL) and in-memory (prefix scan) modes.
        """
        prefix = self._make_user_org_prefix(user_id, org_id)
        self._delete_by_prefix(prefix)
        logger.debug(
            "PermissionCache: busted all entries for user %s in org %s",
            user_id,
            org_id,
        )

    def clear_all(self) -> None:
        """Clear every entry in this cache.

        For tests (prevents cross-test contamination) and emergency use.
        Issues ``FLUSHDB`` when Redis is connected (DB 5 is dedicated, safe).
        """
        if self._using_redis:
            try:
                self._redis.flushdb()
                logger.debug("PermissionCache: flushed Redis DB %d", self._redis_db)
                return
            except Exception as exc:
                logger.warning("PermissionCache: Redis flushdb failed: %s", exc)

        with self._lock:
            self._memory.clear()
            self._memory_timestamps.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _delete_by_prefix(self, prefix: str) -> None:
        """Delete all keys matching ``prefix*`` via SCAN or in-memory iteration."""
        if self._using_redis:
            try:
                cursor = 0
                while True:
                    cursor, keys = self._redis.scan(cursor, match=f"{prefix}*", count=100)
                    if keys:
                        self._redis.delete(*keys)
                    if cursor == 0:
                        break
                return
            except Exception as exc:
                logger.warning(
                    "PermissionCache: Redis scan/delete failed for prefix '%s': %s",
                    prefix,
                    exc,
                )
                # Fall through to in-memory deletion

        with self._lock:
            stale = [k for k in list(self._memory.keys()) if k.startswith(prefix)]
            for k in stale:
                self._memory.pop(k, None)
                self._memory_timestamps.pop(k, None)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_permission_cache = PermissionCache()


def initialize_cache() -> None:
    """Initialize the permission cache (called at app startup in ``main.py``)."""
    _permission_cache.initialize()


def get_permission_cache() -> PermissionCache:
    """Return the process-global permission cache instance."""
    return _permission_cache
