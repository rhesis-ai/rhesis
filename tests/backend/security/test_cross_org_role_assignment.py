"""Role assignment only accepts built-in roles or the caller's own org's custom roles.

Runs as the superuser so RLS cannot hide the foreign role; the app check has to.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

pytest.importorskip("rhesis.backend.ee", reason="EE package not installed")

from rhesis.backend.ee.rbac.models import SCOPE_ORGANIZATION, SCOPE_PROJECT
from rhesis.backend.ee.rbac.router import (
    assign_org_role,
    check_project_role_assignment,
    delete_role,
    update_role,
)
from rhesis.backend.ee.rbac.schemas import OrgRoleAssign, RoleUpdate
from tests.backend.ee.rbac._rbac_helpers import (
    _create_org,
    _create_project,
    _create_user,
    _custom_role,
    _user,
)

pytestmark = [pytest.mark.security, pytest.mark.ee]


@pytest.fixture
def orgs(admin_test_db):
    db = admin_test_db
    org_a = _create_org(db)
    actor = _user(_create_user(db, org_a), org_a)
    project_a = _create_project(db, org_a)
    org_b = _create_org(db)
    return {
        "db": db,
        "org_a": org_a,
        "actor": actor,
        "project_a": project_a,
        "org_b": org_b,
        "target": _create_user(db, org_a),
    }


@pytest.fixture(autouse=True)
def _unrestricted_actor():
    with (
        patch("rhesis.backend.ee.rbac.router._get_actor_permissions", return_value=set()),
        patch("rhesis.backend.ee.rbac.router._get_actor_level", return_value=100),
        patch("rhesis.backend.ee.rbac.router._check_escalation"),
    ):
        yield


def test_project_assignment_rejects_other_orgs_role(orgs):
    foreign = _custom_role(orgs["db"], orgs["org_b"], name="B role", scope=SCOPE_PROJECT)

    with pytest.raises(HTTPException) as exc:
        check_project_role_assignment(orgs["db"], orgs["actor"], foreign.id, orgs["project_a"])

    assert exc.value.status_code == 404


def test_project_assignment_accepts_own_orgs_role(orgs):
    own = _custom_role(orgs["db"], orgs["org_a"], name="A role", scope=SCOPE_PROJECT)

    role = check_project_role_assignment(orgs["db"], orgs["actor"], own.id, orgs["project_a"])

    assert role.id == own.id


def test_org_assignment_rejects_other_orgs_role(orgs):
    foreign = _custom_role(orgs["db"], orgs["org_b"], name="B org role", scope=SCOPE_ORGANIZATION)

    with pytest.raises(HTTPException) as exc:
        assign_org_role(
            user_id=orgs["target"],
            body=OrgRoleAssign(role_id=foreign.id),
            db=orgs["db"],
            current_user=orgs["actor"],
            _org=MagicMock(),
        )

    assert exc.value.status_code == 404


def test_unknown_role_is_404(orgs):
    with pytest.raises(HTTPException) as exc:
        check_project_role_assignment(orgs["db"], orgs["actor"], uuid.uuid4(), orgs["project_a"])

    assert exc.value.status_code == 404


def test_update_other_orgs_role_is_404(orgs):
    foreign = _custom_role(orgs["db"], orgs["org_b"], name="B edit", scope=SCOPE_PROJECT)

    with pytest.raises(HTTPException) as exc:
        update_role(
            role_id=foreign.id,
            body=RoleUpdate(display_name="taken"),
            db=orgs["db"],
            current_user=orgs["actor"],
            _org=None,
        )

    assert exc.value.status_code == 404
    orgs["db"].refresh(foreign)
    assert foreign.display_name == "B edit"


def test_delete_other_orgs_role_is_404(orgs):
    foreign = _custom_role(orgs["db"], orgs["org_b"], name="B delete", scope=SCOPE_PROJECT)

    with pytest.raises(HTTPException) as exc:
        delete_role(role_id=foreign.id, db=orgs["db"], current_user=orgs["actor"], _org=None)

    assert exc.value.status_code == 404
    orgs["db"].refresh(foreign)
    assert foreign.deleted_at is None
