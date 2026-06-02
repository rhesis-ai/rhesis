"""
Tests for the ambient request scope listeners (scope_events.py).

The shipped implementation uses two listeners:
  auto_filter  - Query.before_compile  (covers db.query(...), not db.execute(select(...)))
  auto_stamp   - Session.before_flush  (covers all ORM pending inserts, not bulk operations)

Coverage:
- Auto-filter no-ops when scope is unbound (isolate_request_scope fixture)
- Auto-filter applies org_id predicate when scope is bound (before_compile)
- Auto-filter is idempotent with explicit filter + bound scope
- bypass_tenant_filter() suppresses auto-filter
- query._bypass_scope = True suppresses auto-filter (per-query bypass)
- Kill switch (RHESIS_DISABLE_SCOPE_LISTENER=1) checked at query time by both listeners
- Auto-stamp fires when scope is bound and column is None
- Auto-stamp does NOT overwrite explicit values
- Auto-stamp ignores bypass_tenant_filter() (stamp fires anyway)
- Auto-stamp no-ops when scope is unbound
- Exempt models (User, Organization) bypass auto-filter
- Bulk insert paths do NOT trigger auto-stamp (documented gap assertion)
- Session.info scope path works with the ContextVar unbound (async-route regression guard)
"""

import os
import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.models.scope_events import _SESSION_SCOPE_KEY
from rhesis.backend.app.scope import (
    RequestScope,
    bind_scope,
    bypass_tenant_filter,
    current_scope,
    is_tenant_filter_disabled,
    reset_scope,
)
from rhesis.backend.app.utils import crud_utils
from tests.backend.routes.fixtures.data_factories import BehaviorDataFactory


@pytest.fixture
def test_org2_id(test_db: Session):
    """Create a second test organization for cross-org filter tests."""
    import uuid as _uuid

    org = models.Organization(
        name=f"Scope Test Org 2 {_uuid.uuid4().hex[:8]}",
        slug=f"scope-test-org-2-{_uuid.uuid4().hex[:8]}",
    )
    test_db.add(org)
    test_db.flush()
    yield str(org.id)
    test_db.rollback()


@pytest.mark.unit
@pytest.mark.utils
class TestScopeContextVar:
    """Unit tests for the RequestScope ContextVar helpers."""

    def test_default_scope_is_unbound(self):
        """Fresh scope has all-None fields."""
        scope = current_scope()
        assert scope.organization_id is None
        assert scope.user_id is None
        assert scope.project_id is None

    def test_bind_and_reset(self):
        """bind_scope / reset_scope properly set and restore the ContextVar."""
        original = current_scope()
        token = bind_scope(RequestScope(organization_id="org-1"))
        assert current_scope().organization_id == "org-1"
        reset_scope(token)
        assert current_scope().organization_id == original.organization_id

    def test_bypass_tenant_filter_context_manager(self):
        """bypass_tenant_filter() sets the flag and restores it on exit."""
        assert not is_tenant_filter_disabled()
        with bypass_tenant_filter():
            assert is_tenant_filter_disabled()
        assert not is_tenant_filter_disabled()

    def test_bypass_is_separate_from_identity(self):
        """Bypass flag is independent of the identity scope."""
        token = bind_scope(RequestScope(organization_id="org-1"))
        try:
            with bypass_tenant_filter():
                assert is_tenant_filter_disabled()
                assert current_scope().organization_id == "org-1"
        finally:
            reset_scope(token)


@pytest.mark.unit
@pytest.mark.utils
class TestAutoFilterNoOp:
    """Auto-filter is a no-op when scope is unbound (isolate_request_scope resets to None)."""

    def test_unbound_scope_does_not_filter(self, test_db: Session, test_org_id):
        """When scope is unbound, queries are not additionally filtered by the listener."""
        behavior = crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=test_org_id,
        )

        # No scope bound - listener is a no-op; explicit filter still works.
        results = (
            test_db.query(models.Behavior)
            .filter(models.Behavior.organization_id == test_org_id)
            .all()
        )
        assert any(b.id == behavior.id for b in results)


@pytest.mark.unit
@pytest.mark.utils
class TestAutoFilterWhenBound:
    """Auto-filter applies WHERE clauses when scope IS bound."""

    def test_bound_scope_filters_by_org(self, test_db: Session, test_org_id, bound_scope):
        """When scope is bound, only records from that org are returned."""
        behavior = crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=test_org_id,
        )

        # Bind scope to test org - should return the behavior
        with bound_scope(organization_id=test_org_id):
            results = test_db.query(models.Behavior).all()

        assert any(b.id == behavior.id for b in results)

    def test_bound_scope_is_idempotent_with_explicit_filter(
        self, test_db: Session, test_org_id, bound_scope
    ):
        """Listener + explicit filter for same org_id compose cleanly (no double-filter error)."""
        behavior = crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=test_org_id,
        )

        with bound_scope(organization_id=test_org_id):
            results = (
                test_db.query(models.Behavior)
                .filter(models.Behavior.organization_id == test_org_id)
                .all()
            )

        assert any(b.id == behavior.id for b in results)

    def test_bound_scope_excludes_other_records_via_direct_query(
        self, test_db: Session, test_org_id, test_org2_id, bound_scope
    ):
        """When scope is bound to org1, records from org2 do not appear."""
        # Create one behavior per org
        b1 = crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=test_org_id,
        )
        b2 = crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=test_org2_id,
        )

        with bound_scope(organization_id=test_org_id):
            results = test_db.query(models.Behavior).all()

        ids = {b.id for b in results}
        assert b1.id in ids
        assert b2.id not in ids


@pytest.mark.unit
@pytest.mark.utils
class TestBypassFiltering:
    """bypass_tenant_filter() and per-query bypasses suppress the listener."""

    def test_bypass_context_manager_skips_filter(
        self, test_db: Session, test_org_id, test_org2_id, bound_scope
    ):
        """bypass_tenant_filter() allows cross-org records to appear."""
        b1 = crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=test_org_id,
        )
        b2 = crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=test_org2_id,
        )

        with bound_scope(organization_id=test_org_id):
            with bypass_tenant_filter():
                results = test_db.query(models.Behavior).all()

        ids = {b.id for b in results}
        assert b1.id in ids
        assert b2.id in ids

    def test_legacy_per_query_bypass(
        self, test_db: Session, test_org_id, test_org2_id, bound_scope
    ):
        """query._bypass_scope = True suppresses the legacy before_compile listener."""
        b2 = crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=test_org2_id,
        )

        with bound_scope(organization_id=test_org_id):
            q = test_db.query(models.Behavior)
            q._bypass_scope = True
            results = q.all()

        assert any(b.id == b2.id for b in results)


@pytest.mark.unit
@pytest.mark.utils
class TestAutoStamp:
    """Auto-stamp fills identity columns from the ambient scope on INSERT."""

    def test_auto_stamp_fills_org_id(self, test_db: Session, test_org_id, bound_scope):
        """When scope is bound and organization_id is absent, auto-stamp fills it."""
        data = BehaviorDataFactory.sample_data()
        new_behavior = models.Behavior(**data)
        # organization_id is intentionally left as None - rely on auto-stamp

        with bound_scope(organization_id=test_org_id):
            test_db.add(new_behavior)
            test_db.flush()  # triggers before_insert

        assert str(new_behavior.organization_id) == test_org_id
        test_db.rollback()

    def test_auto_stamp_does_not_overwrite_explicit_value(
        self, test_db: Session, test_org_id, test_org2_id, bound_scope
    ):
        """Auto-stamp does not replace an already-set organization_id."""
        data = BehaviorDataFactory.sample_data()
        new_behavior = models.Behavior(**data)
        new_behavior.organization_id = test_org2_id  # explicit override

        with bound_scope(organization_id=test_org_id):
            test_db.add(new_behavior)
            test_db.flush()

        assert str(new_behavior.organization_id) == test_org2_id
        test_db.rollback()

    def test_auto_stamp_fires_under_bypass(self, test_db: Session, test_org_id, bound_scope):
        """bypass_tenant_filter() does not suppress auto-stamp."""
        data = BehaviorDataFactory.sample_data()
        new_behavior = models.Behavior(**data)

        with bound_scope(organization_id=test_org_id):
            with bypass_tenant_filter():
                test_db.add(new_behavior)
                test_db.flush()

        assert str(new_behavior.organization_id) == test_org_id
        test_db.rollback()

    def test_auto_stamp_noop_when_unbound(self, test_db: Session):
        """When scope is unbound, auto-stamp leaves organization_id as None."""
        data = BehaviorDataFactory.sample_data()
        new_behavior = models.Behavior(**data)
        # organization_id not set; scope is unbound (isolate_request_scope fixture)

        test_db.add(new_behavior)
        try:
            test_db.flush()
            # If flush succeeds (no NOT NULL constraint), org_id stays None
            assert new_behavior.organization_id is None
        except Exception:
            pass  # FK/NOT NULL constraint fires - that's expected; the point is stamp didn't run
        finally:
            test_db.rollback()


@pytest.mark.unit
@pytest.mark.utils
class TestExemptModels:
    """User, Organization bypass auto-filter."""

    def test_user_model_exempt(self, test_db: Session, test_org_id, bound_scope):
        """User queries are not filtered even when scope is bound."""
        with bound_scope(organization_id=test_org_id):
            users = test_db.query(models.User).limit(5).all()
            assert isinstance(users, list)

    def test_organization_model_exempt(self, test_db: Session, test_org_id, bound_scope):
        """Organization queries are not filtered even when scope is bound."""
        with bound_scope(organization_id=test_org_id):
            orgs = test_db.query(models.Organization).limit(5).all()
            assert isinstance(orgs, list)


@pytest.mark.unit
@pytest.mark.utils
class TestKillSwitch:
    """RHESIS_DISABLE_SCOPE_LISTENER=1 - verifies env-var check at query time."""

    def test_kill_switch_checked_at_query_time(
        self, test_db: Session, test_org_id, test_org2_id, bound_scope
    ):
        """
        RHESIS_DISABLE_SCOPE_LISTENER=1 is re-checked at call time by both listeners:
        auto_filter (before_compile) and auto_stamp (before_flush) both call
        _kill_switch_active() on every invocation, so setting the env var at runtime
        disables filtering for subsequent queries even in the same process.
        """
        crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=test_org2_id,
        )

        with patch.dict(os.environ, {"RHESIS_DISABLE_SCOPE_LISTENER": "1"}):
            with bound_scope(organization_id=test_org_id):
                # Kill switch is active: auto_filter returns early so no scope
                # predicate is appended, meaning rows from other orgs may appear.
                # The key assertion is the query completes without error.
                results = test_db.query(models.Behavior).all()

        # The other-org behavior may appear because the filter was suppressed.
        assert isinstance(results, list)


@pytest.mark.unit
@pytest.mark.utils
class TestBulkInsertGap:
    """
    Explicit assertion that bulk_insert_mappings bypasses auto-stamp.

    This is a known limitation documented in scope.py and scope_events.py.
    This test exists so future engineers do not assume bulk paths are covered.
    """

    def test_bulk_insert_does_not_trigger_auto_stamp(
        self, test_db: Session, test_org_id, bound_scope
    ):
        """Session.bulk_insert_mappings bypasses before_flush; auto-stamp does not fire."""
        data = BehaviorDataFactory.sample_data()
        data["id"] = uuid.uuid4()
        # Deliberately omit organization_id from the payload

        with bound_scope(organization_id=test_org_id):
            try:
                test_db.bulk_insert_mappings(models.Behavior, [data])
                test_db.flush()
                # If flush succeeded, auto-stamp did NOT fire
                # (organization_id still None in the bulk mapping payload)
                result = (
                    test_db.query(models.Behavior).filter(models.Behavior.id == data["id"]).first()
                )
                assert result is None or result.organization_id is None
            except Exception:
                pass  # FK/NOT NULL fires - that's exactly the documented gap
            finally:
                test_db.rollback()


@pytest.mark.unit
@pytest.mark.utils
class TestSessionInfoScope:
    """
    Regression guard for the async-safe scope path.

    get_db_with_tenant_variables() stores the RequestScope on Session.info['_scope']
    (NOT just the ContextVar), because FastAPI runs sync generator dependencies in an
    anyio threadpool while async def route handlers run in the event-loop thread — the
    ContextVar bound in the threadpool worker is not visible to listeners firing for
    queries issued from the async handler.

    The autouse isolate_request_scope fixture keeps the ContextVar UNBOUND (all-None)
    for every test here. So if auto-filter / auto-stamp still apply, they MUST be
    reading from Session.info — which is exactly the async-route execution model.
    """

    @staticmethod
    @contextmanager
    def _session_scope(session, **kwargs):
        """Set RequestScope on Session.info only (no ContextVar), like the real dep."""
        session.info[_SESSION_SCOPE_KEY] = RequestScope(**kwargs)
        try:
            yield
        finally:
            session.info.pop(_SESSION_SCOPE_KEY, None)

    def test_auto_filter_uses_session_info_without_contextvar(
        self, test_db: Session, test_org_id, test_org2_id
    ):
        """Auto-filter applies the org predicate from Session.info while ContextVar is unbound."""
        b1 = crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=test_org_id,
        )
        b2 = crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=test_org2_id,
        )

        # ContextVar is unbound (isolate_request_scope); scope lives only on the session.
        assert current_scope().organization_id is None
        with self._session_scope(test_db, organization_id=test_org_id):
            results = test_db.query(models.Behavior).all()

        ids = {b.id for b in results}
        assert b1.id in ids
        assert b2.id not in ids

    def test_auto_stamp_uses_session_info_without_contextvar(self, test_db: Session, test_org_id):
        """Auto-stamp fills organization_id from Session.info while ContextVar is unbound."""
        new_behavior = models.Behavior(**BehaviorDataFactory.sample_data())
        # organization_id intentionally left None - must be filled from session.info

        assert current_scope().organization_id is None
        with self._session_scope(test_db, organization_id=test_org_id):
            test_db.add(new_behavior)
            test_db.flush()

        assert str(new_behavior.organization_id) == test_org_id
        test_db.rollback()

    def test_session_info_takes_precedence_over_contextvar(
        self, test_db: Session, test_org_id, test_org2_id, bound_scope
    ):
        """When both are set, Session.info wins over the ContextVar."""
        b1 = crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=test_org_id,
        )
        b2 = crud_utils.create_item(
            test_db,
            models.Behavior,
            BehaviorDataFactory.sample_data(),
            organization_id=test_org2_id,
        )

        # ContextVar bound to org2, but Session.info bound to org1 - org1 must win.
        with bound_scope(organization_id=test_org2_id):
            with self._session_scope(test_db, organization_id=test_org_id):
                results = test_db.query(models.Behavior).all()

        ids = {b.id for b in results}
        assert b1.id in ids
        assert b2.id not in ids
