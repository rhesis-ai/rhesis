"""Trial test execution authorization (test detail Run test flow).

Covers:
- POST /tests/execute          → test_set:execute
- POST /endpoints/{id}/invoke  → endpoint:update

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_trial_execute_authz.py -v
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission, get_all_capabilities
from rhesis.backend.ee.rbac.models import permissions_for_built_in_role
from tests.backend.ee.rbac._rbac_helpers import _assign_org_role, _ee_provider_active, _rbac_enabled
from tests.backend.fixtures.test_setup import create_test_organization_and_user


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token.token}"}


def _make_user(test_db: Session, role_name: str):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    org, user, token = create_test_organization_and_user(
        test_db,
        f"Trial Execute AuthZ {role_name} {ts}_{suffix}",
        f"trial_exec_{role_name.lower()}_{suffix}@rhesis-test.com",
        f"Trial {role_name}",
    )
    org.owner_id = None
    test_db.flush()
    _assign_org_role(test_db, org.id, user.id, role_name)
    test_db.commit()
    return org, user, token


@pytest.mark.ee
class TestTrialExecuteBuiltInRolePermissions:
    def test_viewer_cannot_execute_tests(self):
        perms = permissions_for_built_in_role("Viewer", get_all_capabilities())
        assert Permission.TestSet.EXECUTE not in perms
        assert Permission.Endpoint.UPDATE not in perms

    def test_member_can_execute_tests(self):
        perms = permissions_for_built_in_role("Member", get_all_capabilities())
        assert Permission.TestSet.EXECUTE in perms
        assert Permission.Endpoint.UPDATE in perms


@pytest.mark.ee
@pytest.mark.integration
class TestTrialExecuteHttp:
    def test_viewer_cannot_post_tests_execute(self, client, test_db):
        _org, _user, token = _make_user(test_db, "Viewer")

        with _ee_provider_active(), _rbac_enabled():
            resp = client.post(
                "/tests/execute",
                json={
                    "endpoint_id": str(uuid.uuid4()),
                    "test_configuration": {"goal": "test goal"},
                    "behavior": "b",
                    "topic": "t",
                    "category": "c",
                },
                headers=_auth(token),
            )

        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.headers.get("X-Accepted-Permissions") == Permission.TestSet.EXECUTE

    def test_member_may_post_tests_execute(self, client, test_db):
        """Member passes the capability gate (may fail later on validation/model)."""
        _org, _user, token = _make_user(test_db, "Member")

        with _ee_provider_active(), _rbac_enabled():
            resp = client.post(
                "/tests/execute",
                json={"endpoint_id": str(uuid.uuid4())},
                headers=_auth(token),
            )

        assert resp.status_code != status.HTTP_403_FORBIDDEN, resp.text

    def test_viewer_cannot_invoke_endpoint(self, client, test_db):
        _org, _user, token = _make_user(test_db, "Viewer")

        with _ee_provider_active(), _rbac_enabled():
            resp = client.post(
                f"/endpoints/{uuid.uuid4()}/invoke",
                json={"input": "hello"},
                headers=_auth(token),
            )

        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.headers.get("X-Accepted-Permissions") == Permission.Endpoint.UPDATE

    def test_member_may_invoke_endpoint(self, client, test_db):
        """Member passes the capability gate (may fail later on 404/validation)."""
        _org, _user, token = _make_user(test_db, "Member")

        with _ee_provider_active(), _rbac_enabled():
            resp = client.post(
                f"/endpoints/{uuid.uuid4()}/invoke",
                json={"input": "hello"},
                headers=_auth(token),
            )

        assert resp.status_code != status.HTTP_403_FORBIDDEN, resp.text
