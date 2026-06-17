"""Tests for SP10 — authorize_object() helper and :own-qualified capabilities.

Key guarantees tested:

- Non-owner of an object is always denied (deny-first, no role bypass).
- Object owner is allowed when the PDP grants the :own capability.
- Object with no user_id attribute is denied.
- Object whose user_id is None is denied.
- Community provider: org-member who owns the object is allowed (non-owner-only cap).
- EE: Member who owns the object is allowed; Viewer who owns is denied.
- EE: Non-owner Member is denied even if role grants comment:update.
- Permission.Comment enum has UPDATE_OWN and DELETE_OWN members.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/auth/test_authorize_object.py -v
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.auth.principal import Principal
from rhesis.backend.app.auth.rbac import (
    authorize_object,
    get_authorization_provider,
    set_authorization_provider,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_obj(user_id) -> object:
    """Return a minimal ORM-like object with a user_id attribute."""
    return SimpleNamespace(user_id=user_id)


def _create_org(db: Session) -> uuid.UUID:
    org_id = uuid.uuid4()
    db.execute(
        text("INSERT INTO organization (id, name, is_active) VALUES (:id, :name, true)"),
        {"id": str(org_id), "name": f"AOOrg-{org_id.hex[:8]}"},
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
        {
            "id": str(user_id),
            "email": f"u-{user_id.hex[:8]}@ao.example",
            "oid": str(org_id),
        },
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
    """Install EE PermissionAuthorizationProvider with RBAC forced on."""
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
def _rbac_on(db: Session, org_id: uuid.UUID, user_id: uuid.UUID, role_name: str = "Member"):
    """Assign *role_name* org-role to *user_id* and activate EE RBAC."""
    from rhesis.backend.app.scope import bypass_tenant_filter
    from rhesis.backend.ee.rbac.models import OrganizationMember, Role

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
# Unit-level: Permission enum
# ---------------------------------------------------------------------------


class TestPermissionEnumOwnCaps:
    def test_update_own_value(self):
        assert Permission.Comment.UPDATE_OWN == "comment:update:own"
        assert str(Permission.Comment.UPDATE_OWN) == "comment:update:own"

    def test_delete_own_value(self):
        assert Permission.Comment.DELETE_OWN == "comment:delete:own"
        assert str(Permission.Comment.DELETE_OWN) == "comment:delete:own"


# ---------------------------------------------------------------------------
# Unit-level: authorize_object — no DB needed
# ---------------------------------------------------------------------------


class TestAuthorizeObjectUnit:
    """Unit tests using a fake DB session and community provider."""

    def _community_principal(self, user_id: uuid.UUID, org_id: uuid.UUID) -> Principal:
        return Principal(user_id=user_id, organization_id=org_id, kind="session")

    def test_non_owner_denied_no_db_query(self, monkeypatch):
        """Non-owner is denied immediately without hitting the PDP at all."""
        owner_id = uuid.uuid4()
        caller_id = uuid.uuid4()
        org_id = uuid.uuid4()

        principal = self._community_principal(caller_id, org_id)
        obj = _make_obj(owner_id)

        called = []
        monkeypatch.setattr(
            "rhesis.backend.app.auth.rbac.authorize",
            lambda *a, **kw: called.append(True) or True,
        )

        result = authorize_object(
            principal, Permission.Comment.UPDATE_OWN, obj, project_id=None, db=None
        )
        assert result is False
        assert not called, "authorize() must not be called for non-owners"

    def test_obj_without_user_id_denied(self, monkeypatch):
        """Object with no user_id attribute is always denied."""
        principal = self._community_principal(uuid.uuid4(), uuid.uuid4())
        obj = SimpleNamespace()  # no user_id

        monkeypatch.setattr("rhesis.backend.app.auth.rbac.authorize", lambda *a, **kw: True)
        result = authorize_object(
            principal, Permission.Comment.UPDATE_OWN, obj, project_id=None, db=None
        )
        assert result is False

    def test_obj_with_none_user_id_denied(self, monkeypatch):
        """Object whose user_id is None is denied."""
        principal = self._community_principal(uuid.uuid4(), uuid.uuid4())
        obj = _make_obj(None)

        monkeypatch.setattr("rhesis.backend.app.auth.rbac.authorize", lambda *a, **kw: True)
        result = authorize_object(
            principal, Permission.Comment.UPDATE_OWN, obj, project_id=None, db=None
        )
        assert result is False


# ---------------------------------------------------------------------------
# Integration: community provider
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAuthorizeObjectCommunity:
    def test_owner_allowed_for_own_comment(self, test_db):
        """Org member who owns the comment is allowed (community tier)."""
        db = test_db
        org_id = _create_org(db)
        user_id = _create_user(db, org_id)
        _set_owner(db, org_id, user_id)
        _point_session_at_org(db, org_id)

        principal = Principal(user_id=user_id, organization_id=org_id, kind="session")
        obj = _make_obj(user_id)

        result = authorize_object(
            principal, Permission.Comment.UPDATE_OWN, obj, project_id=None, db=db
        )
        assert result is True

    def test_non_owner_denied_for_others_comment(self, test_db):
        """Org member who does NOT own the comment is denied (community tier)."""
        db = test_db
        org_id = _create_org(db)
        owner_id = _create_user(db, org_id)
        caller_id = _create_user(db, org_id)
        _set_owner(db, org_id, owner_id)
        _point_session_at_org(db, org_id)

        principal = Principal(user_id=caller_id, organization_id=org_id, kind="session")
        obj = _make_obj(owner_id)  # owned by owner_id, not caller_id

        result = authorize_object(
            principal, Permission.Comment.UPDATE_OWN, obj, project_id=None, db=db
        )
        assert result is False, "Non-owner must be denied in community tier"

    def test_org_owner_allowed_for_own_comment(self, test_db):
        """Org owner who also owns the comment is allowed."""
        db = test_db
        org_id = _create_org(db)
        user_id = _create_user(db, org_id)
        _set_owner(db, org_id, user_id)
        _point_session_at_org(db, org_id)

        principal = Principal(user_id=user_id, organization_id=org_id, kind="session")
        obj = _make_obj(user_id)

        result = authorize_object(
            principal, Permission.Comment.UPDATE_OWN, obj, project_id=None, db=db
        )
        assert result is True

    def test_org_owner_denied_for_others_comment(self, test_db):
        """Org owner who does NOT own the comment is still denied (no admin bypass)."""
        db = test_db
        org_id = _create_org(db)
        org_owner_id = _create_user(db, org_id)
        other_user_id = _create_user(db, org_id)
        _set_owner(db, org_id, org_owner_id)
        _point_session_at_org(db, org_id)

        principal = Principal(user_id=org_owner_id, organization_id=org_id, kind="session")
        obj = _make_obj(other_user_id)  # owned by other_user_id

        result = authorize_object(
            principal, Permission.Comment.UPDATE_OWN, obj, project_id=None, db=db
        )
        assert result is False, "authorize_object enforces ownership strictly — no admin bypass"


# ---------------------------------------------------------------------------
# Integration: EE provider
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestAuthorizeObjectEe:
    def test_member_allowed_for_own_comment(self, test_db):
        """EE Member role: allowed to update their own comment."""
        db = test_db
        org_id = _create_org(db)
        user_id = _create_user(db, org_id)
        _point_session_at_org(db, org_id)

        principal = Principal(user_id=user_id, organization_id=org_id, kind="session")
        obj = _make_obj(user_id)

        with _rbac_on(db, org_id, user_id, "Member"):
            result = authorize_object(
                principal, Permission.Comment.UPDATE_OWN, obj, project_id=None, db=db
            )
        assert result is True

    def test_viewer_denied_for_own_comment(self, test_db):
        """EE Viewer role: denied even for their own comment (read-only)."""
        db = test_db
        org_id = _create_org(db)
        user_id = _create_user(db, org_id)
        _point_session_at_org(db, org_id)

        principal = Principal(user_id=user_id, organization_id=org_id, kind="session")
        obj = _make_obj(user_id)

        with _rbac_on(db, org_id, user_id, "Viewer"):
            result = authorize_object(
                principal, Permission.Comment.UPDATE_OWN, obj, project_id=None, db=db
            )
        assert result is False, "Viewer role must not be allowed to update even own comments"

    def test_member_denied_for_others_comment(self, test_db):
        """EE Member role: denied for another user's comment (no bypass)."""
        db = test_db
        org_id = _create_org(db)
        member_id = _create_user(db, org_id)
        other_id = _create_user(db, org_id)
        _point_session_at_org(db, org_id)

        principal = Principal(user_id=member_id, organization_id=org_id, kind="session")
        obj = _make_obj(other_id)

        with _rbac_on(db, org_id, member_id, "Member"):
            result = authorize_object(
                principal, Permission.Comment.UPDATE_OWN, obj, project_id=None, db=db
            )
        assert result is False, "Non-owner Member must be denied regardless of role"

    def test_delete_own_member_allowed(self, test_db):
        """EE Member role: allowed to delete their own comment."""
        db = test_db
        org_id = _create_org(db)
        user_id = _create_user(db, org_id)
        _point_session_at_org(db, org_id)

        principal = Principal(user_id=user_id, organization_id=org_id, kind="session")
        obj = _make_obj(user_id)

        with _rbac_on(db, org_id, user_id, "Member"):
            result = authorize_object(
                principal, Permission.Comment.DELETE_OWN, obj, project_id=None, db=db
            )
        assert result is True
