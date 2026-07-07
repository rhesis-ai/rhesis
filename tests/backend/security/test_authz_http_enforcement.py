"""End-to-end PEP enforcement over HTTP (SP4 backstop).

Every other RBAC test exercises the decision logic at the ``authorize()`` (PDP)
level or verifies the route→capability mapping statically. None of them fire a
real HTTP request through the wired enforcement point. This suite closes that
loop: it boots the real FastAPI app (``apply_authz_backstop`` already applied at
import) via ``TestClient`` and asserts that real requests are allowed or denied
(200 vs 403) by the injected ``require_permission`` dependency.

A bug in the backstop *wiring* — a route whose dependency isn't copied on
``include_router``, a dependency-ordering issue, an ``AUTHZ_EXEMPT_ROUTES``
mistake — would pass the PDP and static-coverage tests yet fail here.

Tier: community (RBAC ships dark — the default deployed state). The community
``DefaultAuthorizationProvider`` governs:
- org owner → allowed for owner-only capabilities,
- non-owner org member → denied for owner-only capabilities (403),
- non-owner org member → allowed for ordinary read capabilities,
- unauthenticated → 401 before authorization runs.

The EE per-role matrix is exhaustively covered at the provider level in
``tests/backend/ee/rbac/test_sp8_access_control.py``.

Routes used (resolved from the live capability map):
- ``PUT /organizations/{id}`` → ``organization:update`` (owner-only, core/non-EE).
- ``GET /behaviors/`` → ``behavior:read`` (ordinary, not owner-only).

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/security/test_authz_http_enforcement.py -v
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from tests.backend.fixtures.test_setup import create_test_organization_and_user

# Route + capability under test (kept in sync with the live capability map).
OWNER_ONLY_ROUTE_CAP = "organization:update"
ORDINARY_READ_ROUTE = "/behaviors/"


def _make_context(test_db, *, owner: bool):
    """Create a fresh org + user + API token; return (org, user, token).

    ``create_test_organization_and_user`` gives the user the Owner role. Under
    RBAC, authorization is decided by that role, not ``organization.owner_id``,
    so for ``owner=False`` we demote the user to the built-in **Member** role
    (a plain org member — lacks org-admin caps like organization:update, but
    keeps ordinary reads). Commit so the auth path — which resolves the token
    on its own ``get_db()`` connection — sees the rows.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    org, user, token = create_test_organization_and_user(
        test_db,
        f"AuthZ HTTP {'Owner' if owner else 'Member'} {ts}_{suffix}",
        f"authz_http_{suffix}@rhesis-test.com",
        "AuthZ HTTP User",
    )
    if not owner:
        org.owner_id = None  # plain member, not the org owner
        test_db.flush()
        _demote_to_member(test_db, org.id, user.id)
    test_db.commit()
    return org, user, token


def _demote_to_member(test_db, organization_id, user_id) -> None:
    """Set the user's org-member role to the built-in Member role (no-op in community)."""
    try:
        from rhesis.backend.app.scope import bypass_tenant_filter
        from rhesis.backend.ee.rbac.models import OrganizationMember, Role
    except ImportError:
        return
    with bypass_tenant_filter():
        member_role = (
            test_db.query(Role)
            .filter_by(name="Member", is_built_in=True, organization_id=None)
            .first()
        )
        member = (
            test_db.query(OrganizationMember)
            .filter_by(organization_id=organization_id, user_id=user_id)
            .first()
        )
    if member_role is not None and member is not None:
        member.role_id = member_role.id
        test_db.flush()


def _auth(token) -> dict:
    return {"Authorization": f"Bearer {token.token}"}


@pytest.mark.integration
@pytest.mark.security
class TestHttpAuthzEnforcement:
    """The PEP backstop must enforce on real HTTP requests, not just in theory."""

    def test_unauthenticated_request_is_401(self, client):
        """A protected route with no credentials is rejected before authorization."""
        resp = client.get(ORDINARY_READ_ROUTE)
        assert resp.status_code == 401, resp.text

    def test_owner_allowed_on_owner_only_route(self, client, test_db):
        """Org owner passes the owner-only capability gate (not 403)."""
        org, _user, token = _make_context(test_db, owner=True)
        resp = client.put(
            f"/organizations/{org.id}",
            json={"name": f"Renamed {uuid.uuid4().hex[:6]}"},
            headers=_auth(token),
        )
        assert resp.status_code != 403, (
            f"Org owner was wrongly denied organization:update: {resp.status_code} {resp.text}"
        )

    def test_non_owner_denied_on_owner_only_route(self, client, test_db):
        """Non-owner org member is denied the owner-only capability (403 + header).

        This is the core proof that the backstop fires on a real request.
        """
        org, _user, token = _make_context(test_db, owner=False)
        resp = client.put(
            f"/organizations/{org.id}",
            json={"name": "should-be-denied"},
            headers=_auth(token),
        )
        assert resp.status_code == 403, (
            f"Expected 403 for non-owner organization:update, got {resp.status_code}: {resp.text}"
        )
        # GitHub-style header naming the missing capability (SP12).
        assert resp.headers.get("X-Accepted-Permissions") == OWNER_ONLY_ROUTE_CAP

    def test_non_owner_allowed_on_ordinary_read_route(self, client, test_db):
        """Backstop does not over-block: a non-owner member may read ordinary resources."""
        _org, _user, token = _make_context(test_db, owner=False)
        resp = client.get(ORDINARY_READ_ROUTE, headers=_auth(token))
        assert resp.status_code != 403, (
            f"Non-owner member wrongly denied behavior:read: {resp.status_code} {resp.text}"
        )
        assert resp.status_code == 200, resp.text
