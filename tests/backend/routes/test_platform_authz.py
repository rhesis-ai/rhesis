"""HTTP-level authz enforcement for the platform key admin endpoints.

Mirrors ``tests/backend/ee/sso/test_sso_admin_authz_http.py``'s shape:
``PUT``/``DELETE /platform/rhesis-key`` require ``Permission.Platform.MANAGE``,
which is owner-only via ``_OWNER_ONLY_CAPABILITIES`` in the community-tier PDP
fallback and via the built-in role catalog in EE. ``GET`` stays open to any
authenticated org member (read-only, never exposes the raw key).

Unlike SSO, there is no ``org_id`` path parameter here -- the org is always
resolved from the caller's own ``current_user.organization_id`` -- so there is
no cross-org test class to mirror.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/routes/test_platform_authz.py -v
"""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.backend.ee.rbac._rbac_helpers import _assign_org_role, _ee_provider_active
from tests.backend.fixtures.test_setup import create_test_organization_and_user


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token.token}"}


def _rhesis_key_enabled():
    """Patch require_rhesis_key_enabled's settings check so the routes don't 404."""
    settings = type("_Settings", (), {"enable_rhesis_key": True})()
    return patch(
        "rhesis.backend.app.auth.feature_gates.get_application_settings",
        return_value=settings,
    )


def _no_op_validation():
    """Avoid a real network call to the hosted platform during PUT tests."""
    return patch(
        "rhesis.backend.app.services.platform_key.validate_platform_key",
        return_value={"valid": None, "polyphemus_authorized": None},
    )


def _context(test_db: Session, role_name: str):
    """Create a fresh org + user + token, assigned the given built-in org role.

    Mirrors ``tests/backend/ee/sso/test_sso_admin_authz_http.py``'s helper:
    the created user is the org owner by default (``create_test_organization_and_user``
    also gives them an explicit ``OrganizationMember`` row with the Owner
    role), so exercising a non-owner role means clearing ``owner_id`` *and*
    reassigning that membership row via ``_assign_org_role`` -- clearing
    ``owner_id`` alone leaves the pre-existing Owner membership row in place.
    """
    suffix = uuid.uuid4().hex[:8]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    org, user, token = create_test_organization_and_user(
        test_db,
        f"Platform Authz {role_name} {ts}_{suffix}",
        f"platform_authz_{role_name.lower()}_{suffix}@rhesis-test.com",
        f"Platform Authz {role_name} User",
    )
    if role_name != "Owner":
        org.owner_id = None
        test_db.flush()
        _assign_org_role(test_db, org.id, user.id, role_name)
    test_db.commit()
    return org, user, token


@pytest.mark.integration
@pytest.mark.security
class TestPlatformKeyAdminDeniedForNonOwner:
    """A plain Member (non-owner) must get 403 on PUT/DELETE."""

    def test_set_key_denied(self, client: TestClient, test_db):
        _org, _user, token = _context(test_db, "Member")
        with _ee_provider_active(), _rhesis_key_enabled():
            resp = client.put("/platform/rhesis-key", json={"key": "rh-test"}, headers=_auth(token))
        assert resp.status_code == 403, resp.text

    def test_clear_key_denied(self, client: TestClient, test_db):
        _org, _user, token = _context(test_db, "Member")
        with _ee_provider_active(), _rhesis_key_enabled():
            resp = client.delete("/platform/rhesis-key", headers=_auth(token))
        assert resp.status_code == 403, resp.text

    def test_read_key_status_still_allowed(self, client: TestClient, test_db):
        """GET is read-only (masked key only) and stays open to any member."""
        _org, _user, token = _context(test_db, "Member")
        with _ee_provider_active(), _rhesis_key_enabled():
            resp = client.get("/platform/rhesis-key", headers=_auth(token))
        assert resp.status_code != 403, resp.text


@pytest.mark.integration
@pytest.mark.security
class TestPlatformKeyAdminAllowedForOwner:
    """The org Owner is allowed through the authz gate on every admin route."""

    def test_set_key_allowed(self, client: TestClient, test_db):
        _org, _user, token = _context(test_db, "Owner")
        with _ee_provider_active(), _rhesis_key_enabled(), _no_op_validation():
            resp = client.put("/platform/rhesis-key", json={"key": "rh-test"}, headers=_auth(token))
        assert resp.status_code != 403, resp.text

    def test_clear_key_allowed(self, client: TestClient, test_db):
        _org, _user, token = _context(test_db, "Owner")
        with _ee_provider_active(), _rhesis_key_enabled():
            resp = client.delete("/platform/rhesis-key", headers=_auth(token))
        assert resp.status_code != 403, resp.text
