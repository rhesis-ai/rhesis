"""End-to-end authz enforcement for the SSO admin endpoints over HTTP.

GitHub issue #1748: the SSO admin endpoints (``GET/PUT/DELETE
/organizations/{org_id}/sso``, ``POST .../sso/test``) must be reachable only
by an org admin/owner, not any org member — the config includes the IdP
``client_secret``. Two things gate these routes and both are exercised here:

1. The ``@capability(Permission.SSO.MANAGE)``-driven authz backstop
   (``apply_authz_backstop`` in ``main.py``), which denies non-owners before
   the route handler body runs at all.
2. ``_require_org_admin`` in ``ee/backend/.../sso/router.py``, which adds a
   same-org guard (the backstop's capability check is evaluated against the
   caller's *own* org, not the ``org_id`` path parameter — without this guard
   an owner of org A could reach org B's SSO config) plus a redundant PDP
   role check so the function is correct standalone.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/ee/sso/test_sso_admin_authz_http.py -v
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from tests.backend.ee.rbac._rbac_helpers import _assign_org_role, _ee_provider_active
from tests.backend.fixtures.test_setup import create_test_organization_and_user

VALID_SSO_BODY = {
    "issuer_url": "https://idp.example.com",
    "client_id": "test-client",
    "client_secret": "test-secret",
}


def _ee_active():
    return _ee_provider_active()


def _context(test_db, role_name: str):
    """Create a fresh org + user + token, assigned the given built-in org role."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    org, user, token = create_test_organization_and_user(
        test_db,
        f"SSO AuthZ {role_name} {ts}_{suffix}",
        f"sso_authz_{role_name.lower()}_{suffix}@rhesis-test.com",
        f"SSO AuthZ {role_name} User",
    )
    if role_name != "Owner":
        org.owner_id = None
        test_db.flush()
        _assign_org_role(test_db, org.id, user.id, role_name)
    test_db.commit()
    return org, user, token


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token.token}"}


@pytest.mark.ee
@pytest.mark.integration
@pytest.mark.security
class TestSsoAdminDeniedForNonOwners:
    """A plain Member or non-Owner Admin must get 403 on every SSO admin route."""

    @pytest.mark.parametrize("role_name", ["Member", "Admin", "Viewer"])
    def test_get_sso_config_denied(self, client, test_db, role_name):
        org, _user, token = _context(test_db, role_name)
        with _ee_active():
            resp = client.get(f"/organizations/{org.id}/sso", headers=_auth(token))
        assert resp.status_code == 403, resp.text
        assert resp.headers.get("X-Accepted-Permissions") == "sso:manage"

    @pytest.mark.parametrize("role_name", ["Member", "Admin", "Viewer"])
    def test_update_sso_config_denied(self, client, test_db, role_name):
        org, _user, token = _context(test_db, role_name)
        with _ee_active():
            resp = client.put(
                f"/organizations/{org.id}/sso",
                json=VALID_SSO_BODY,
                headers=_auth(token),
            )
        assert resp.status_code == 403, resp.text

    @pytest.mark.parametrize("role_name", ["Member", "Admin", "Viewer"])
    def test_delete_sso_config_denied(self, client, test_db, role_name):
        org, _user, token = _context(test_db, role_name)
        with _ee_active():
            resp = client.delete(f"/organizations/{org.id}/sso", headers=_auth(token))
        assert resp.status_code == 403, resp.text

    @pytest.mark.parametrize("role_name", ["Member", "Admin", "Viewer"])
    def test_test_connection_denied(self, client, test_db, role_name):
        org, _user, token = _context(test_db, role_name)
        with _ee_active():
            resp = client.post(f"/organizations/{org.id}/sso/test", headers=_auth(token))
        assert resp.status_code == 403, resp.text


@pytest.mark.ee
@pytest.mark.integration
@pytest.mark.security
class TestSsoAdminAllowedForOwner:
    """The org Owner is allowed through the authz gate on every SSO admin route."""

    def test_get_sso_config_allowed(self, client, test_db):
        org, _user, token = _context(test_db, "Owner")
        with _ee_active():
            resp = client.get(f"/organizations/{org.id}/sso", headers=_auth(token))
        assert resp.status_code != 403, resp.text

    def test_update_sso_config_allowed(self, client, test_db):
        org, _user, token = _context(test_db, "Owner")
        with _ee_active():
            resp = client.put(
                f"/organizations/{org.id}/sso",
                json=VALID_SSO_BODY,
                headers=_auth(token),
            )
        assert resp.status_code != 403, resp.text

    def test_delete_sso_config_allowed(self, client, test_db):
        org, _user, token = _context(test_db, "Owner")
        with _ee_active():
            resp = client.delete(f"/organizations/{org.id}/sso", headers=_auth(token))
        assert resp.status_code != 403, resp.text

    def test_test_connection_allowed(self, client, test_db):
        org, _user, token = _context(test_db, "Owner")
        with _ee_active():
            resp = client.post(f"/organizations/{org.id}/sso/test", headers=_auth(token))
        assert resp.status_code != 403, resp.text


@pytest.mark.ee
@pytest.mark.integration
@pytest.mark.security
class TestSsoAdminCrossOrgDenied:
    """An Owner of org A must not reach org B's SSO config via the path param.

    The ``sso:manage`` capability check is evaluated against the caller's own
    org context, not the ``org_id`` in the URL — only ``_require_org_admin``'s
    same-org guard catches a mismatched path parameter.
    """

    def test_owner_cannot_read_other_orgs_sso_config(self, client, test_db):
        _owner_org, _owner_user, owner_token = _context(test_db, "Owner")
        other_org, _other_user, _other_token = _context(test_db, "Owner")
        with _ee_active():
            resp = client.get(f"/organizations/{other_org.id}/sso", headers=_auth(owner_token))
        assert resp.status_code == 403, resp.text

    def test_owner_cannot_update_other_orgs_sso_config(self, client, test_db):
        _owner_org, _owner_user, owner_token = _context(test_db, "Owner")
        other_org, _other_user, _other_token = _context(test_db, "Owner")
        with _ee_active():
            resp = client.put(
                f"/organizations/{other_org.id}/sso",
                json=VALID_SSO_BODY,
                headers=_auth(owner_token),
            )
        assert resp.status_code == 403, resp.text

    def test_owner_cannot_delete_other_orgs_sso_config(self, client, test_db):
        _owner_org, _owner_user, owner_token = _context(test_db, "Owner")
        other_org, _other_user, _other_token = _context(test_db, "Owner")
        with _ee_active():
            resp = client.delete(f"/organizations/{other_org.id}/sso", headers=_auth(owner_token))
        assert resp.status_code == 403, resp.text

    def test_owner_cannot_test_connection_on_other_orgs_sso_config(self, client, test_db):
        _owner_org, _owner_user, owner_token = _context(test_db, "Owner")
        other_org, _other_user, _other_token = _context(test_db, "Owner")
        with _ee_active():
            resp = client.post(
                f"/organizations/{other_org.id}/sso/test", headers=_auth(owner_token)
            )
        assert resp.status_code == 403, resp.text
