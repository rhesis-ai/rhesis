"""Unit tests for :mod:`rhesis.backend.app.features`."""

from __future__ import annotations

import pytest

from rhesis.backend.app.features import (
    DefaultLicenseProvider,
    Feature,
    FeatureName,
    FeatureRegistry,
    LicenseProvider,
)


@pytest.fixture
def clean_registry():
    """Reset the registry before each test, restore the real state after.

    ``ee.bootstrap()`` registers RBAC (and other EE features) exactly once,
    at process import time — it never runs again during a test session. A
    bare ``FeatureRegistry.reset()`` on teardown leaves ``_features`` empty
    for the rest of the suite, so every later test sees RBAC as unregistered
    and every RBAC permission check silently falls back to the community
    provider. Snapshot the pre-test state and restore it instead of wiping.
    """
    saved_features = dict(FeatureRegistry._features)
    saved_license = FeatureRegistry._license
    FeatureRegistry.reset()
    yield
    FeatureRegistry._features = saved_features
    FeatureRegistry._license = saved_license


class _DenyingProvider:
    def allows_feature(self, feature, org):
        return False

    def info(self):
        return {"edition": "enterprise", "licensed": True}


class _AllowingProvider:
    def allows_feature(self, feature, org):
        return True

    def info(self):
        return {"edition": "enterprise", "licensed": True}


class TestIsRegistered:
    """The cheap check: in the registry + runtime check passes. No license."""

    def test_unknown_feature_is_not_registered(self, clean_registry):
        assert FeatureRegistry.is_registered("nonsense") is False

    def test_unregistered_known_enum_returns_false(self, clean_registry):
        assert FeatureRegistry.is_registered(FeatureName.SSO) is False

    def test_registered_feature_returns_true(self, clean_registry):
        FeatureRegistry.register(Feature(name=FeatureName.SSO, display_name="SSO"))
        assert FeatureRegistry.is_registered(FeatureName.SSO) is True

    def test_accepts_raw_string_equivalent(self, clean_registry):
        FeatureRegistry.register(Feature(name=FeatureName.SSO, display_name="SSO"))
        assert FeatureRegistry.is_registered("sso") is True

    def test_runtime_check_failure_makes_unavailable(self, clean_registry):
        FeatureRegistry.register(
            Feature(
                name=FeatureName.SSO,
                display_name="SSO",
                runtime_check=lambda: False,
            )
        )
        assert FeatureRegistry.is_registered(FeatureName.SSO) is False

    def test_does_not_consult_license_provider(self, clean_registry):
        """is_registered ignores the license provider entirely.

        That is the whole point: this is the early-bailout API used in
        OIDC callbacks before an org has been resolved.
        """
        FeatureRegistry.register(Feature(name=FeatureName.SSO, display_name="SSO"))
        FeatureRegistry.set_license_provider(_DenyingProvider())
        assert FeatureRegistry.is_registered(FeatureName.SSO) is True


class TestIsAvailable:
    """The full check: registered + licensed for org + runtime check."""

    def test_unknown_feature_returns_false(self, clean_registry):
        assert FeatureRegistry.is_available("nonsense", org=object()) is False

    def test_unregistered_known_enum_returns_false(self, clean_registry):
        assert FeatureRegistry.is_available(FeatureName.SSO, org=object()) is False

    def test_registered_and_default_provider_returns_true(self, clean_registry):
        FeatureRegistry.register(Feature(name=FeatureName.SSO, display_name="SSO"))
        # DefaultLicenseProvider allows everything; org is just a sentinel here.
        assert FeatureRegistry.is_available(FeatureName.SSO, org=object()) is True

    def test_accepts_raw_string_equivalent(self, clean_registry):
        FeatureRegistry.register(Feature(name=FeatureName.SSO, display_name="SSO"))
        assert FeatureRegistry.is_available("sso", org=object()) is True

    def test_denying_license_provider_blocks(self, clean_registry):
        FeatureRegistry.register(Feature(name=FeatureName.SSO, display_name="SSO"))
        FeatureRegistry.set_license_provider(_DenyingProvider())
        assert FeatureRegistry.is_available(FeatureName.SSO, org=object()) is False

    def test_runtime_check_failure_blocks(self, clean_registry):
        FeatureRegistry.register(
            Feature(
                name=FeatureName.SSO,
                display_name="SSO",
                runtime_check=lambda: False,
            )
        )
        assert FeatureRegistry.is_available(FeatureName.SSO, org=object()) is False

    def test_provider_swap_changes_behaviour(self, clean_registry):
        FeatureRegistry.register(Feature(name=FeatureName.SSO, display_name="SSO"))
        org = object()

        FeatureRegistry.set_license_provider(_DenyingProvider())
        assert FeatureRegistry.is_available(FeatureName.SSO, org=org) is False

        FeatureRegistry.set_license_provider(_AllowingProvider())
        assert FeatureRegistry.is_available(FeatureName.SSO, org=org) is True


class TestEnabledFeatures:
    def test_lists_only_available_features(self, clean_registry):
        FeatureRegistry.register(Feature(name=FeatureName.SSO, display_name="SSO"))
        enabled = FeatureRegistry.enabled_features(org=object())
        assert [f.name for f in enabled] == [FeatureName.SSO]

    def test_excludes_features_with_failing_runtime_check(self, clean_registry):
        FeatureRegistry.register(
            Feature(
                name=FeatureName.SSO,
                display_name="SSO",
                runtime_check=lambda: False,
            )
        )
        assert FeatureRegistry.enabled_features(org=object()) == []


class TestReset:
    def test_clears_registry_and_provider(self, clean_registry):
        FeatureRegistry.register(Feature(name=FeatureName.SSO, display_name="SSO"))
        FeatureRegistry.set_license_provider(_DenyingProvider())
        FeatureRegistry.reset()

        assert FeatureRegistry.is_registered(FeatureName.SSO) is False
        assert FeatureRegistry.license_info() == {"edition": "community", "licensed": False}

    def test_license_info_forwards_org(self, clean_registry):
        """license_info(org=...) passes org through to the provider."""

        class _OrgCapture:
            received_org = None

            def allows_feature(self, feature, org):
                return True

            def info(self, org=None):
                _OrgCapture.received_org = org
                return {"edition": "test", "licensed": True}

        FeatureRegistry.set_license_provider(_OrgCapture())
        sentinel_org = object()
        FeatureRegistry.license_info(org=sentinel_org)
        assert _OrgCapture.received_org is sentinel_org


class TestDefaultLicenseProvider:
    def test_allows_non_rbac_features(self):
        provider = DefaultLicenseProvider()
        feature = Feature(name=FeatureName.SSO, display_name="SSO")
        assert provider.allows_feature(feature, org=object()) is True

    def test_allows_rbac_by_default(self):
        """RBAC is allowed by default now that the backfill migration seeds
        organization_member rows for every existing user, so enabling it does
        not lock anyone out (see DefaultLicenseProvider's docstring)."""
        provider = DefaultLicenseProvider()
        feature = Feature(name=FeatureName.RBAC, display_name="RBAC")
        assert provider.allows_feature(feature, org=object()) is True

    def test_info_marks_community_edition(self):
        """Community build has no EE license — edition is 'community'."""
        provider = DefaultLicenseProvider()
        assert provider.info() == {"edition": "community", "licensed": False}

    def test_info_accepts_org_kwarg(self):
        """info() accepts org= without error (org-aware interface)."""
        provider = DefaultLicenseProvider()
        org = object()
        assert provider.info(org=org) == {"edition": "community", "licensed": False}


class TestFeatureDataclass:
    def test_equality_is_by_name_only(self):
        """Display label and description must not influence equality.

        Two Feature instances with the same name but different metadata
        should compare equal so idempotent re-registration is well-defined.
        """
        a = Feature(name=FeatureName.SSO, display_name="A")
        b = Feature(name=FeatureName.SSO, display_name="B", description="different")
        assert a == b


class TestFeatureNameEnum:
    def test_str_equivalence(self):
        assert FeatureName.SSO == "sso"
        assert FeatureName.SSO.value == "sso"


class TestLicenseProviderProtocol:
    def test_default_conforms_to_protocol(self):
        provider: LicenseProvider = DefaultLicenseProvider()
        assert hasattr(provider, "allows_feature")
        assert hasattr(provider, "info")


ee_pkg = pytest.importorskip(
    "rhesis.backend.ee",
    reason="EE package not installed (community build); skipping EE bootstrap tests.",
)


class TestEEBootstrap:
    """SSO feature registration via the EE bootstrap."""

    def test_registers_sso(self, clean_registry):
        from unittest.mock import MagicMock

        mock_app = MagicMock()
        ee_pkg.bootstrap(mock_app)
        feature = FeatureRegistry._features.get(FeatureName.SSO)
        assert feature is not None
        assert feature.display_name == "Single Sign-On"
        assert feature.runtime_check is not None
        # The bootstrap mounts four routers today: SSO admin, API
        # Clients CRUD, the token-exchange endpoint, and the RBAC router.
        # Pin the count so a future addition is a deliberate test update
        # rather than silently growing the EE surface area.
        assert mock_app.include_router.call_count == 4

    def test_registers_api_clients(self, clean_registry):
        """API_CLIENTS feature is registered alongside SSO."""
        from unittest.mock import MagicMock

        mock_app = MagicMock()
        ee_pkg.bootstrap(mock_app)
        feature = FeatureRegistry._features.get(FeatureName.API_CLIENTS)
        assert feature is not None
        assert feature.display_name == "API Clients"
        assert feature.runtime_check is not None

    def test_registration_is_idempotent(self, clean_registry):
        from unittest.mock import MagicMock

        mock_app = MagicMock()
        ee_pkg.bootstrap(mock_app)
        ee_pkg.bootstrap(mock_app)
        # SSO + API_CLIENTS + RBAC; idempotency means re-running bootstrap
        # does not double the count.
        assert len(FeatureRegistry._features) == 3

    def test_route_class_inherits_from_app(self, clean_registry):
        """The EE router must adopt the app's authenticated route class.

        Without this, EE routes silently bypass the path-based public/token
        auth scheme used by core routers.
        """
        from unittest.mock import MagicMock

        sentinel_route_class = object()
        mock_app = MagicMock()
        mock_app.router.route_class = sentinel_route_class

        ee_pkg.bootstrap(mock_app)

        included = mock_app.include_router.call_args.args[0]
        assert included.route_class is sentinel_route_class
