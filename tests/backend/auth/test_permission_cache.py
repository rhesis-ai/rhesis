"""SP5 — Permission cache tests.

Covers all four exit criteria from the SP5 scope:

1. **hit/miss** — ``PermissionCache.get`` returns ``None`` on miss and the
   cached value on hit; ``authorize()`` skips the DB provider on a cache hit.
2. **revocation-timing** — a membership write calls ``bust_user`` which
   invalidates the cache, causing the next ``authorize()`` call to go back to
   the DB for a fresh result.
3. **in-process fallback** — when Redis is not initialized (unit-test mode),
   the cache transparently uses an in-memory dict so ``authorize()`` still
   works correctly.
4. **never-cross-org** — a cache entry for principal A in org-1 is never
   returned for the same user in org-2, and a bust for user+org-1 does not
   affect a cached entry for user+org-2.

Test naming convention: ``test_<subject>_<condition>_<expected>``
All tests are pure unit tests — no DB, no Redis.  SQLAlchemy queries are
mocked via ``unittest.mock.MagicMock``.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from rhesis.backend.app.auth.principal import Principal
from rhesis.backend.app.auth.rbac import (
    _AuthorizationRegistry,
    authorize,
)
from rhesis.backend.app.services.permission_cache import PermissionCache, get_permission_cache

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

ORG_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()
OTHER_ORG_ID = uuid.uuid4()
OTHER_PROJECT_ID = uuid.uuid4()


def _principal(
    user_id=USER_ID,
    organization_id=ORG_ID,
    kind: str = "session",
) -> Principal:
    return Principal(user_id=user_id, organization_id=organization_id, kind=kind)


def _mock_db(*, is_owner: bool, is_member: bool) -> MagicMock:
    """Minimal DB mock that drives DefaultAuthorizationProvider decisions."""
    db = MagicMock()

    def _query_side_effect(model):
        q = MagicMock()

        def _filter_by(**kwargs):
            fq = MagicMock()
            if "owner_id" in kwargs:
                fq.first.return_value = MagicMock() if is_owner else None
            else:
                fq.first.return_value = MagicMock() if is_member else None
            return fq

        q.filter_by.side_effect = _filter_by
        return q

    db.query.side_effect = _query_side_effect
    return db


# ===========================================================================
# 1. PermissionCache unit tests (pure in-memory, no Redis)
# ===========================================================================


class TestPermissionCacheUnit:
    """Test PermissionCache in isolation using its in-memory mode."""

    def setup_method(self):
        self.cache = PermissionCache()
        # Deliberately NOT calling initialize() — stays in in-memory mode.

    # --- miss ---

    def test_get_uninitialised_returns_none(self):
        result = self.cache.get(USER_ID, ORG_ID, PROJECT_ID, "test_set:read")
        assert result is None

    def test_get_unknown_key_returns_none(self):
        self.cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)
        assert self.cache.get(USER_ID, ORG_ID, PROJECT_ID, "test_set:write") is None

    # --- hit ---

    def test_set_allow_then_get_returns_true(self):
        self.cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)
        assert self.cache.get(USER_ID, ORG_ID, PROJECT_ID, "test_set:read") is True

    def test_set_deny_then_get_returns_false(self):
        self.cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", False)
        assert self.cache.get(USER_ID, ORG_ID, PROJECT_ID, "test_set:read") is False

    def test_none_project_stored_and_retrieved(self):
        self.cache.set(USER_ID, ORG_ID, None, "organization:update", True)
        assert self.cache.get(USER_ID, ORG_ID, None, "organization:update") is True

    # --- key uniqueness (never-cross-org / never-cross-project) ---

    def test_different_org_is_a_miss(self):
        """An allow for (user, org1, project) must NOT appear for (user, org2, project)."""
        self.cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)
        assert self.cache.get(USER_ID, OTHER_ORG_ID, PROJECT_ID, "test_set:read") is None

    def test_different_project_is_a_miss(self):
        """An allow for project A must NOT appear for project B."""
        self.cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)
        assert self.cache.get(USER_ID, ORG_ID, OTHER_PROJECT_ID, "test_set:read") is None

    def test_none_project_distinct_from_explicit_project(self):
        """An org-scoped result (project_id=None) must not bleed into a project-scoped one."""
        self.cache.set(USER_ID, ORG_ID, None, "organization:update", True)
        assert self.cache.get(USER_ID, ORG_ID, PROJECT_ID, "organization:update") is None

    def test_different_user_is_a_miss(self):
        self.cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)
        assert self.cache.get(OTHER_USER_ID, ORG_ID, PROJECT_ID, "test_set:read") is None

    def test_different_permission_is_a_miss(self):
        self.cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)
        assert self.cache.get(USER_ID, ORG_ID, PROJECT_ID, "test_set:delete") is None

    # --- bust_user ---

    def test_bust_user_clears_all_entries_for_user_org(self):
        """bust_user must remove every cached permission for (user, org)."""
        self.cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)
        self.cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:delete", True)
        self.cache.set(USER_ID, ORG_ID, None, "organization:update", True)

        self.cache.bust_user(USER_ID, ORG_ID)

        assert self.cache.get(USER_ID, ORG_ID, PROJECT_ID, "test_set:read") is None
        assert self.cache.get(USER_ID, ORG_ID, PROJECT_ID, "test_set:delete") is None
        assert self.cache.get(USER_ID, ORG_ID, None, "organization:update") is None

    def test_bust_user_does_not_affect_other_users(self):
        """A bust for user A must leave user B's entries intact."""
        self.cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)
        self.cache.set(OTHER_USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)

        self.cache.bust_user(USER_ID, ORG_ID)

        assert self.cache.get(OTHER_USER_ID, ORG_ID, PROJECT_ID, "test_set:read") is True

    def test_bust_user_does_not_affect_other_orgs(self):
        """Busting (user, org1) must not clear (user, org2) entries."""
        self.cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)
        self.cache.set(USER_ID, OTHER_ORG_ID, PROJECT_ID, "test_set:read", True)

        self.cache.bust_user(USER_ID, ORG_ID)

        assert self.cache.get(USER_ID, OTHER_ORG_ID, PROJECT_ID, "test_set:read") is True

    def test_bust_user_on_empty_cache_is_a_noop(self):
        """bust_user on a cache with no entries must not raise."""
        self.cache.bust_user(USER_ID, ORG_ID)

    # --- clear_all ---

    def test_clear_all_empties_everything(self):
        self.cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)
        self.cache.set(OTHER_USER_ID, OTHER_ORG_ID, None, "organization:update", False)

        self.cache.clear_all()

        assert self.cache.get(USER_ID, ORG_ID, PROJECT_ID, "test_set:read") is None
        assert self.cache.get(OTHER_USER_ID, OTHER_ORG_ID, None, "organization:update") is None


# ===========================================================================
# 2. Redis-mode unit tests (mocked Redis client)
# ===========================================================================


class TestPermissionCacheRedisMode:
    """Verify Redis-path code branches using a mocked redis client."""

    def _make_redis_cache(self) -> PermissionCache:
        """Return a PermissionCache with a fake Redis client injected."""
        cache = PermissionCache()
        # Inject a mock Redis client so _using_redis returns True.
        mock_redis = MagicMock()
        # Simulate an empty store for scan (cursor=0, no keys).
        mock_redis.scan.return_value = (0, [])
        cache._redis = mock_redis
        cache._redis_read = mock_redis
        cache._initialized = True
        return cache

    def test_get_calls_redis_get(self):
        cache = self._make_redis_cache()
        cache._redis_read.get.return_value = "1"

        result = cache.get(USER_ID, ORG_ID, PROJECT_ID, "test_set:read")

        assert result is True
        cache._redis_read.get.assert_called_once()

    def test_get_miss_returns_none_when_redis_returns_none(self):
        cache = self._make_redis_cache()
        cache._redis_read.get.return_value = None

        result = cache.get(USER_ID, ORG_ID, PROJECT_ID, "test_set:read")

        assert result is None

    def test_set_calls_redis_set(self):
        cache = self._make_redis_cache()
        cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)
        cache._redis.set.assert_called_once()
        _, kwargs = cache._redis.set.call_args
        assert kwargs.get("ex") is not None  # TTL (ex) must be set

    def test_bust_user_uses_scan_delete(self):
        cache = self._make_redis_cache()
        key = cache._make_key(USER_ID, ORG_ID, PROJECT_ID, "test_set:read")
        cache._redis.scan.return_value = (0, [key])

        cache.bust_user(USER_ID, ORG_ID)

        cache._redis.scan.assert_called_once()
        cache._redis.delete.assert_called_once_with(key)

    def test_bust_user_scan_no_keys_skips_delete(self):
        cache = self._make_redis_cache()
        cache._redis.scan.return_value = (0, [])

        cache.bust_user(USER_ID, ORG_ID)

        cache._redis.delete.assert_not_called()

    def test_clear_all_calls_flushdb(self):
        cache = self._make_redis_cache()
        cache.clear_all()
        cache._redis.flushdb.assert_called_once()

    def test_redis_set_failure_falls_back_to_memory(self):
        """If Redis raises on _set, the value is stored in memory instead."""
        cache = self._make_redis_cache()
        cache._redis.set.side_effect = ConnectionError("redis down")

        cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)

        # In-memory fallback should have the value.
        with cache._lock:
            key = cache._make_key(USER_ID, ORG_ID, PROJECT_ID, "test_set:read")
            assert cache._memory.get(key) == "1"

    def test_redis_scan_failure_falls_back_to_memory_bust(self):
        """If Redis SCAN raises, bust_user falls back to in-memory key scan."""
        cache = self._make_redis_cache()
        cache._redis.scan.side_effect = ConnectionError("redis down")

        # Prime the in-memory store as well (simulates the fallback layer).
        key = cache._make_key(USER_ID, ORG_ID, PROJECT_ID, "test_set:read")
        with cache._lock:
            cache._memory[key] = "1"
            cache._memory_timestamps[key] = 0.0

        cache.bust_user(USER_ID, ORG_ID)

        with cache._lock:
            assert key not in cache._memory


# ===========================================================================
# 3. authorize() + cache integration
# ===========================================================================


class _AuthzCacheTestBase:
    """Shared setup/teardown: reset the provider registry and flush the cache."""

    def setup_method(self):
        _AuthorizationRegistry.reset()
        get_permission_cache().clear_all()

    def teardown_method(self):
        _AuthorizationRegistry.reset()
        get_permission_cache().clear_all()


class TestAuthorizeWithCache(_AuthzCacheTestBase):
    """Verify that authorize() correctly uses the process-global permission cache."""

    # --- cache hit skips DB ---

    def test_cache_hit_skips_db_provider(self):
        """Second authorize() call must return the cached result without hitting the DB."""
        p = _principal()
        db_allow = _mock_db(is_owner=True, is_member=False)

        result1 = authorize(p, "test_set:read", project_id=PROJECT_ID, db=db_allow)
        assert result1 is True

        # DB that would deny if consulted.
        db_deny = _mock_db(is_owner=False, is_member=False)
        result2 = authorize(p, "test_set:read", project_id=PROJECT_ID, db=db_deny)

        assert result2 is True  # cache hit — stale DB not used

    def test_deny_result_is_also_cached(self):
        """A False result must be cached and returned on the next call."""
        p = _principal()
        db_deny = _mock_db(is_owner=False, is_member=False)

        result1 = authorize(p, "test_set:read", project_id=PROJECT_ID, db=db_deny)
        assert result1 is False

        # DB that would allow if consulted.
        db_allow = _mock_db(is_owner=True, is_member=True)
        result2 = authorize(p, "test_set:read", project_id=PROJECT_ID, db=db_allow)

        assert result2 is False  # deny is cached

    def test_different_permissions_cached_independently(self):
        """Cache entries are per-permission; a hit for one must not mask another."""
        p = _principal()
        db = _mock_db(is_owner=True, is_member=False)

        authorize(p, "test_set:read", project_id=PROJECT_ID, db=db)
        result = authorize(p, "test_set:delete", project_id=PROJECT_ID, db=db)

        assert result is True  # own DB call, not a mismatched cache hit

    # --- in-process fallback (Redis not initialized) ---

    def test_in_process_fallback_works_without_redis(self):
        """With Redis unavailable, in-memory cache still provides hit/miss semantics."""
        # The global cache is never initialized in unit tests, so it is already
        # operating in in-memory mode.  No additional setup needed.
        p = _principal()
        db_allow = _mock_db(is_owner=True, is_member=False)

        authorize(p, "test_set:read", project_id=PROJECT_ID, db=db_allow)

        db_deny = _mock_db(is_owner=False, is_member=False)
        result = authorize(p, "test_set:read", project_id=PROJECT_ID, db=db_deny)

        assert result is True  # served from in-memory cache

    # --- exception path not cached ---

    def test_provider_exception_not_cached(self):
        """A deny caused by a provider exception must NOT be cached."""
        p = _principal()
        db_broken = MagicMock()
        db_broken.query.side_effect = RuntimeError("DB exploded")

        result1 = authorize(p, "test_set:read", project_id=PROJECT_ID, db=db_broken)
        assert result1 is False  # fail-closed

        # Next call with a working DB should NOT get a cached False.
        db_allow = _mock_db(is_owner=True, is_member=False)
        result2 = authorize(p, "test_set:read", project_id=PROJECT_ID, db=db_allow)
        assert result2 is True

    # --- no-org principal not cached ---

    def test_no_org_principal_result_not_cached(self):
        """Results for principals with no org context must never be stored in the cache."""
        p_no_org = Principal(user_id=USER_ID, organization_id=None, kind="session")
        db = _mock_db(is_owner=False, is_member=False)

        result = authorize(p_no_org, "test_set:read", project_id=PROJECT_ID, db=db)
        assert result is False

        # Verify nothing was written for this user under any org.
        cached = get_permission_cache().get(USER_ID, ORG_ID, PROJECT_ID, "test_set:read")
        assert cached is None

    # --- never-cross-org ---

    def test_never_cross_org_separate_principals(self):
        """A cache entry for (user, org1) must NOT be returned for (user, org2)."""
        p_org1 = _principal(organization_id=ORG_ID)
        p_org2 = _principal(organization_id=OTHER_ORG_ID)

        db_allow = _mock_db(is_owner=True, is_member=False)
        authorize(p_org1, "test_set:read", project_id=PROJECT_ID, db=db_allow)

        # org2 principal — DB would deny.
        db_deny = _mock_db(is_owner=False, is_member=False)
        result = authorize(p_org2, "test_set:read", project_id=PROJECT_ID, db=db_deny)

        assert result is False  # no cross-org cache hit

    def test_never_cross_org_same_user_different_orgs_cached_independently(self):
        """Same user_id with two different orgs must store and retrieve independently."""
        p1 = _principal(organization_id=ORG_ID)
        p2 = _principal(organization_id=OTHER_ORG_ID)

        db_allow = _mock_db(is_owner=True, is_member=False)
        db_deny = _mock_db(is_owner=False, is_member=False)

        authorize(p1, "test_set:read", project_id=PROJECT_ID, db=db_allow)  # True → cached
        authorize(p2, "test_set:read", project_id=PROJECT_ID, db=db_deny)   # False → cached

        # Verify both are independently stored.
        cache = get_permission_cache()
        assert cache.get(USER_ID, ORG_ID, PROJECT_ID, "test_set:read") is True
        assert cache.get(USER_ID, OTHER_ORG_ID, PROJECT_ID, "test_set:read") is False


# ===========================================================================
# 4. Revocation-timing tests
# ===========================================================================


class TestRevocationTiming(_AuthzCacheTestBase):
    """Verify that bust_user causes authorize() to re-read from the DB."""

    def test_bust_user_causes_fresh_db_read_on_next_authorize(self):
        """After bust_user the next authorize() must consult the DB, not the cache."""
        p = _principal()
        cache = get_permission_cache()

        # Prime cache: allow.
        db_allow = _mock_db(is_owner=True, is_member=False)
        result1 = authorize(p, "test_set:read", project_id=PROJECT_ID, db=db_allow)
        assert result1 is True

        # Bust cache (simulates membership removal).
        cache.bust_user(USER_ID, ORG_ID)
        assert cache.get(USER_ID, ORG_ID, PROJECT_ID, "test_set:read") is None

        # Next call must go to DB; DB now returns deny.
        db_deny = _mock_db(is_owner=False, is_member=False)
        result2 = authorize(p, "test_set:read", project_id=PROJECT_ID, db=db_deny)
        assert result2 is False

    def test_enroll_busts_cache(self):
        """enroll_user_in_project must bust the permission cache for the user."""
        from rhesis.backend.app.services.organization import enroll_user_in_project

        # Prime cache with a deny.
        get_permission_cache().set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", False)

        db = MagicMock()
        db.execute.return_value = None

        with patch(
            "rhesis.backend.app.services.organization._set_default_project_if_empty"
        ):
            enroll_user_in_project(db, USER_ID, PROJECT_ID, ORG_ID)

        # Cache must be busted.
        assert get_permission_cache().get(USER_ID, ORG_ID, PROJECT_ID, "test_set:read") is None

    def test_unenroll_busts_cache(self):
        """unenroll_user_from_project must bust the permission cache for the user."""
        from rhesis.backend.app.services.organization import unenroll_user_from_project

        # Prime cache with an allow.
        get_permission_cache().set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)

        # Build a minimal DB mock that satisfies the unenroll guard path.
        db = MagicMock()
        project_mock = MagicMock()
        project_mock.owner_id = OTHER_USER_ID  # not USER_ID, so no owner guard
        membership_mock = MagicMock()

        def _query(model):
            from rhesis.backend.app.models.project import Project
            from rhesis.backend.app.models.project_membership import ProjectMembership

            q = MagicMock()
            if model is Project:
                q.filter.return_value.first.return_value = project_mock
            elif model is ProjectMembership:
                fq = MagicMock()
                fq.first.return_value = membership_mock
                q.filter_by.return_value = fq
            else:
                q.filter.return_value.first.return_value = None
                q.filter_by.return_value.first.return_value = None
            return q

        db.query.side_effect = _query

        with patch(
            "rhesis.backend.app.services.organization._reassign_default_project_if_removed"
        ):
            result = unenroll_user_from_project(
                db, USER_ID, PROJECT_ID, ORG_ID, requester_user_id=OTHER_USER_ID
            )

        assert result is True
        # Cache must be busted.
        assert get_permission_cache().get(USER_ID, ORG_ID, PROJECT_ID, "test_set:read") is None

    def test_bust_one_user_does_not_revoke_another(self):
        """A membership change for user A must not invalidate user B's cache."""
        p_b = _principal(user_id=OTHER_USER_ID)
        cache = get_permission_cache()

        # Prime cache for user B.
        cache.set(OTHER_USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)

        # Bust only user A.
        cache.bust_user(USER_ID, ORG_ID)

        # User B's entry must be intact.
        assert cache.get(OTHER_USER_ID, ORG_ID, PROJECT_ID, "test_set:read") is True

        # And authorize() for user B must still return the cached True without hitting DB.
        db_deny = _mock_db(is_owner=False, is_member=False)
        result = authorize(p_b, "test_set:read", project_id=PROJECT_ID, db=db_deny)
        assert result is True  # cache hit, DB not consulted

    def test_result_re_cached_after_bust(self):
        """After a bust the fresh DB result must be stored in the cache again."""
        p = _principal()
        cache = get_permission_cache()

        # Prime, bust, then re-evaluate.
        db_allow = _mock_db(is_owner=True, is_member=False)
        authorize(p, "test_set:read", project_id=PROJECT_ID, db=db_allow)
        cache.bust_user(USER_ID, ORG_ID)

        db_deny = _mock_db(is_owner=False, is_member=False)
        authorize(p, "test_set:read", project_id=PROJECT_ID, db=db_deny)

        # The deny result must now be in the cache.
        assert cache.get(USER_ID, ORG_ID, PROJECT_ID, "test_set:read") is False

    def test_unenroll_all_busts_each_member(self):
        """unenroll_all_project_members must bust the cache for every removed member."""
        from rhesis.backend.app.services.organization import unenroll_all_project_members

        cache = get_permission_cache()
        cache.set(USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)
        cache.set(OTHER_USER_ID, ORG_ID, PROJECT_ID, "test_set:read", True)

        # Build DB mock returning two memberships.
        db = MagicMock()
        m1 = MagicMock()
        m1.user_id = USER_ID
        m2 = MagicMock()
        m2.user_id = OTHER_USER_ID

        def _query(model):
            q = MagicMock()
            q.filter_by.return_value.all.return_value = [m1, m2]
            return q

        db.query.side_effect = _query
        db.flush.return_value = None

        with patch(
            "rhesis.backend.app.services.organization._reassign_default_project_if_removed"
        ):
            count = unenroll_all_project_members(db, PROJECT_ID, ORG_ID)

        assert count == 2
        assert cache.get(USER_ID, ORG_ID, PROJECT_ID, "test_set:read") is None
        assert cache.get(OTHER_USER_ID, ORG_ID, PROJECT_ID, "test_set:read") is None


# ===========================================================================
# 5. Key-format sanity checks
# ===========================================================================


class TestCacheKeyFormat:
    """Verify that the key format encodes all four dimensions unambiguously."""

    def test_key_contains_all_four_components(self):
        key = PermissionCache._make_key(USER_ID, ORG_ID, PROJECT_ID, "test_set:read")
        assert str(USER_ID) in key
        assert str(ORG_ID) in key
        assert str(PROJECT_ID) in key
        assert "test_set:read" in key

    def test_key_none_project_uses_none_literal(self):
        key = PermissionCache._make_key(USER_ID, ORG_ID, None, "organization:update")
        assert ":None:" in key

    def test_prefix_is_versioned(self):
        key = PermissionCache._make_key(USER_ID, ORG_ID, PROJECT_ID, "x:y")
        assert key.startswith("perm:v1:")

    def test_user_org_prefix_is_a_prefix_of_the_key(self):
        key = PermissionCache._make_key(USER_ID, ORG_ID, PROJECT_ID, "test_set:read")
        prefix = PermissionCache._make_user_org_prefix(USER_ID, ORG_ID)
        assert key.startswith(prefix)

    def test_user_org_prefix_does_not_match_different_org(self):
        prefix = PermissionCache._make_user_org_prefix(USER_ID, ORG_ID)
        other_key = PermissionCache._make_key(USER_ID, OTHER_ORG_ID, PROJECT_ID, "test_set:read")
        assert not other_key.startswith(prefix)
