"""Tests for default org-role assignment on user↔org association (item 0).

Covers the RBAC-activation prerequisite: ``crud.create_user`` / onboarding /
re-invite call the core ``on_user_org_assigned`` hook, and the EE handler
(:func:`~rhesis.backend.ee.rbac.default_role.assign_default_org_role`) seeds an
``organization_member`` row so users are not locked out once RBAC is enabled.

Deny-first matrix:
- new invitee (user != owner) → **Member**: allowed on Member endpoints,
  denied on Admin-only ones;
- org creator (user == owner) → **Owner**: allowed everywhere;
- RBAC off / community build → handler no-ops (no row written);
- idempotent: an existing Owner is never downgraded on re-invite.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_default_org_role.py -v
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.principal import Principal
from rhesis.backend.app.scope import bypass_tenant_filter
from rhesis.backend.ee.rbac.default_role import assign_default_org_role
from rhesis.backend.ee.rbac.models import OrganizationMember, Role
from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def _rbac_on():
    """Force RBAC available for both the handler (FeatureRegistry.is_available)
    and the provider (``_rbac_available``)."""
    with (
        patch(
            "rhesis.backend.app.features.FeatureRegistry.is_available",
            return_value=True,
        ),
        patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True),
    ):
        yield


@contextmanager
def _rbac_off():
    """Force RBAC unavailable, overriding ``DefaultLicenseProvider``'s allow-all
    default (RBAC ships dark only when explicitly gated off, e.g. no license)."""
    with (
        patch(
            "rhesis.backend.app.features.FeatureRegistry.is_available",
            return_value=False,
        ),
        patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=False),
    ):
        yield


def _create_org(db: Session, owner_id: uuid.UUID | None = None) -> uuid.UUID:
    """Create an org. ``owner_id`` is left NULL unless given (the FK requires the
    user to exist first, so creator tests set it via :func:`_set_owner`)."""
    org_id = uuid.uuid4()
    db.execute(
        text("INSERT INTO organization (id, name, is_active) VALUES (:id, :name, true)"),
        {"id": str(org_id), "name": f"TestOrg-{org_id.hex[:8]}"},
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
        {"id": str(user_id), "email": f"u-{user_id.hex[:8]}@test.example", "oid": str(org_id)},
    )
    db.flush()
    return user_id


def _set_owner(db: Session, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
    db.execute(
        text("UPDATE organization SET owner_id = :owner WHERE id = :id"),
        {"owner": str(user_id), "id": str(org_id)},
    )
    db.flush()


def _member_row(db: Session, org_id: uuid.UUID, user_id: uuid.UUID) -> OrganizationMember | None:
    with bypass_tenant_filter():
        return (
            db.query(OrganizationMember).filter_by(organization_id=org_id, user_id=user_id).first()
        )


def _role_name(db: Session, role_id: uuid.UUID) -> str:
    with bypass_tenant_filter():
        return db.query(Role).filter_by(id=role_id).first().name


def _authorized(db: Session, user_id, org_id, permission, project_id=None) -> bool:
    return PermissionAuthorizationProvider().is_authorized(
        Principal(user_id=user_id, organization_id=org_id, kind="session"),
        permission,
        project_id=project_id,
        db=db,
    )


# ---------------------------------------------------------------------------
# Invitee → Member
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestInviteeGetsMember:
    def test_member_row_written(self, test_db: Session):
        org_id = _create_org(test_db)
        user_id = _create_user(test_db, org_id)

        with _rbac_on():
            assign_default_org_role(test_db, user_id, org_id)

        member = _member_row(test_db, org_id, user_id)
        assert member is not None
        assert _role_name(test_db, member.role_id) == "Member"

    def test_member_allowed_on_member_endpoint(self, test_db: Session):
        org_id = _create_org(test_db)
        user_id = _create_user(test_db, org_id)

        with _rbac_on():
            assign_default_org_role(test_db, user_id, org_id)
            # Org-level check (no project context): Member holds this read.
            # Project-scoped enrollment gating is covered by
            # test_sp8_provider.py::TestExplicitEnrollmentRequired.
            assert _authorized(test_db, user_id, org_id, "test_set:read", project_id=None)

    def test_member_denied_on_admin_only_endpoint(self, test_db: Session):
        org_id = _create_org(test_db)
        user_id = _create_user(test_db, org_id)

        with _rbac_on():
            assign_default_org_role(test_db, user_id, org_id)
            # member:manage is org-scoped admin — not in the Member set.
            assert not _authorized(test_db, user_id, org_id, "member:manage", project_id=None)


# ---------------------------------------------------------------------------
# Org creator → Owner
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestCreatorGetsOwner:
    def test_owner_row_written_for_creator(self, test_db: Session):
        org_id = _create_org(test_db)
        user_id = _create_user(test_db, org_id)
        _set_owner(test_db, org_id, user_id)

        with _rbac_on():
            assign_default_org_role(test_db, user_id, org_id)

        member = _member_row(test_db, org_id, user_id)
        assert member is not None
        assert _role_name(test_db, member.role_id) == "Owner"

    def test_owner_allowed_on_admin_only_endpoint(self, test_db: Session):
        org_id = _create_org(test_db)
        user_id = _create_user(test_db, org_id)
        _set_owner(test_db, org_id, user_id)

        with _rbac_on():
            assign_default_org_role(test_db, user_id, org_id)
            assert _authorized(test_db, user_id, org_id, "member:manage", project_id=None)


# ---------------------------------------------------------------------------
# PUT /users/{user_id} seeds the Owner role immediately (regression: the org
# creator must not be locked out of later onboarding calls — invite teammates,
# load-initial-data — that are capability-gated on this same role).
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestUpdateUserSeedsOwnerRoleOnFirstOrgAssignment:
    def test_owner_row_written_when_organization_id_first_set(self, test_db: Session):
        from rhesis.backend.app import schemas
        from rhesis.backend.app.models.user import User
        from rhesis.backend.app.routers.user import update_user

        org_id = _create_org(test_db)
        user_id = _create_user(test_db, org_id)
        _set_owner(test_db, org_id, user_id)

        # Simulate the user's state *before* they are attached to the org: no
        # organization_id yet, matching the onboarding creator flow.
        current_user = test_db.query(User).filter_by(id=user_id).first()
        current_user.organization_id = None
        test_db.flush()

        assert _member_row(test_db, org_id, user_id) is None

        with _rbac_on():
            update_user(
                user_id=user_id,
                user=schemas.UserUpdate(organization_id=org_id),
                request=None,
                db=test_db,
                current_user=current_user,
            )

        member = _member_row(test_db, org_id, user_id)
        assert member is not None
        assert _role_name(test_db, member.role_id) == "Owner"

    def test_no_op_when_user_already_has_an_organization(self, test_db: Session):
        """Ordinary profile updates (already in an org) must not re-trigger seeding."""
        from rhesis.backend.app import schemas
        from rhesis.backend.app.models.user import User
        from rhesis.backend.app.routers.user import update_user

        org_id = _create_org(test_db)
        user_id = _create_user(test_db, org_id)
        current_user = test_db.query(User).filter_by(id=user_id).first()

        with _rbac_on():
            update_user(
                user_id=user_id,
                user=schemas.UserUpdate(name="New Name"),
                request=None,
                db=test_db,
                current_user=current_user,
            )

        assert _member_row(test_db, org_id, user_id) is None


# ---------------------------------------------------------------------------
# RBAC off / idempotency
# ---------------------------------------------------------------------------


@pytest.mark.ee
@pytest.mark.integration
class TestNoOpAndIdempotency:
    def test_rbac_off_writes_no_row(self, test_db: Session):
        org_id = _create_org(test_db)
        user_id = _create_user(test_db, org_id)

        # DefaultLicenseProvider allows RBAC by default (dev/unlicensed EE);
        # force it off here to cover the licensed-off / community-build case.
        with _rbac_off():
            assign_default_org_role(test_db, user_id, org_id)

        assert _member_row(test_db, org_id, user_id) is None

    def test_existing_owner_not_downgraded(self, test_db: Session):
        """Re-invite of an existing Owner must keep Owner, not reset to Member."""
        org_id = _create_org(test_db)  # owner_id left NULL → user is not the creator
        user_id = _create_user(test_db, org_id)

        with bypass_tenant_filter():
            owner_role = test_db.query(Role).filter_by(name="Owner", is_built_in=True).first()
        test_db.add(
            OrganizationMember(organization_id=org_id, user_id=user_id, role_id=owner_role.id)
        )
        test_db.flush()

        with _rbac_on():
            assign_default_org_role(test_db, user_id, org_id)

        member = _member_row(test_db, org_id, user_id)
        assert _role_name(test_db, member.role_id) == "Owner"


# ---------------------------------------------------------------------------
# Core hook dispatch — community build (no handler) no-ops
# ---------------------------------------------------------------------------


@pytest.mark.ee
class TestCoreHookDispatch:
    def test_no_handler_is_noop(self):
        from rhesis.backend.app.auth import org_membership_hook as hook

        saved = list(hook._handlers)
        try:
            hook.reset_org_membership_handlers()
            # No handler registered → must not raise, must not need a usable db.
            hook.on_user_org_assigned(db=None, user_id=uuid.uuid4(), organization_id=uuid.uuid4())
        finally:
            hook._handlers[:] = saved

    def test_falsy_org_is_noop(self):
        from rhesis.backend.app.auth import org_membership_hook as hook

        called = []
        hook.register_org_membership_handler(lambda db, u, o: called.append((u, o)))
        try:
            hook.on_user_org_assigned(db=None, user_id=uuid.uuid4(), organization_id=None)
            assert called == []
        finally:
            hook.reset_org_membership_handlers()
