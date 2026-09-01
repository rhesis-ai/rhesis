"""Integration tests for the ``GET /features`` endpoint."""

from __future__ import annotations

from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_db_session,
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.features import (
    Feature,
    FeatureName,
    FeatureRegistry,
)
from rhesis.backend.app.main import app
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.quota import QuotaResource

_TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000000")


@pytest.fixture
def registered_sso():
    """Ensure SSO is registered for the duration of the test."""
    FeatureRegistry.reset()
    FeatureRegistry.register(
        Feature(
            name=FeatureName.SSO,
            display_name="Single Sign-On",
            description="Per-organization OIDC-based SSO.",
        )
    )
    yield
    FeatureRegistry.reset()


@pytest.fixture
def mock_current_user():
    """Stub the auth/tenant chain.

    ``/features`` resolves its organization through
    ``get_current_organization_optional``, which reads
    ``current_user.organization_id`` and loads the row with ``get_db_session``.
    Both of those are stubbed here, along with the tenant pair other
    dependencies on the route resolve through, so the endpoint never touches a
    real session.

    ``organization_id`` has to be set explicitly on the user stub: a bare
    ``Mock`` would hand back a truthy child mock, which passes the dependency's
    "has an org" guard and then reaches Postgres as an invalid UUID.

    The app's defense-in-depth backstop (``apply_auth_backstop``) also injects
    ``require_current_user_or_token`` directly on the route, so we override it
    too, otherwise the backstop would reject the mocked request with 401.
    """
    org_stub = Mock(spec=Organization)
    org_stub.id = _TEST_ORG_ID

    db_stub = Mock()
    db_stub.get.return_value = org_stub

    user_id = UUID("11111111-1111-1111-1111-111111111111")
    user_stub = Mock(organization=org_stub, organization_id=_TEST_ORG_ID, id=user_id)

    def _override_tenant_context():
        return (_TEST_ORG_ID, user_id)

    def _override_db_session():
        yield db_stub

    app.dependency_overrides[get_tenant_context] = _override_tenant_context
    app.dependency_overrides[get_tenant_db_session] = _override_db_session
    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[require_current_user_or_token] = lambda: user_stub
    yield user_stub
    app.dependency_overrides.clear()


class TestFeaturesEndpoint:
    def test_requires_authentication(self, client: TestClient, registered_sso):
        response = client.get("/features")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_license_info(self, client: TestClient, registered_sso, mock_current_user):
        response = client.get("/features")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "license" in body
        assert body["license"] == {
            "edition": "community",
            "licensed": False,
            "is_paid": False,
        }

    def test_returns_enabled_list(self, client: TestClient, registered_sso, mock_current_user):
        response = client.get("/features")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["enabled"] == ["sso"]

    def test_includes_feature_with_failing_runtime_check(
        self, client: TestClient, mock_current_user
    ):
        """GET /features uses licensed_features, so a failing runtime check
        does not hide the feature from the UI but produces a warning."""
        FeatureRegistry.reset()
        FeatureRegistry.register(
            Feature(
                name=FeatureName.SSO,
                display_name="SSO",
                runtime_check=lambda: False,
            )
        )
        try:
            response = client.get("/features")
            assert response.status_code == status.HTTP_200_OK
            body = response.json()
            assert body["enabled"] == ["sso"]
            assert "sso" in body["warnings"]
        finally:
            FeatureRegistry.reset()

    def test_no_warnings_when_runtime_check_passes(
        self, client: TestClient, registered_sso, mock_current_user
    ):
        response = client.get("/features")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["warnings"] == {}

    def test_omits_feature_when_license_denies(self, client: TestClient, mock_current_user):
        class _Deny:
            def allows_feature(self, feature, org):
                return False

            def info(self, org=None):
                return {"edition": "community", "licensed": False}

        FeatureRegistry.reset()
        FeatureRegistry.register(Feature(name=FeatureName.SSO, display_name="SSO"))
        FeatureRegistry.set_license_provider(_Deny())
        try:
            response = client.get("/features")
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["enabled"] == []
        finally:
            FeatureRegistry.reset()

    def test_response_shape_is_stable(self, client: TestClient, registered_sso, mock_current_user):
        response = client.get("/features")
        body = response.json()
        assert set(body.keys()) == {
            "license",
            "plan",
            "enabled",
            "warnings",
            "limits",
            "is_local",
            "rhesis_key_enabled",
        }
        assert set(body["license"].keys()) == {"edition", "licensed", "is_paid"}
        # `plan` is the client's whole contract for displaying a plan: a label
        # to render verbatim, plus the two booleans that decide styling and
        # whether an upgrade is offered. No tier enum on the wire, so a new tier
        # needs no frontend release. It rides on this response rather than
        # GET /usage because this one is server-seeded in the frontend's
        # protected layout, so plan surfaces have it on first paint.
        assert set(body["plan"].keys()) == {"name", "is_paid", "is_active"}
        assert isinstance(body["plan"]["name"], str) and body["plan"]["name"] != ""
        assert isinstance(body["plan"]["is_paid"], bool)
        assert isinstance(body["plan"]["is_active"], bool)
        assert isinstance(body["enabled"], list)
        assert all(isinstance(name, str) for name in body["enabled"])
        assert isinstance(body["warnings"], dict)
        assert isinstance(body["limits"], dict)
        assert isinstance(body["is_local"], bool)
        assert isinstance(body["rhesis_key_enabled"], bool)

    def test_license_info_reflects_org(self, client: TestClient, registered_sso, mock_current_user):
        """license_info() must always receive the org object, never None.

        May fire more than once per request: QuotaRegistry's
        ConfigQuotaProvider (installed by ee.bootstrap()) also resolves the
        org's edition via FeatureRegistry.license_info() to look up quota
        limits, independent of the router's own call for the ``license``
        field. That's fine in production -- SignedTokenLicenseProvider.info()
        bottoms out in the lru_cache'd verify_token(), so a repeat call is a
        cache hit, not re-verification. The invariant that actually matters
        is that every call gets the real org, never None.
        """
        received_orgs: list = []

        class _CapturingProvider:
            def allows_feature(self, feature, org):
                return True

            def info(self, org=None):
                received_orgs.append(org)
                return {"edition": "enterprise", "licensed": True}

        FeatureRegistry.set_license_provider(_CapturingProvider())
        try:
            response = client.get("/features")
            assert response.status_code == status.HTTP_200_OK
            # Provider must always be called with the org, never None
            assert len(received_orgs) >= 1
            assert all(org is not None for org in received_orgs)
            # is_paid defaults to False because this provider omits it --
            # fail-closed, so an unknown posture never presents as paid.
            assert response.json()["license"] == {
                "edition": "enterprise",
                "licensed": True,
                "is_paid": False,
            }
        finally:
            FeatureRegistry.reset()

    def test_forwards_is_paid_from_the_provider(
        self, client: TestClient, registered_sso, mock_current_user
    ):
        """A paid tier reaches the client as a flag, not as a name to compare.

        The point of carrying ``is_paid`` is that no client has to infer
        paid-ness from ``edition``. This pins the lapsed combination
        (``is_paid`` true, ``licensed`` false) specifically, since that is the
        pair a name comparison gets wrong: the edition still reads
        ``enterprise`` while the licence is dead.
        """

        class _LapsedPaidProvider:
            def allows_feature(self, feature, org):
                return False

            def info(self, org=None):
                return {"edition": "enterprise", "licensed": False, "is_paid": True}

        FeatureRegistry.set_license_provider(_LapsedPaidProvider())
        try:
            response = client.get("/features")
            assert response.status_code == status.HTTP_200_OK
            body = response.json()
            assert body["license"] == {
                "edition": "enterprise",
                "licensed": False,
                "is_paid": True,
            }
            # The same facts, composed for display -- including the qualifier,
            # so the lapsed state is legible without relying on styling.
            assert body["plan"] == {
                "name": "Enterprise (inactive)",
                "is_paid": True,
                "is_active": False,
            }
        finally:
            FeatureRegistry.reset()


ee_pkg = pytest.importorskip(
    "rhesis.backend.ee",
    reason="EE package not installed; skipping EE licensing endpoint tests.",
)


class TestFeaturesEndpointWithSignedProvider:
    """Endpoint tests using the real SignedTokenLicenseProvider.

    Creates a standalone TestClient (no ``client`` fixture / test_db) so that
    mock_current_user overrides are not clobbered by the real-DB client fixture.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, mock_current_user):
        from rhesis.backend.ee.licensing.provider import SignedTokenLicenseProvider

        FeatureRegistry.reset()
        FeatureRegistry.register(Feature(name=FeatureName.SSO, display_name="SSO"))
        FeatureRegistry.set_license_provider(SignedTokenLicenseProvider())
        # Build a TestClient here, after mock_current_user has applied its overrides.
        self._tc = TestClient(app)
        yield
        FeatureRegistry.reset()

    def test_unlicensed_returns_community_and_no_features(self):
        """No license token, in any environment → community, no features."""
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"RHESIS_LICENSE": ""}):
            response = self._tc.get("/features")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["license"]["edition"] == "community"
        assert body["license"]["licensed"] is False
        assert body["enabled"] == []


class TestFeaturesEndpointQuotasOff:
    """With quotas disabled, GET /features returns all-null limits with stable keys."""

    def test_all_limits_null_with_quotas_off(
        self, client: TestClient, registered_sso, mock_current_user, quotas_disabled
    ):
        response = client.get("/features")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        limits = body["limits"]
        assert set(limits.keys()) == {str(r) for r in QuotaResource}
        assert all(v is None for v in limits.values())
