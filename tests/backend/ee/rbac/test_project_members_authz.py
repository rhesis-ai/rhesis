"""Authorization scope for GET /rbac/projects/{project_id}/members.

``member:read`` is an *org-scoped* capability, so the capability gate alone does
not prove the caller may see a *specific* project's roster. ``list_project_members``
therefore calls ``assert_project_access`` to require that the caller is either
enrolled in the project or holds an org-level ``member:manage`` role
(Admin/Owner). Without this, a plain org Viewer (who has ``member:read``) could
enumerate the members of any project in the org.

These tests call the endpoint function directly (the HTTP capability gate is not
in the path), which is exactly what exercises the explicit ``assert_project_access``
check added to close the gap.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_project_members_authz.py -v
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.ee.rbac.router import list_project_members
from tests.backend.ee.rbac._rbac_helpers import (
    _add_project_member,
    _assign_org_role,
    _builtin_role,
    _create_org,
    _create_project,
    _create_user,
    _rbac_enabled,
    _user,
)


def _request() -> SimpleNamespace:
    """Minimal Request stand-in: assert_project_access / principal resolution
    only read optional attributes off ``request.state`` (default None)."""
    return SimpleNamespace(state=SimpleNamespace())


@pytest.mark.ee
@pytest.mark.integration
class TestProjectMembersListingAuthz:
    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.project_id = _create_project(test_db, self.org_id)
        # A member already enrolled in the project (the roster to protect).
        self.enrolled_id = _create_user(test_db, self.org_id)
        _add_project_member(test_db, self.org_id, self.project_id, self.enrolled_id)

    def _list(self, caller_id):
        return list_project_members(
            project_id=self.project_id,
            request=_request(),
            db=self.db,
            current_user=_user(caller_id, self.org_id),
            _org=None,
        )

    def test_unenrolled_caller_is_denied(self):
        """An org member not enrolled in the project cannot list its members."""
        outsider = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, outsider, "Viewer")
        with _rbac_enabled():
            with pytest.raises(HTTPException) as exc:
                self._list(outsider)
        assert exc.value.status_code == 403

    def test_enrolled_caller_sees_roster(self):
        """A caller enrolled in the project may list its members."""
        caller = _create_user(self.db, self.org_id)
        _add_project_member(self.db, self.org_id, self.project_id, caller)
        result = self._list(caller)
        user_ids = {m.user_id for m in result}
        assert self.enrolled_id in user_ids
        assert caller in user_ids

    def test_org_owner_not_enrolled_is_allowed(self):
        """An org Owner (member:manage) may list even without project enrollment."""
        owner = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, owner, "Owner")
        with _rbac_enabled():
            result = self._list(owner)
        assert self.enrolled_id in {m.user_id for m in result}


@pytest.mark.ee
@pytest.mark.integration
class TestProjectMemberPermittedActions:
    """`permitted_actions` on ProjectMemberRoleRead must reflect the same
    escalation gates as list_org_members (see `_member_permitted_actions`),
    minus `member:delete` — project membership removal goes through the
    community `remove_project_member` endpoint, which this guard does not
    reach, so the affordance is never asserted for project rows.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.project_id = _create_project(test_db, self.org_id)

    def _list(self, actor_id):
        with _rbac_enabled():
            return list_project_members(
                project_id=self.project_id,
                request=_request(),
                db=self.db,
                current_user=_user(actor_id, self.org_id),
                _org=None,
            )

    def _row(self, results, user_id):
        return next(r for r in results if r.user_id == user_id)

    def test_own_row_has_no_permitted_actions(self):
        admin_id = _create_user(self.db, self.org_id)
        _add_project_member(
            self.db, self.org_id, self.project_id, admin_id, _builtin_role(self.db, "Admin").id
        )

        results = self._list(admin_id)
        assert self._row(results, admin_id).permitted_actions == []

    def test_admin_sees_manage_but_not_delete_on_ordinary_member(self):
        admin_id = _create_user(self.db, self.org_id)
        member_id = _create_user(self.db, self.org_id)
        _add_project_member(
            self.db, self.org_id, self.project_id, admin_id, _builtin_role(self.db, "Admin").id
        )
        _add_project_member(
            self.db, self.org_id, self.project_id, member_id, _builtin_role(self.db, "Member").id
        )

        results = self._list(admin_id)
        assert self._row(results, member_id).permitted_actions == ["member:manage"]

    def test_admin_sees_no_permitted_actions_on_project_owner_row(self):
        """Regression test surfaced on the read side: a project Admin
        viewing a project Owner's row must not see member:manage."""
        admin_id = _create_user(self.db, self.org_id)
        owner_id = _create_user(self.db, self.org_id)
        _add_project_member(
            self.db, self.org_id, self.project_id, admin_id, _builtin_role(self.db, "Admin").id
        )
        _add_project_member(
            self.db, self.org_id, self.project_id, owner_id, _builtin_role(self.db, "Owner").id
        )

        results = self._list(admin_id)
        assert self._row(results, owner_id).permitted_actions == []


@pytest.mark.ee
@pytest.mark.integration
class TestProjectMemberInheritedRoleDisplay:
    """Members with NULL project_membership.role_id inherit their org role for
    authorization; list_project_members must surface that effective role in the
  ``role`` field so the Members grid does not show "—"."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session):
        self.db = test_db
        self.org_id = _create_org(test_db)
        self.project_id = _create_project(test_db, self.org_id)

    def _list(self, actor_id):
        with _rbac_enabled():
            return list_project_members(
                project_id=self.project_id,
                request=_request(),
                db=self.db,
                current_user=_user(actor_id, self.org_id),
                _org=None,
            )

    def test_owner_without_project_role_shows_inherited_owner(self):
        owner_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")
        _add_project_member(self.db, self.org_id, self.project_id, owner_id)

        row = next(r for r in self._list(owner_id) if r.user_id == owner_id)
        assert row.role_id is None
        assert row.role is not None
        assert row.role.name == "Owner"

    def test_admin_sees_no_manage_on_inherited_owner_row(self):
        admin_id = _create_user(self.db, self.org_id)
        owner_id = _create_user(self.db, self.org_id)
        _assign_org_role(self.db, self.org_id, admin_id, "Admin")
        _assign_org_role(self.db, self.org_id, owner_id, "Owner")
        _add_project_member(self.db, self.org_id, self.project_id, admin_id)
        _add_project_member(self.db, self.org_id, self.project_id, owner_id)

        results = self._list(admin_id)
        owner_row = next(r for r in results if r.user_id == owner_id)
        assert owner_row.role is not None
        assert owner_row.role.name == "Owner"
        assert owner_row.permitted_actions == []
