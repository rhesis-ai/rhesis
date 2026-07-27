"""Polyphemus access request authorization and settings affordances.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/rbac/test_polyphemus_access_authz.py -v
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi import status

from rhesis.backend.app.auth.capabilities import Permission
from tests.backend.ee.rbac._rbac_helpers import _assign_org_role, _ee_provider_active, _rbac_enabled
from tests.backend.fixtures.test_setup import create_test_organization_and_user


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token.token}"}


def _make_user(test_db, role_name: str):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    org, user, token = create_test_organization_and_user(
        test_db,
        f"Polyphemus AuthZ {role_name} {ts}_{suffix}",
        f"polyphemus_{role_name.lower()}_{suffix}@rhesis-test.com",
        f"Polyphemus {role_name}",
    )
    org.owner_id = None
    test_db.flush()
    _assign_org_role(test_db, org.id, user.id, role_name)
    test_db.commit()
    return org, user, token


_REQUEST_BODY = {
    "justification": "Need adversarial testing for our insurance chatbot.",
    "expected_monthly_requests": 100,
}


@pytest.mark.ee
@pytest.mark.integration
class TestPolyphemusAccessHttp:
    def test_viewer_cannot_request_polyphemus_access(self, client, test_db):
        _org, _user, token = _make_user(test_db, "Viewer")
        with _ee_provider_active(), _rbac_enabled():
            resp = client.post(
                "/users/request-polyphemus-access",
                json=_REQUEST_BODY,
                headers=_auth(token),
            )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.headers.get("X-Accepted-Permissions") == Permission.Polyphemus.REQUEST

    def test_member_can_request_polyphemus_access(self, client, test_db):
        _org, _user, token = _make_user(test_db, "Member")
        with _ee_provider_active(), _rbac_enabled():
            resp = client.post(
                "/users/request-polyphemus-access",
                json=_REQUEST_BODY,
                headers=_auth(token),
            )
        assert resp.status_code == status.HTTP_200_OK, resp.text


@pytest.mark.ee
@pytest.mark.integration
class TestPolyphemusSettingsAffordances:
    def test_viewer_settings_omit_polyphemus_request_affordance(self, client, test_db):
        _org, user, token = _make_user(test_db, "Viewer")
        with _ee_provider_active(), _rbac_enabled():
            resp = client.get("/users/settings", headers=_auth(token))
        assert resp.status_code == status.HTTP_200_OK
        assert Permission.Polyphemus.REQUEST not in resp.json().get("permitted_actions", [])

    def test_member_settings_include_polyphemus_request_affordance(self, client, test_db):
        _org, user, token = _make_user(test_db, "Member")
        with _ee_provider_active(), _rbac_enabled():
            resp = client.get("/users/settings", headers=_auth(token))
        assert resp.status_code == status.HTTP_200_OK
        assert Permission.Polyphemus.REQUEST in resp.json().get("permitted_actions", [])
