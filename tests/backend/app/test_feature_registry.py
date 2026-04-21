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
from rhesis.backend.app.features_bootstrap import register_core_features
from rhesis.backend.app.models.subscription import SubscriptionPlan


@pytest.fixture
def clean_registry():
    """Reset the registry before and after each test for isolation."""
    FeatureRegistry.reset()
    yield
    FeatureRegistry.reset()
    register_core_features()  # restore session-wide default


class _DenyingProvider:
    def allows_feature(self, feature, org):  # noqa: D401 - stub
        return False

    def info(self):
        return {"edition": "enterprise", "licensed": True}


class _AllowingProvider:
    def allows_feature(self, feature, org):  # noqa: D401 - stub
        return True

    def info(self):
        return {"edition": "enterprise", "licensed": True}


class TestFeatureRegistry:
    def test_is_available_returns_false_for_unknown_feature(self, clean_registry):
        assert FeatureRegistry.is_available("nonsense", org=None) is False

    def test_is_available_returns_false_for_unregistered_enum_member(self, clean_registry):
        assert FeatureRegistry.is_available(FeatureName.SSO, org=None) is False

    def test_is_available_returns_true_when_registered_and_allowed(self, clean_registry):
        FeatureRegistry.register(
            Feature(name=FeatureName.SSO, display_name="SSO")
        )
        assert FeatureRegistry.is_available(FeatureName.SSO, org=None) is True

    def test_is_available_accepts_raw_string_equivalent(self, clean_registry):
        FeatureRegistry.register(
            Feature(name=FeatureName.SSO, display_name="SSO")
        )
        assert FeatureRegistry.is_available("sso", org=None) is True

    def test_is_available_honours_license_provider_denial(self, clean_registry):
        FeatureRegistry.register(
            Feature(name=FeatureName.SSO, display_name="SSO")
        )
        org = object()  # sentinel; DefaultLicenseProvider ignores it
        FeatureRegistry.set_license_provider(_DenyingProvider())
        assert FeatureRegistry.is_available(FeatureName.SSO, org=org) is False

    def test_license_check_skipped_when_org_is_none(self, clean_registry):
        FeatureRegistry.register(
            Feature(name=FeatureName.SSO, display_name="SSO")
        )
        FeatureRegistry.set_license_provider(_DenyingProvider())
        assert FeatureRegistry.is_available(FeatureName.SSO, org=None) is True

    def test_is_available_honours_runtime_check_failure(self, clean_registry):
        FeatureRegistry.register(
            Feature(
                name=FeatureName.SSO,
                display_name="SSO",
                runtime_check=lambda: False,
            )
        )
        assert FeatureRegistry.is_available(FeatureName.SSO, org=None) is False

    def test_set_license_provider_swap_changes_behaviour(self, clean_registry):
        FeatureRegistry.register(
            Feature(name=FeatureName.SSO, display_name="SSO", min_plan=SubscriptionPlan.PREMIUM)
        )
        org = object()

        FeatureRegistry.set_license_provider(_DenyingProvider())
        assert FeatureRegistry.is_available(FeatureName.SSO, org=org) is False

        FeatureRegistry.set_license_provider(_AllowingProvider())
        assert FeatureRegistry.is_available(FeatureName.SSO, org=org) is True

    def test_enabled_features_filters_by_is_available(self, clean_registry):
        FeatureRegistry.register(
            Feature(name=FeatureName.SSO, display_name="SSO")
        )
        enabled = FeatureRegistry.enabled_features(org=None)
        assert [f.name for f in enabled] == [FeatureName.SSO]

    def test_enabled_features_empty_when_runtime_check_fails(self, clean_registry):
        FeatureRegistry.register(
            Feature(
                name=FeatureName.SSO,
                display_name="SSO",
                runtime_check=lambda: False,
            )
        )
        assert FeatureRegistry.enabled_features(org=None) == []

    def test_reset_clears_registry_and_provider(self, clean_registry):
        FeatureRegistry.register(
            Feature(name=FeatureName.SSO, display_name="SSO")
        )
        FeatureRegistry.set_license_provider(_DenyingProvider())
        FeatureRegistry.reset()

        assert FeatureRegistry.is_available(FeatureName.SSO, org=None) is False
        assert FeatureRegistry.license_info() == {"edition": "community", "licensed": False}

    def test_license_info_reflects_current_provider(self, clean_registry):
        FeatureRegistry.set_license_provider(_AllowingProvider())
        assert FeatureRegistry.license_info() == {
            "edition": "enterprise",
            "licensed": True,
        }


class TestDefaultLicenseProvider:
    def test_allows_every_feature(self):
        provider = DefaultLicenseProvider()
        feature = Feature(name=FeatureName.SSO, display_name="SSO")
        assert provider.allows_feature(feature, org=object()) is True

    def test_info_marks_community_edition(self):
        provider = DefaultLicenseProvider()
        assert provider.info() == {"edition": "community", "licensed": False}


class TestFeatureNameEnum:
    def test_str_equivalence(self):
        assert FeatureName.SSO == "sso"
        assert FeatureName.SSO.value == "sso"

    def test_serialisable_as_string(self):
        # str-Enum members act as strings for JSON-compatible contexts.
        assert str(FeatureName.SSO.value) == "sso"


class TestLicenseProviderProtocol:
    def test_default_conforms_to_protocol(self):
        provider: LicenseProvider = DefaultLicenseProvider()
        assert hasattr(provider, "allows_feature")
        assert hasattr(provider, "info")


class TestRegisterCoreFeatures:
    def test_registers_sso(self, clean_registry):
        register_core_features()
        feature = FeatureRegistry._features.get(FeatureName.SSO)
        assert feature is not None
        assert feature.display_name == "Single Sign-On"
        assert feature.min_plan == SubscriptionPlan.PREMIUM
        assert feature.runtime_check is not None

    def test_registration_is_idempotent(self, clean_registry):
        register_core_features()
        register_core_features()
        assert len(FeatureRegistry._features) == 1
