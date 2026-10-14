"""Members and Auditors manage their own API tokens; only Owner and Admin delete projects."""

from __future__ import annotations

import pytest

from rhesis.backend.app.auth.rbac import authorize
from tests.backend.ee.rbac._rbac_helpers import (
    _add_project_member,
    _assign_org_role,
    _assign_project_role,
    _create_org,
    _create_project,
    _create_user,
    _ee_provider_active,
    _principal,
)


@pytest.fixture
def member(test_db):
    org_id = _create_org(test_db)
    project_id = _create_project(test_db, org_id)
    user_id = _create_user(test_db, org_id)
    return org_id, project_id, user_id


def _can(db, user_id, org_id, permission, project_id=None) -> bool:
    with _ee_provider_active():
        return authorize(_principal(user_id, org_id), permission, project_id=project_id, db=db)


TOKEN_PERMISSIONS = ["token:create", "token:read", "token:update", "token:delete"]


@pytest.mark.parametrize("role", ["Member", "Auditor"])
@pytest.mark.parametrize("permission", TOKEN_PERMISSIONS)
def test_member_and_auditor_manage_own_tokens(test_db, member, role, permission):
    org_id, _, user_id = member
    _assign_org_role(test_db, org_id, user_id, role)

    assert _can(test_db, user_id, org_id, permission)


def test_viewer_still_has_no_tokens(test_db, member):
    org_id, _, user_id = member
    _assign_org_role(test_db, org_id, user_id, "Viewer")

    assert not _can(test_db, user_id, org_id, "token:create")


@pytest.mark.parametrize(
    ("org_role", "project_role", "deletes"),
    [
        ("Member", None, False),
        ("Viewer", "Member", False),
        ("Member", "Admin", True),
        ("Admin", None, True),
    ],
)
def test_project_delete_needs_admin(test_db, member, org_role, project_role, deletes):
    org_id, project_id, user_id = member
    _assign_org_role(test_db, org_id, user_id, org_role)
    if project_role:
        _assign_project_role(test_db, org_id, project_id, user_id, project_role)
    else:
        _add_project_member(test_db, org_id, project_id, user_id)

    assert _can(test_db, user_id, org_id, "project:update", project_id)
    assert _can(test_db, user_id, org_id, "project:delete", project_id) is deletes
