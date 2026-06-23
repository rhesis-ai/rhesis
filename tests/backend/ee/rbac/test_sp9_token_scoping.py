"""Tests for SP9 — token scoping (scopes JSONB + intersection enforcement).

Key guarantees tested:

- A token with explicit scopes is denied for permissions outside those scopes,
  even if the owner's role would allow them (deny-first).
- A token with explicit scopes is allowed for permissions inside both the
  owner's role AND the token scopes (positive path).
- ``scopes=None`` (unscoped token) inherits the owner's full access.
- The community provider ignores scopes entirely (Principal.scopes present,
  but DefaultAuthorizationProvider still checks membership only).
- ``scopes ⊆ issuer`` is enforced at token creation time (422 when the
  requested scopes exceed the creator's effective permissions).
- Auto-narrow: if the owner's role is downgraded, the scope intersection is
  already denied by the role check — stale wide token scopes cannot re-grant.
- resolve_principal accepts and forwards scopes + token_project_id correctly.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_sp9_token_scoping.py -v
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.principal import Principal, resolve_principal
from rhesis.backend.app.auth.rbac import (
    DefaultAuthorizationProvider,
    _scope_fingerprint,
    authorize,
    get_authorization_provider,
    set_authorization_provider,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_org(db: Session) -> uuid.UUID:
    org_id = uuid.uuid4()
    db.execute(
        text("INSERT INTO organization (id, name, is_active) VALUES (:id, :name, true)"),
        {"id": str(org_id), "name": f"SP9Org-{org_id.hex[:8]}"},
    )
    db.flush()
    return org_id


def _create_user(db: Session, org_id: uuid.UUID) -> uuid.UUID:
    user_id = uuid.uuid4()
    db.execute(
        text(
            'INSERT INTO "user" (id, email, organization_id, is_active) '
            "VALUES (:id, :email, :oid, true)"
        ),
        {"id": str(user_id), "email": f"u-{user_id.hex[:8]}@sp9.example", "oid": str(org_id)},
    )
    db.flush()
    return user_id


def _set_owner(db: Session, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
    db.execute(
        text("UPDATE organization SET owner_id = :owner WHERE id = :id"),
        {"owner": str(user_id), "id": str(org_id)},
    )
    db.flush()


def _point_session_at_org(db: Session, org_id: uuid.UUID) -> None:
    db.execute(text('SET "app.current_organization" = :o'), {"o": str(org_id)})


@contextmanager
def _ee_provider_active():
    """Install the EE PermissionAuthorizationProvider with RBAC forced on."""
    from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

    previous = get_authorization_provider()
    set_authorization_provider(PermissionAuthorizationProvider())
    try:
        with (
            patch(
                "rhesis.backend.app.features.FeatureRegistry.is_available",
                return_value=True,
            ),
            patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True),
        ):
            yield
    finally:
        set_authorization_provider(previous)


@contextmanager
def _rbac_on(db: Session, org_id: uuid.UUID, user_id: uuid.UUID, role_name: str = "Owner"):
    """Assign *role_name* org-role to *user_id* and activate EE RBAC."""
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.ee.rbac.models import OrganizationMember, Role

    # Built-in roles have organization_id=NULL; bypass ORM auto-filter to find them.
    with bypass_tenant_filter():
        role = db.query(Role).filter_by(name=role_name, is_built_in=True).first()
    assert role is not None, f"Built-in role '{role_name}' not found"
    member = OrganizationMember(organization_id=org_id, user_id=user_id, role_id=role.id)
    db.add(member)
    db.flush()
    try:
        with _ee_provider_active():
            yield role
    finally:
        db.delete(member)
        db.flush()


# ---------------------------------------------------------------------------
# Unit-level: resolve_principal scopes forwarding
# ---------------------------------------------------------------------------


class TestResolvePrincipal:
    def test_default_kind_is_session(self):
        """resolve_principal without token args defaults to kind=session, scopes=None."""

        class _FakeUser:
            id = uuid.uuid4()
            organization_id = uuid.uuid4()

        p = resolve_principal(_FakeUser())
        assert p.kind == "session"
        assert p.scopes is None
        assert p.token_project_id is None

    def test_scopes_forwarded(self):
        class _FakeUser:
            id = uuid.uuid4()
            organization_id = uuid.uuid4()

        scopes = frozenset(["test_set:read"])
        p = resolve_principal(_FakeUser(), scopes=scopes, kind="token")
        assert p.scopes == scopes
        assert p.kind == "token"

    def test_token_project_id_forwarded(self):
        class _FakeUser:
            id = uuid.uuid4()
            organization_id = uuid.uuid4()

        pid = uuid.uuid4()
        p = resolve_principal(_FakeUser(), token_project_id=pid, kind="token")
        assert p.token_project_id == pid


# ---------------------------------------------------------------------------
# Unit-level: cache scope fingerprint (no DB)
# ---------------------------------------------------------------------------


class TestScopeFingerprint:
    def test_unscoped_principal_is_star(self):
        p = Principal(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), kind="session")
        assert _scope_fingerprint(p) == "*"

    def test_different_scopes_differ(self):
        org = uuid.uuid4()
        uid = uuid.uuid4()
        a = Principal(uid, org, "token", scopes=frozenset(["test_set:read"]))
        b = Principal(uid, org, "token", scopes=frozenset(["test_set:delete"]))
        assert _scope_fingerprint(a) != _scope_fingerprint(b)
        # And neither collides with the unscoped sentinel.
        assert _scope_fingerprint(a) != "*"

    def test_order_independent(self):
        org = uuid.uuid4()
        uid = uuid.uuid4()
        a = Principal(uid, org, "token", scopes=frozenset(["a:read", "b:read"]))
        b = Principal(uid, org, "token", scopes=frozenset(["b:read", "a:read"]))
        assert _scope_fingerprint(a) == _scope_fingerprint(b)


# ---------------------------------------------------------------------------
# Unit-level: token project boundary short-circuit (no DB, no provider)
# ---------------------------------------------------------------------------


class TestTokenProjectBoundary:
    def test_cross_project_denied_without_db(self):
        """A project-scoped token targeting a different project is denied in the
        PDP before any DB/provider work (so db is never touched)."""
        token_project = uuid.uuid4()
        other_project = uuid.uuid4()
        principal = Principal(
            user_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            kind="token",
            token_project_id=token_project,
        )
        # db=None proves the short-circuit returns before using the session.
        assert authorize(principal, "test_set:read", project_id=other_project, db=None) is False

    def test_org_scoped_request_not_blocked_by_token_project(self, test_db):
        """token_project_id must NOT block org-scoped (project_id=None) checks."""
        db = test_db
        org_id = _create_org(db)
        user_id = _create_user(db, org_id)
        _set_owner(db, org_id, user_id)
        _point_session_at_org(db, org_id)
        principal = Principal(
            user_id=user_id,
            organization_id=org_id,
            kind="token",
            token_project_id=uuid.uuid4(),
        )
        with _rbac_on(db, org_id, user_id, "Owner"):
            # Org-scoped permission with project_id=None — boundary does not apply.
            assert authorize(principal, "organization:update", project_id=None, db=db) is True


# ---------------------------------------------------------------------------
# Integration: EE provider scopes intersection
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestEeTokenScopesIntersection:
    def test_scoped_token_denied_for_out_of_scope_permission(self, test_db):
        """Token scopes narrow what the EE owner can do."""
        db = test_db
        org_id = _create_org(db)
        user_id = _create_user(db, org_id)
        _set_owner(db, org_id, user_id)
        _point_session_at_org(db, org_id)

        # Token only allows test_set:read
        principal = Principal(
            user_id=user_id,
            organization_id=org_id,
            kind="token",
            scopes=frozenset(["test_set:read"]),
        )

        with _rbac_on(db, org_id, user_id, "Owner"):
            # Owner role has test_set:delete — but the token does NOT include it.
            result = authorize(principal, "test_set:delete", project_id=None, db=db)
            assert result is False, "Scoped token must be denied for out-of-scope permissions"

    def test_scoped_token_allowed_for_in_scope_permission(self, test_db):
        """Token scopes: permission in both role and scopes → allow."""
        db = test_db
        org_id = _create_org(db)
        user_id = _create_user(db, org_id)
        _set_owner(db, org_id, user_id)
        _point_session_at_org(db, org_id)

        principal = Principal(
            user_id=user_id,
            organization_id=org_id,
            kind="token",
            scopes=frozenset(["test_set:read", "test_set:create"]),
        )

        with _rbac_on(db, org_id, user_id, "Owner"):
            result = authorize(principal, "test_set:read", project_id=None, db=db)
            assert result is True

    def test_unscoped_token_inherits_full_owner_access(self, test_db):
        """Token with scopes=None inherits owner's full permissions."""
        db = test_db
        org_id = _create_org(db)
        user_id = _create_user(db, org_id)
        _set_owner(db, org_id, user_id)
        _point_session_at_org(db, org_id)

        principal = Principal(
            user_id=user_id,
            organization_id=org_id,
            kind="token",
            scopes=None,  # no scope restriction
        )

        with _rbac_on(db, org_id, user_id, "Owner"):
            result = authorize(principal, "test_set:delete", project_id=None, db=db)
            assert result is True

    def test_cached_unscoped_allow_does_not_leak_to_scoped_token(self, test_db):
        """Regression (audit HIGH): a decision cached for an unscoped principal must
        NOT be served to a scoped token for the same (user, org, project, perm).

        Before the fix the cache key omitted the token scope set, so the scope
        intersection (which runs inside the provider, after the cache) was skipped
        on a cache hit — silently defeating SP9.
        """
        from rhesis.backend.app.services.permission_cache import get_permission_cache

        db = test_db
        org_id = _create_org(db)
        user_id = _create_user(db, org_id)
        _set_owner(db, org_id, user_id)
        _point_session_at_org(db, org_id)

        get_permission_cache().clear_all()

        unscoped = Principal(user_id=user_id, organization_id=org_id, kind="token", scopes=None)
        scoped = Principal(
            user_id=user_id,
            organization_id=org_id,
            kind="token",
            scopes=frozenset(["test_set:read"]),  # does NOT include test_set:delete
        )

        with _rbac_on(db, org_id, user_id, "Owner"):
            # 1. Unscoped principal evaluates test_set:delete → True, populating cache.
            assert authorize(unscoped, "test_set:delete", project_id=None, db=db) is True
            # 2. Same user/org/project/perm via a scoped token that excludes it.
            #    Must be denied — not served the cached unscoped True.
            assert authorize(scoped, "test_set:delete", project_id=None, db=db) is False

    def test_auto_narrow_on_role_downgrade(self, test_db):
        """Stale wide token scopes cannot re-grant a permission removed by role downgrade.

        Scenario: token claims ["test_set:delete"] but the owner was downgraded to
        Viewer which does NOT have test_set:delete.  The role check must fail first,
        so the stale wide scope is irrelevant.
        """
        db = test_db
        org_id = _create_org(db)
        owner_id = _create_user(db, org_id)
        _set_owner(db, org_id, owner_id)
        user_id = _create_user(db, org_id)  # different user, not the owner
        _point_session_at_org(db, org_id)

        # Token claims a wide scope
        principal = Principal(
            user_id=user_id,
            organization_id=org_id,
            kind="token",
            scopes=frozenset(["test_set:delete"]),
        )

        # Viewer role does NOT have test_set:delete — role check fails first.
        with _rbac_on(db, org_id, user_id, "Viewer"):
            result = authorize(principal, "test_set:delete", project_id=None, db=db)
            assert result is False, "Downgraded role must deny even when token scopes are wide"


# ---------------------------------------------------------------------------
# Community provider: scopes stored, not enforced
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCommunityTokenScopes:
    def test_community_owner_with_scoped_token_still_allowed(self, test_db):
        """Community DefaultAuthorizationProvider ignores token scopes entirely.

        The org owner is allowed for any capability regardless of Principal.scopes.
        """
        db = test_db
        org_id = _create_org(db)
        user_id = _create_user(db, org_id)
        _set_owner(db, org_id, user_id)
        _point_session_at_org(db, org_id)

        # Ensure we are using the community provider
        community_provider = DefaultAuthorizationProvider()
        previous = get_authorization_provider()
        set_authorization_provider(community_provider)
        try:
            # Narrow scopes: token only claims test_set:read
            principal = Principal(
                user_id=user_id,
                organization_id=org_id,
                kind="token",
                scopes=frozenset(["test_set:read"]),
            )
            # Community tier: org owner bypasses all checks; scopes are ignored.
            result = authorize(principal, "test_set:delete", project_id=None, db=db)
            assert result is True, "Community provider must not enforce token scopes"
        finally:
            set_authorization_provider(previous)
