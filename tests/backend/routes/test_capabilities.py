"""Integration tests for the ``GET /capabilities`` and ``GET /me/permissions`` endpoints.

Both endpoints are wired up in
:mod:`rhesis.backend.app.routers.capabilities`.  The tests here do **not**
require a real database: all SQLAlchemy query chains are mocked, mirroring the
approach used in ``test_features.py``.

Test coverage:
- ``GET /capabilities`` — auth guard, response shape, known capabilities present.
- ``GET /me/permissions`` — auth guard, org-owner gets all, non-member gets none,
  project-member gets project-scoped, ``?project_id`` query param plumbing.
"""

from __future__ import annotations

from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.main import app

_TEST_ORG_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_TEST_USER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_TEST_PROJECT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# ---------------------------------------------------------------------------
# Module-level fixture: ensure capabilities are registered for every test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def ensure_capabilities_registered():
    """Re-register capabilities before each test and reset after.

    Other test modules (e.g. test_rbac.py) may call ``reset_capabilities()``
    in their teardown, leaving the cache empty.  This autouse fixture re-fills
    it so every test in this module always sees a non-empty registry.
    """
    from rhesis.backend.app.auth.capabilities import register_capabilities, reset_capabilities
    from rhesis.backend.app.main import app

    register_capabilities(app)
    yield
    reset_capabilities()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_mock(*, is_owner: bool, is_member: bool) -> Mock:
    """Return a mock SQLAlchemy session whose query chains behave as requested.

    The ``DefaultAuthorizationProvider`` makes exactly two query patterns:

    1. ``db.query(Organization).filter_by(id=..., owner_id=...).first()``
    2. ``db.query(ProjectMembership).filter_by(...).first()``

    We dispatch on the model class so each pattern returns its expected value
    independently.
    """
    from rhesis.backend.app.models.organization import Organization
    from rhesis.backend.app.models.project_membership import ProjectMembership

    def _query_side_effect(model):
        q = Mock()
        if model is Organization:
            q.filter_by.return_value.first.return_value = Mock() if is_owner else None
        elif model is ProjectMembership:
            q.filter_by.return_value.first.return_value = Mock() if is_member else None
        else:
            q.filter_by.return_value.first.return_value = None
        return q

    db = Mock()
    db.query.side_effect = _query_side_effect
    return db


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_org_owner():
    """Override auth/tenant deps so the caller appears as an org owner.

    The ``apply_auth_backstop`` wires ``require_current_user_or_token`` directly
    onto every non-public route, so we override it alongside the tenant deps.
    """
    user_stub = Mock(id=_TEST_USER_ID, organization_id=_TEST_ORG_ID)
    db_stub = _make_db_mock(is_owner=True, is_member=False)

    app.dependency_overrides[require_current_user_or_token] = lambda: user_stub
    app.dependency_overrides[get_tenant_context] = lambda: (_TEST_ORG_ID, _TEST_USER_ID)
    app.dependency_overrides[get_tenant_db_session] = lambda: db_stub  # type: ignore[return-value]
    yield user_stub
    app.dependency_overrides.clear()


@pytest.fixture
def mock_non_member():
    """Override auth deps so the caller has an org but is *not* an owner or member."""
    user_stub = Mock(id=_TEST_USER_ID, organization_id=_TEST_ORG_ID)
    db_stub = _make_db_mock(is_owner=False, is_member=False)

    app.dependency_overrides[require_current_user_or_token] = lambda: user_stub
    app.dependency_overrides[get_tenant_context] = lambda: (_TEST_ORG_ID, _TEST_USER_ID)
    app.dependency_overrides[get_tenant_db_session] = lambda: db_stub  # type: ignore[return-value]
    yield user_stub
    app.dependency_overrides.clear()


@pytest.fixture
def mock_project_member():
    """Override auth deps so the caller is a project member (but not org owner)."""
    user_stub = Mock(id=_TEST_USER_ID, organization_id=_TEST_ORG_ID)
    db_stub = _make_db_mock(is_owner=False, is_member=True)

    app.dependency_overrides[require_current_user_or_token] = lambda: user_stub
    app.dependency_overrides[get_tenant_context] = lambda: (_TEST_ORG_ID, _TEST_USER_ID)
    app.dependency_overrides[get_tenant_db_session] = lambda: db_stub  # type: ignore[return-value]
    yield user_stub
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client() -> TestClient:
    """Plain test client with no dependency overrides (for auth-guard tests)."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def authed_client() -> TestClient:
    """Test client whose fixture setup is deferred — use alongside a mock_* fixture."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /capabilities
# ---------------------------------------------------------------------------


class TestListCapabilities:
    def test_requires_authentication(self, unauthed_client: TestClient):
        resp = unauthed_client.get("/capabilities")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_200_for_authenticated_user(
        self, authed_client: TestClient, mock_org_owner
    ):
        resp = authed_client.get("/capabilities")
        assert resp.status_code == status.HTTP_200_OK

    def test_response_is_list_of_strings(
        self, authed_client: TestClient, mock_org_owner
    ):
        resp = authed_client.get("/capabilities")
        body = resp.json()
        assert isinstance(body, list)
        assert all(isinstance(c, str) for c in body)

    def test_response_is_non_empty(self, authed_client: TestClient, mock_org_owner):
        resp = authed_client.get("/capabilities")
        assert len(resp.json()) > 0

    def test_response_is_sorted(self, authed_client: TestClient, mock_org_owner):
        caps = authed_client.get("/capabilities").json()
        assert caps == sorted(caps)

    def test_response_contains_core_capabilities(
        self, authed_client: TestClient, mock_org_owner
    ):
        caps = set(authed_client.get("/capabilities").json())
        for expected in (
            "behavior:read",
            "behavior:create",
            "test_set:read",
            "test_set:execute",
            "organization:read",
            "comment:react",
            "recycle:restore",
        ):
            assert expected in caps, f"GET /capabilities is missing '{expected}'"

    def test_all_capabilities_match_resource_action_format(
        self, authed_client: TestClient, mock_org_owner
    ):
        import re

        # resource:action, optionally with an object-level qualifier (SP10),
        # e.g. comment:update:own or task:update:assigned.
        pattern = re.compile(r"^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*(:own|:assigned)?$")
        for cap in authed_client.get("/capabilities").json():
            assert pattern.match(cap), (
                f"Capability '{cap}' does not match resource:action format"
            )

    def test_same_result_regardless_of_caller_identity(
        self,
        authed_client: TestClient,
        mock_org_owner,
        mock_non_member,
    ):
        """GET /capabilities is not filtered per caller — it's the full catalog."""
        # mock_org_owner is applied last; both fixtures produce the same list
        resp = authed_client.get("/capabilities")
        assert resp.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# GET /me/permissions
# ---------------------------------------------------------------------------


class TestGetMyPermissions:
    def test_requires_authentication(self, unauthed_client: TestClient):
        resp = unauthed_client.get("/me/permissions")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_org_owner_receives_all_capabilities(
        self, authed_client: TestClient, mock_org_owner
    ):
        from rhesis.backend.app.auth.capabilities import get_all_capabilities

        all_caps = set(get_all_capabilities())
        my_perms = set(authed_client.get("/me/permissions").json())
        assert all_caps == my_perms, (
            f"Org owner should have all capabilities. "
            f"Missing: {all_caps - my_perms}. "
            f"Extra: {my_perms - all_caps}."
        )

    def test_non_member_without_project_id_gets_standard_capabilities(
        self, authed_client: TestClient, mock_non_member
    ):
        """Org member without ownership or project membership gets standard (non-owner) capabilities.

        Community tier rule: any authenticated org member may exercise non-owner-only
        capabilities when no project scope is given.  The ORM scope already limits
        visible rows to the caller's organization, so no extra gate is needed.
        Owner-only capabilities (organization:update, member:manage, etc.) are excluded.
        """
        from rhesis.backend.app.auth.capabilities import get_all_capabilities
        from rhesis.backend.app.auth.rbac import _OWNER_ONLY_CAPABILITIES

        all_caps = set(get_all_capabilities())
        expected = all_caps - _OWNER_ONLY_CAPABILITIES
        resp = authed_client.get("/me/permissions")
        assert resp.status_code == status.HTTP_200_OK
        my_perms = set(resp.json())
        assert my_perms == expected, (
            f"Org member should hold standard capabilities without project scope. "
            f"Missing: {expected - my_perms}. Extra: {my_perms - expected}."
        )

    def test_project_member_with_project_id_gets_all_capabilities(
        self, authed_client: TestClient, mock_project_member
    ):
        """Project member gets all capabilities when the project_id scope matches."""
        from rhesis.backend.app.auth.capabilities import get_all_capabilities

        all_caps = set(get_all_capabilities())
        my_perms = set(
            authed_client.get(
                "/me/permissions", params={"project_id": str(_TEST_PROJECT_ID)}
            ).json()
        )
        assert all_caps == my_perms, (
            f"Project member should have all capabilities for their project. "
            f"Missing: {all_caps - my_perms}."
        )

    def test_project_member_without_project_id_gets_standard_capabilities(
        self, authed_client: TestClient, mock_project_member
    ):
        """Project member omitting project_id gets standard (non-owner) capabilities.

        Project membership is project-scoped; without the project_id query param the
        provider falls through to the org-member rule, granting non-owner-only capabilities.
        """
        from rhesis.backend.app.auth.capabilities import get_all_capabilities
        from rhesis.backend.app.auth.rbac import _OWNER_ONLY_CAPABILITIES

        all_caps = set(get_all_capabilities())
        expected = all_caps - _OWNER_ONLY_CAPABILITIES
        resp = authed_client.get("/me/permissions")
        assert resp.status_code == status.HTTP_200_OK
        my_perms = set(resp.json())
        assert my_perms == expected, (
            f"Org member (project member without project scope) should hold standard capabilities. "
            f"Missing: {expected - my_perms}. Extra: {my_perms - expected}."
        )

    def test_response_is_sorted(self, authed_client: TestClient, mock_org_owner):
        perms = authed_client.get("/me/permissions").json()
        assert perms == sorted(perms)

    def test_invalid_project_id_returns_422(
        self, authed_client: TestClient, mock_org_owner
    ):
        resp = authed_client.get("/me/permissions", params={"project_id": "not-a-uuid"})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_response_is_subset_of_all_capabilities(
        self, authed_client: TestClient, mock_non_member
    ):
        """Whatever the caller holds must be a subset of the full catalog."""
        from rhesis.backend.app.auth.capabilities import get_all_capabilities

        all_caps = set(get_all_capabilities())
        my_perms = set(authed_client.get("/me/permissions").json())
        assert my_perms <= all_caps, (
            f"Caller cannot hold capabilities outside the catalog: {my_perms - all_caps}"
        )
