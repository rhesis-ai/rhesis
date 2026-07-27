"""Test set export and associate authorization.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_test_set_export_authz.py -v
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission, get_all_capabilities
from rhesis.backend.app.models.prompt import Prompt
from rhesis.backend.app.models.status import Status
from rhesis.backend.app.models.test import Test, test_test_set_association
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.scope import bypass_tenant_filter
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
        f"TestSet AuthZ {role_name} {ts}_{suffix}",
        f"test_set_{role_name.lower()}_{suffix}@rhesis-test.com",
        f"TestSet {role_name}",
    )
    org.owner_id = None
    test_db.flush()
    _assign_org_role(test_db, org.id, user.id, role_name)
    test_db.commit()
    return org, user, token


def _org_status(test_db: Session, organization_id) -> Status:
    with bypass_tenant_filter():
        status_row = (
            test_db.query(Status).filter_by(organization_id=organization_id).first()
        )
    assert status_row is not None, "Expected seeded status for organization"
    return status_row


def _seed_test_set_with_prompt(test_db: Session, organization_id, user_id):
    status_row = _org_status(test_db, organization_id)
    test_set = TestSet(
        name="Export AuthZ Test Set",
        description="RBAC HTTP test fixture",
        user_id=user_id,
        organization_id=organization_id,
        status_id=status_row.id,
        is_published=False,
        visibility="organization",
    )
    prompt = Prompt(
        content="What is the capital of France?",
        language_code="en",
        expected_response="Paris",
        user_id=user_id,
        organization_id=organization_id,
        status_id=status_row.id,
    )
    test_db.add_all([test_set, prompt])
    test_db.flush()

    test = Test(
        prompt_id=prompt.id,
        priority=1,
        user_id=user_id,
        organization_id=organization_id,
        status_id=status_row.id,
        test_metadata={"source": "rbac_test"},
    )
    test_db.add(test)
    test_db.flush()

    test_db.execute(
        test_test_set_association.insert().values(
            test_id=test.id,
            test_set_id=test_set.id,
            organization_id=organization_id,
            user_id=user_id,
        )
    )
    test_db.commit()
    test_db.refresh(test_set)
    test_db.refresh(test)
    return test_set, test


def _seed_unlinked_test(test_db: Session, organization_id, user_id) -> Test:
    status_row = _org_status(test_db, organization_id)
    prompt = Prompt(
        content="Unlinked prompt for associate test",
        language_code="en",
        user_id=user_id,
        organization_id=organization_id,
        status_id=status_row.id,
    )
    test_db.add(prompt)
    test_db.flush()

    test = Test(
        prompt_id=prompt.id,
        priority=1,
        user_id=user_id,
        organization_id=organization_id,
        status_id=status_row.id,
        test_metadata={"source": "rbac_test"},
    )
    test_db.add(test)
    test_db.commit()
    test_db.refresh(test)
    return test


@pytest.mark.ee
class TestTestSetExportBuiltInRolePermissions:
    def test_viewer_cannot_export_test_sets(self):
        perms = permissions_for_built_in_role("Viewer", get_all_capabilities())
        assert Permission.TestSet.EXPORT not in perms

    def test_member_can_export_test_sets(self):
        perms = permissions_for_built_in_role("Member", get_all_capabilities())
        assert Permission.TestSet.EXPORT in perms

    def test_owner_can_export_test_sets(self):
        perms = permissions_for_built_in_role("Owner", get_all_capabilities())
        assert Permission.TestSet.EXPORT in perms


@pytest.mark.ee
@pytest.mark.integration
class TestTestSetExportHttp:
    def test_viewer_cannot_download_test_set_csv(self, client, test_db):
        org, user, token = _make_user(test_db, "Viewer")
        test_set, _test = _seed_test_set_with_prompt(test_db, org.id, user.id)

        with _ee_provider_active(), _rbac_enabled():
            resp = client.get(
                f"/test_sets/{test_set.id}/download",
                headers=_auth(token),
            )

        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.headers.get("X-Accepted-Permissions") == Permission.TestSet.EXPORT

    def test_member_can_download_test_set_csv(self, client, test_db):
        org, user, token = _make_user(test_db, "Member")
        test_set, _test = _seed_test_set_with_prompt(test_db, org.id, user.id)

        with _ee_provider_active(), _rbac_enabled():
            resp = client.get(
                f"/test_sets/{test_set.id}/download",
                headers=_auth(token),
            )

        assert resp.status_code == status.HTTP_200_OK, resp.text
        assert "text/csv" in resp.headers.get("content-type", "")


@pytest.mark.ee
@pytest.mark.integration
class TestTestSetAssociateHttp:
    def test_viewer_cannot_associate_tests(self, client, test_db):
        org, user, token = _make_user(test_db, "Viewer")
        test_set, _linked = _seed_test_set_with_prompt(test_db, org.id, user.id)
        unlinked = _seed_unlinked_test(test_db, org.id, user.id)

        with _ee_provider_active(), _rbac_enabled():
            resp = client.post(
                f"/test_sets/{test_set.id}/associate",
                json={"test_ids": [str(unlinked.id)]},
                headers=_auth(token),
            )

        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.headers.get("X-Accepted-Permissions") == Permission.TestSet.UPDATE

    def test_member_can_associate_tests(self, client, test_db):
        org, user, token = _make_user(test_db, "Member")
        test_set, _linked = _seed_test_set_with_prompt(test_db, org.id, user.id)
        unlinked = _seed_unlinked_test(test_db, org.id, user.id)

        with _ee_provider_active(), _rbac_enabled():
            resp = client.post(
                f"/test_sets/{test_set.id}/associate",
                json={"test_ids": [str(unlinked.id)]},
                headers=_auth(token),
            )

        assert resp.status_code == status.HTTP_200_OK, resp.text
        assert resp.json()["success"] is True
