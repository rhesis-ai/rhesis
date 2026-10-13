"""The built-in Auditor: reads every project, acts in none, org tier only."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from rhesis.backend.ee.rbac.owner_check import has_ee_org_wide_project_access
from tests.backend.ee.rbac._rbac_helpers import (
    _assign_org_role,
    _builtin_role,
    _create_org,
    _create_user,
)


@pytest.mark.parametrize(
    ("role_name", "sees", "acts"),
    [
        ("Owner", True, True),
        ("Admin", True, True),
        ("Auditor", True, False),
        ("Member", False, False),
    ],
)
def test_org_wide_access_by_role(test_db, role_name, sees, acts):
    org_id = _create_org(test_db)
    user_id = _create_user(test_db, org_id)
    _assign_org_role(test_db, org_id, user_id, role_name)

    assert has_ee_org_wide_project_access(test_db, user_id, org_id) is sees
    # The connector writes with no capability check, so a read-only role is kept out.
    assert has_ee_org_wide_project_access(test_db, user_id, org_id, acting=True) is acts


def test_auditor_cannot_be_a_project_role(test_db):
    from rhesis.backend.ee.rbac.router import assign_project_role
    from rhesis.backend.ee.rbac.schemas import ProjectMemberRoleAssign

    org_id = _create_org(test_db)
    role = _builtin_role(test_db, "Auditor")
    current_user = MagicMock(id=uuid.uuid4(), organization_id=org_id)

    with patch("rhesis.backend.ee.rbac.router._get_actor_permissions", return_value=set()):
        with patch("rhesis.backend.ee.rbac.router._get_actor_level", return_value=100):
            with pytest.raises(HTTPException) as exc_info:
                assign_project_role(
                    project_id=uuid.uuid4(),
                    user_id=uuid.uuid4(),
                    body=ProjectMemberRoleAssign(role_id=role.id),
                    db=test_db,
                    current_user=current_user,
                    _org=MagicMock(),
                )

    assert exc_info.value.status_code == 422
    assert "organization tier" in exc_info.value.detail
