"""Shared RBAC test helpers.

Extracted from ``test_sp8_access_control.py`` so other RBAC test modules
(``test_project_members_authz.py``, ``test_role_soft_delete.py``, the
role×capability matrix, escalation-guard tests, ...) don't need to import
private helpers from a sibling test module.

The permission catalog and the five built-in roles are seeded once by the
Alembic migrations the ``test_db`` fixture runs, so no per-test catalog sync
is needed. Built-in role permissions are computed from code by the provider
(``permissions_for_built_in_role``); custom roles use ``role_permission``.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.principal import Principal
from rhesis.backend.app.auth.rbac import get_authorization_provider, set_authorization_provider
from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.app.scope import bypass_tenant_filter
from rhesis.backend.ee.rbac.models import OrganizationMember, Permission, Role, RolePermission
from rhesis.backend.ee.rbac.provider import PermissionAuthorizationProvider


@contextmanager
def _rbac_enabled():
    """Force the EE provider to treat RBAC as licensed for the duration.

    Patches at the *class* level so it covers both the ``self.provider``
    instances used by the direct-authorization tests and the fresh providers
    the router constructs internally (e.g. ``resolve_effective_role``).
    """
    with patch.object(PermissionAuthorizationProvider, "_rbac_available", return_value=True):
        yield


def _builtin_role(db: Session, name: str) -> Role:
    with bypass_tenant_filter():
        role = db.query(Role).filter_by(name=name, is_built_in=True).first()
    assert role is not None, f"Built-in role '{name}' not seeded by migrations"
    return role


def _create_org(db: Session) -> uuid.UUID:
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


def _create_project(db: Session, org_id: uuid.UUID) -> uuid.UUID:
    pid = uuid.uuid4()
    db.execute(
        text("INSERT INTO project (id, name, organization_id) VALUES (:id, :name, :oid)"),
        {"id": str(pid), "name": f"Proj-{pid.hex[:8]}", "oid": str(org_id)},
    )
    db.flush()
    return pid


def _custom_role(db: Session, org_id: uuid.UUID, *, name: str, scope: str, level: int = 50) -> Role:
    """Create an org-owned custom role row directly (bypassing the escalation guard)."""
    role = Role(
        name=name,
        display_name=name,
        scope=scope,
        level=level,
        is_built_in=False,
        organization_id=org_id,
    )
    db.add(role)
    db.flush()
    return role


def _grant_permission(db: Session, role_id: uuid.UUID, permission_name: str) -> None:
    perm = db.query(Permission).filter_by(name=permission_name).first()
    assert perm is not None, f"Permission '{permission_name}' not in catalog"
    db.add(RolePermission(role_id=role_id, permission_id=perm.id))
    db.flush()


def _assign_org_role(db: Session, org_id: uuid.UUID, user_id: uuid.UUID, role_name: str) -> None:
    role = _builtin_role(db, role_name)
    existing = (
        db.query(OrganizationMember).filter_by(organization_id=org_id, user_id=user_id).first()
    )
    if existing:
        existing.role_id = role.id
    else:
        db.add(OrganizationMember(organization_id=org_id, user_id=user_id, role_id=role.id))
    db.flush()


def _add_project_member(
    db: Session,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    role_id: uuid.UUID | None = None,
) -> None:
    existing = db.query(ProjectMembership).filter_by(project_id=project_id, user_id=user_id).first()
    if existing:
        existing.role_id = role_id
    else:
        db.add(
            ProjectMembership(
                project_id=project_id,
                user_id=user_id,
                organization_id=org_id,
                role_id=role_id,
            )
        )
    db.flush()


def _assign_project_role(
    db: Session,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    role_name: str,
) -> None:
    _add_project_member(db, org_id, project_id, user_id, _builtin_role(db, role_name).id)


def _principal(user_id: uuid.UUID, org_id: uuid.UUID) -> Principal:
    return Principal(user_id=user_id, organization_id=org_id, kind="session")


def _user(user_id: uuid.UUID, org_id: uuid.UUID) -> MagicMock:
    """Lightweight ``current_user`` stand-in for router calls."""
    u = MagicMock()
    u.id = user_id
    u.organization_id = org_id
    return u


def _authorized(
    db: Session,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    permission: str,
    project_id: uuid.UUID | None = None,
) -> bool:
    """Resolve an authorization decision for *user_id* with RBAC forced on."""
    with _rbac_enabled():
        return PermissionAuthorizationProvider().is_authorized(
            _principal(user_id, org_id), permission, project_id=project_id, db=db
        )


@contextmanager
def _ee_provider_active():
    """Install the EE ``PermissionAuthorizationProvider`` as the active PDP provider.

    Unlike :func:`_rbac_enabled`/:func:`_authorized`, which call the EE provider
    directly, this installs it into the global registry so callers can exercise
    the real single-decision-point ``authorize()`` function (``app/auth/rbac.py``)
    exactly as production code does.
    """
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
