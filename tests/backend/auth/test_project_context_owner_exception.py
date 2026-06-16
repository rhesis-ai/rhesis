"""Tests for the org Owner/Admin get_project_context exception (item 1, plan §1.4).

``get_project_context`` was strictly binary — only a ``project_membership`` row
let a user enter a project scope.  The carry-over exception lets the org ceiling
role (community: org Owner; EE: org Owner/Admin) enter ANY project context in its
org without a membership row, while a plain member is still denied (fail-closed).

The dependency opens its own ``get_db_with_tenant_variables`` session, so these
tests monkeypatch it to yield ``test_db`` (the GUC is repointed to the freshly
created org so RLS makes the rows visible).

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/auth/test_project_context_owner_exception.py -v
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app import dependencies
from rhesis.backend.app.dependencies import get_project_context


def _point_session_at_org(db: Session, org_id: uuid.UUID) -> None:
    """Repoint the RLS GUC so rows in *org_id* are visible on this session."""
    db.execute(text('SET "app.current_organization" = :o'), {"o": str(org_id)})


def _create_org(db: Session) -> uuid.UUID:
    org_id = uuid.uuid4()
    db.execute(
        text("INSERT INTO organization (id, name, is_active) VALUES (:id, :name, true)"),
        {"id": str(org_id), "name": f"CtxOrg-{org_id.hex[:8]}"},
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


def _create_project(db: Session, org_id: uuid.UUID) -> uuid.UUID:
    pid = uuid.uuid4()
    db.execute(
        text("INSERT INTO project (id, name, organization_id) VALUES (:id, :name, :oid)"),
        {"id": str(pid), "name": f"Proj-{pid.hex[:8]}", "oid": str(org_id)},
    )
    db.flush()
    return pid


@pytest.fixture
def patch_ctx_session(test_db, monkeypatch):
    """Make get_project_context use ``test_db`` instead of a fresh connection."""

    @contextmanager
    def _fake(*_args, **_kwargs):
        yield test_db

    monkeypatch.setattr(dependencies, "get_db_with_tenant_variables", _fake)
    return test_db


@contextmanager
def _ee_provider_active():
    """Install the EE provider with RBAC forced on, restoring the prior provider.

    Other suites (e.g. test_rbac.py) swap the global authorization provider, so
    the EE tests cannot assume the EE provider is installed — pin it explicitly.
    """
    from unittest.mock import patch

    from rhesis.backend.app.auth.rbac import (
        get_authorization_provider,
        set_authorization_provider,
    )
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


def _call(user_id: uuid.UUID, org_id: uuid.UUID, project_id: uuid.UUID):
    request = SimpleNamespace(headers={}, state=SimpleNamespace())
    current_user = SimpleNamespace(id=user_id, organization_id=org_id)
    return get_project_context(request, current_user, x_project_id=str(project_id))


@pytest.mark.integration
class TestOwnerException:
    def test_org_owner_enters_non_member_project(self, patch_ctx_session):
        db = patch_ctx_session
        org_id = _create_org(db)
        owner_id = _create_user(db, org_id)
        _set_owner(db, org_id, owner_id)
        project_id = _create_project(db, org_id)
        _point_session_at_org(db, org_id)

        # Owner is NOT enrolled in the project, yet may enter its context.
        assert _call(owner_id, org_id, project_id) == str(project_id)

    def test_plain_member_still_denied(self, patch_ctx_session):
        db = patch_ctx_session
        org_id = _create_org(db)
        owner_id = _create_user(db, org_id)
        _set_owner(db, org_id, owner_id)
        other_id = _create_user(db, org_id)  # not the owner, no membership
        project_id = _create_project(db, org_id)
        _point_session_at_org(db, org_id)

        with pytest.raises(HTTPException) as exc:
            _call(other_id, org_id, project_id)
        assert exc.value.status_code == 403

    def test_nonexistent_project_denied_even_for_owner(self, patch_ctx_session):
        db = patch_ctx_session
        org_id = _create_org(db)
        owner_id = _create_user(db, org_id)
        _set_owner(db, org_id, owner_id)
        _point_session_at_org(db, org_id)

        with pytest.raises(HTTPException) as exc:
            _call(owner_id, org_id, uuid.uuid4())  # no such project
        assert exc.value.status_code == 403


@pytest.mark.ee
@pytest.mark.integration
class TestEeAdminException:
    def test_org_admin_enters_non_member_project(self, patch_ctx_session):
        from rhesis.backend.ee.rbac.models import OrganizationMember, Role

        db = patch_ctx_session
        org_id = _create_org(db)
        owner_id = _create_user(db, org_id)
        _set_owner(db, org_id, owner_id)  # someone else owns the org
        admin_id = _create_user(db, org_id)
        project_id = _create_project(db, org_id)

        admin_role = db.query(Role).filter_by(name="Admin", is_built_in=True).first()
        db.add(OrganizationMember(organization_id=org_id, user_id=admin_id, role_id=admin_role.id))
        db.flush()
        _point_session_at_org(db, org_id)

        with _ee_provider_active():
            assert _call(admin_id, org_id, project_id) == str(project_id)

    def test_ee_viewer_denied(self, patch_ctx_session):
        from rhesis.backend.ee.rbac.models import OrganizationMember, Role

        db = patch_ctx_session
        org_id = _create_org(db)
        owner_id = _create_user(db, org_id)
        _set_owner(db, org_id, owner_id)
        viewer_id = _create_user(db, org_id)
        project_id = _create_project(db, org_id)

        viewer_role = db.query(Role).filter_by(name="Viewer", is_built_in=True).first()
        db.add(
            OrganizationMember(organization_id=org_id, user_id=viewer_id, role_id=viewer_role.id)
        )
        db.flush()
        _point_session_at_org(db, org_id)

        with _ee_provider_active():
            with pytest.raises(HTTPException) as exc:
                _call(viewer_id, org_id, project_id)
            assert exc.value.status_code == 403
