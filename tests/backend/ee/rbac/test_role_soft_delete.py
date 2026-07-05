"""Role deletion behavior: soft-delete + unassign holders.

``delete_role`` no longer hard-deletes a custom role or rejects when the role is
in use. It now:

- stamps ``deleted_at`` (soft delete — the row is retained for audit and hidden
  by the global soft-delete filter),
- reassigns org-tier holders to the built-in **None** role (``organization_member.role_id``
  is NOT NULL, so holders must keep *some* role),
- clears project-tier holders' ``role_id`` (they revert to their inherited org role),
- frees the role name for reuse (the ``ix_role_name_org`` unique index is partial:
  ``WHERE deleted_at IS NULL``).

Reuses the DB helpers from ``test_sp8_access_control`` rather than redefining them.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_role_soft_delete.py -v
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.database import without_soft_delete_filter
from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.ee.rbac.models import OrganizationMember, Role
from rhesis.backend.ee.rbac.router import create_role, delete_role
from rhesis.backend.ee.rbac.schemas import RoleCreate
from tests.backend.ee.rbac.test_sp8_access_control import (
    _add_project_member,
    _assign_org_role,
    _authorized,
    _builtin_role,
    _create_org,
    _create_project,
    _create_user,
    _custom_role,
    _grant_permission,
    _rbac_enabled,
    _user,
)


@pytest.mark.ee
@pytest.mark.integration
class TestRoleSoftDelete:
    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.actor_id = _create_user(test_db, self.org_id)
        # Owner actor — allowed to delete any custom role below them.
        _assign_org_role(test_db, self.org_id, self.actor_id, "Owner")
        self.actor = _user(self.actor_id, self.org_id)

    def _delete(self, role_id) -> None:
        delete_role(role_id=role_id, db=self.db, current_user=self.actor, _org=None)

    # --- soft delete ------------------------------------------------------

    def test_delete_stamps_deleted_at_and_hides_role(self):
        role = _custom_role(self.db, self.org_id, name="Doomed", scope="organization")

        self._delete(role.id)

        # Hidden from normal queries by the global soft-delete filter.
        assert self.db.query(Role).filter_by(id=role.id).first() is None

        # But the row is retained (soft, not hard, delete) with deleted_at set.
        with without_soft_delete_filter():
            persisted = self.db.query(Role).filter_by(id=role.id).first()
        assert persisted is not None, "role row must be retained for audit"
        assert persisted.deleted_at is not None

    def test_cannot_delete_builtin_role(self):
        from fastapi import HTTPException

        viewer = _builtin_role(self.db, "Viewer")
        with pytest.raises(HTTPException) as exc:
            self._delete(viewer.id)
        assert exc.value.status_code == 400

    # --- org-tier holders -------------------------------------------------

    def test_org_holder_reassigned_to_none_and_loses_access(self):
        role = _custom_role(self.db, self.org_id, name="OrgCustom", scope="organization")
        _grant_permission(self.db, role.id, "test_set:read")
        holder = _create_user(self.db, self.org_id)
        self.db.add(
            OrganizationMember(organization_id=self.org_id, user_id=holder, role_id=role.id)
        )
        self.db.flush()

        # Sanity: the custom role grants the permission before deletion.
        assert _authorized(self.db, holder, self.org_id, "test_set:read") is True

        self._delete(role.id)

        none_role = _builtin_role(self.db, "None")
        member = (
            self.db.query(OrganizationMember)
            .filter_by(organization_id=self.org_id, user_id=holder)
            .first()
        )
        assert member is not None
        assert member.role_id == none_role.id
        # Access granted only by the deleted role is now gone.
        assert _authorized(self.db, holder, self.org_id, "test_set:read") is False

    # --- project-tier holders --------------------------------------------

    def test_project_holder_role_id_nulled_reverts_to_inherited(self):
        project_id = _create_project(self.db, self.org_id)
        role = _custom_role(self.db, self.org_id, name="ProjCustom", scope="project")
        holder = _create_user(self.db, self.org_id)
        _add_project_member(self.db, self.org_id, project_id, holder, role.id)

        self._delete(role.id)

        membership = (
            self.db.query(ProjectMembership)
            .filter_by(project_id=project_id, user_id=holder)
            .first()
        )
        assert membership is not None, "member stays in the project"
        assert membership.role_id is None, "role_id cleared → inherits org role"

    # --- name reuse -------------------------------------------------------

    def test_name_reusable_after_soft_delete(self):
        role = _custom_role(self.db, self.org_id, name="Recyclable", scope="organization")

        self._delete(role.id)

        # Re-creating a role with the same name in the same org must succeed —
        # the partial unique index ignores the soft-deleted row.
        with _rbac_enabled():
            recreated = create_role(
                body=RoleCreate(
                    name="Recyclable",
                    scope="organization",
                    permission_names=[],
                ),
                db=self.db,
                current_user=self.actor,
                _org=None,
            )
        assert recreated.name == "Recyclable"
        assert recreated.id != role.id
