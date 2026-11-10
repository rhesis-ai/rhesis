"""Routes with a ``{project_id}`` path parameter authorize against the path project.

The backstop used to evaluate the capability on the request's active project (from
``X-Project-Id``) only, so a member of P1 with P1 active could manage the members of
P2. These tests drive the real routes through ``TestClient`` and check the capability
is evaluated on the project named in the URL, whatever the active project is.

The ``client`` fixture overrides ``get_tenant_db_session``, so the header never
reaches the session scope there. ``_active`` binds ``db.info['_scope']`` the way
``get_tenant_db_session`` does for a real ``X-Project-Id`` header.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/security/test_project_scope_confusion.py -v
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime

import pytest

from rhesis.backend.app import models
from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.app.scope import RequestScope, bypass_tenant_filter
from tests.backend.fixtures.rls import scope_to_org
from tests.backend.fixtures.test_setup import (
    create_test_api_token,
    create_test_organization_and_user,
    create_test_user,
)


def _builtin_role_id(db, name: str):
    """Built-in role id under EE, else None (community: membership alone grants access)."""
    try:
        from rhesis.backend.ee.rbac.models import Role
    except ImportError:
        return None
    with bypass_tenant_filter():
        role = db.query(Role).filter_by(name=name, is_built_in=True, organization_id=None).first()
    return role.id if role is not None else None


def _create_project(db, org_id, owner_id) -> uuid.UUID:
    scope_to_org(db, org_id)
    project = models.Project(
        name=f"Scope-{uuid.uuid4().hex[:8]}",
        organization_id=org_id,
        owner_id=owner_id,
        user_id=owner_id,
    )
    db.add(project)
    db.flush()
    return project.id


def _enroll(db, org_id, project_id, user_id, role: str | None = "Admin") -> None:
    scope_to_org(db, org_id)
    db.add(
        ProjectMembership(
            project_id=project_id,
            user_id=user_id,
            organization_id=org_id,
            role_id=_builtin_role_id(db, role) if role else None,
        )
    )
    db.flush()


def _is_member(db, project_id, user_id) -> bool:
    with bypass_tenant_filter():
        return (
            db.query(ProjectMembership).filter_by(project_id=project_id, user_id=user_id).first()
            is not None
        )


@pytest.mark.integration
@pytest.mark.security
class TestProjectPathAuthorization:
    @pytest.fixture(autouse=True)
    def _setup(self, test_db, client):
        self.db = test_db
        self.client = client
        suffix = f"{datetime.now():%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}"
        org, owner, _owner_token = create_test_organization_and_user(
            test_db, f"Scope Org {suffix}", f"scope_owner_{suffix}@rhesis-test.com", "Owner"
        )
        self.org_id = org.id

        # Plain org members (not the org owner): access comes from project enrollment.
        self.p1_admin = create_test_user(test_db, org.id, f"scope_p1_{suffix}@rhesis-test.com")
        self.p2_admin = create_test_user(test_db, org.id, f"scope_p2_{suffix}@rhesis-test.com")
        self.bystander = create_test_user(test_db, org.id, f"scope_by_{suffix}@rhesis-test.com")
        self.tokens = {
            self.p1_admin.id: create_test_api_token(test_db, self.p1_admin),
            self.p2_admin.id: create_test_api_token(test_db, self.p2_admin),
        }

        self.p1 = _create_project(test_db, org.id, owner.id)
        self.p2 = _create_project(test_db, org.id, owner.id)
        _enroll(test_db, org.id, self.p1, self.p1_admin.id)
        _enroll(test_db, org.id, self.p2, self.p2_admin.id)
        _enroll(test_db, org.id, self.p2, self.bystander.id, role=None)

    @contextmanager
    def _active(self, user, project_id):
        previous = self.db.info.get("_scope")
        self.db.info["_scope"] = RequestScope(
            organization_id=str(self.org_id),
            user_id=str(user.id),
            project_id=str(project_id) if project_id else None,
        )
        try:
            yield
        finally:
            self.db.info["_scope"] = previous

    def _call(self, method, url, user, active=None, **kwargs):
        headers = {"Authorization": f"Bearer {self.tokens[user.id].token}"}
        if active is not None:
            headers["X-Project-Id"] = str(active)
        with self._active(user, active):
            return self.client.request(method, url, headers=headers, **kwargs)

    # --- the escalation path: active project is one the caller can manage ---

    def test_member_of_p1_cannot_add_self_to_p2_with_p1_active(self):
        resp = self._call(
            "POST",
            f"/projects/{self.p2}/members",
            self.p1_admin,
            active=self.p1,
            json={"user_id": str(self.p1_admin.id)},
        )
        assert resp.status_code == 403, resp.text
        assert not _is_member(self.db, self.p2, self.p1_admin.id)

    def test_member_of_p1_cannot_add_self_to_p2_without_active_project(self):
        resp = self._call(
            "POST",
            f"/projects/{self.p2}/members",
            self.p1_admin,
            json={"user_id": str(self.p1_admin.id)},
        )
        assert resp.status_code == 403, resp.text
        assert not _is_member(self.db, self.p2, self.p1_admin.id)

    def test_member_of_p1_cannot_list_p2_members(self):
        resp = self._call("GET", f"/projects/{self.p2}/members", self.p1_admin, active=self.p1)
        assert resp.status_code == 403, resp.text

    def test_member_of_p1_cannot_remove_p2_member(self):
        resp = self._call(
            "DELETE",
            f"/projects/{self.p2}/members/{self.bystander.id}",
            self.p1_admin,
            active=self.p1,
        )
        assert resp.status_code == 403, resp.text
        assert _is_member(self.db, self.p2, self.bystander.id)

    def test_p2_member_cannot_delete_p2_with_p1_admin_role(self):
        """Enrolled in P2 without a project role, so P2 does not grant project:delete;
        the Admin role on the active project P1 must not count."""
        _enroll(self.db, self.org_id, self.p2, self.p1_admin.id, role=None)
        resp = self._call("DELETE", f"/projects/{self.p2}", self.p1_admin, active=self.p1)
        assert resp.status_code == 403, resp.text

    def test_member_of_p1_cannot_update_p2_parameters(self):
        resp = self._call(
            "PUT",
            f"/projects/{self.p2}/parameters/schema",
            self.p1_admin,
            active=self.p1,
            json={"fields": []},
        )
        assert resp.status_code == 403, resp.text

    def test_invalid_path_project_is_rejected(self):
        resp = self._call("GET", "/projects/not-a-uuid/members", self.p1_admin, active=self.p1)
        assert resp.status_code == 422, resp.text

    # --- legitimate use keeps working, including with a different active project ---

    def test_member_of_p2_can_manage_p2_members(self):
        resp = self._call("GET", f"/projects/{self.p2}/members", self.p2_admin, active=self.p2)
        assert resp.status_code == 200, resp.text

        resp = self._call(
            "POST",
            f"/projects/{self.p2}/members",
            self.p2_admin,
            active=self.p2,
            json={"user_id": str(self.p1_admin.id)},
        )
        assert resp.status_code == 201, resp.text
        assert _is_member(self.db, self.p2, self.p1_admin.id)

        resp = self._call(
            "DELETE",
            f"/projects/{self.p2}/members/{self.p1_admin.id}",
            self.p2_admin,
            active=self.p2,
        )
        assert resp.status_code == 204, resp.text
        assert not _is_member(self.db, self.p2, self.p1_admin.id)

    def test_path_project_wins_over_a_different_active_project(self):
        """The team page sends the active project while it manages other projects'
        members; the path project decides, so that keeps working."""
        _enroll(self.db, self.org_id, self.p1, self.p2_admin.id, role=None)
        resp = self._call(
            "POST",
            f"/projects/{self.p2}/members",
            self.p2_admin,
            active=self.p1,
            json={"user_id": str(self.p1_admin.id)},
        )
        assert resp.status_code == 201, resp.text
        assert _is_member(self.db, self.p2, self.p1_admin.id)

    def test_create_experiment_in_path_project_with_a_different_active_project(self):
        _enroll(self.db, self.org_id, self.p1, self.p2_admin.id, role=None)
        resp = self._call(
            "POST",
            f"/projects/{self.p2}/experiments",
            self.p2_admin,
            active=self.p1,
            json={"name": "cross-project create", "visibility": "shared"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["project_id"] == str(self.p2)

    def test_member_of_p1_cannot_create_experiment_in_p2(self):
        resp = self._call(
            "POST",
            f"/projects/{self.p2}/experiments",
            self.p1_admin,
            active=self.p1,
            json={"name": "not allowed", "visibility": "shared"},
        )
        assert resp.status_code == 403, resp.text
