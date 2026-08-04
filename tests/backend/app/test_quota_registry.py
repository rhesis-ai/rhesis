"""Unit tests for :mod:`rhesis.backend.app.quota`."""

from __future__ import annotations

import pytest

from rhesis.backend.app.quota import (
    FREE_TIER_LIMITS,
    DefaultQuotaProvider,
    QuotaProvider,
    QuotaRegistry,
    QuotaResource,
)


@pytest.fixture
def clean_registry():
    """Reset the registry before each test, restore the real state after.

    Mirrors the ``clean_registry`` fixture in ``test_feature_registry.py``:
    ``ee.bootstrap()`` installs the config-backed provider once at process
    import time, so a bare ``QuotaRegistry.reset()`` on teardown would leave
    the default provider installed for the rest of the suite.
    """
    saved_provider = QuotaRegistry._provider
    QuotaRegistry.reset()
    yield
    QuotaRegistry._provider = saved_provider


class _FixedProvider:
    """Provider returning a fixed limits dict, regardless of org."""

    def __init__(self, limits: dict[QuotaResource, int | None]):
        self._limits = limits

    def get_limits(self, org=None) -> dict[QuotaResource, int | None]:
        return dict(self._limits)


class TestDefaultQuotaProvider:
    def test_returns_free_tier_limits(self, clean_registry):
        assert QuotaRegistry.get_limits() == FREE_TIER_LIMITS

    def test_ignores_org(self, clean_registry):
        """The default provider has no org-awareness -- everyone gets the
        same free-tier numbers until an EE provider is installed."""
        assert QuotaRegistry.get_limits(org=object()) == FREE_TIER_LIMITS


class TestGetLimits:
    def test_delegates_to_installed_provider(self, clean_registry):
        custom = {QuotaResource.SEATS: 42}
        QuotaRegistry.set_quota_provider(_FixedProvider(custom))
        assert QuotaRegistry.get_limits() == custom


class TestGetLimit:
    def test_returns_limit_for_known_resource(self, clean_registry):
        assert QuotaRegistry.get_limit(None, QuotaResource.SEATS) == 3

    def test_accepts_raw_string_equivalent(self, clean_registry):
        """QuotaResourceLike accepts wire strings, mirroring FeatureName."""
        assert QuotaRegistry.get_limit(None, "seats") == 3

    def test_none_means_unlimited(self, clean_registry):
        QuotaRegistry.set_quota_provider(_FixedProvider({QuotaResource.SEATS: None}))
        assert QuotaRegistry.get_limit(None, QuotaResource.SEATS) is None

    def test_resource_absent_from_provider_returns_none(self, clean_registry):
        """Distinct from an unknown resource name: a resource the provider
        simply didn't set a limit for is treated as unlimited, same as an
        explicit ``None`` value."""
        QuotaRegistry.set_quota_provider(_FixedProvider({}))
        assert QuotaRegistry.get_limit(None, QuotaResource.SEATS) is None

    def test_unknown_resource_name_raises(self, clean_registry):
        """A typo'd resource name must fail loud, not silently return None
        (which would read as "unlimited") -- see QuotaRegistry._coerce."""
        with pytest.raises(ValueError):
            QuotaRegistry.get_limit(None, "not_a_real_resource")


class TestSetQuotaProvider:
    def test_installed_provider_takes_effect_immediately(self, clean_registry):
        assert QuotaRegistry.get_limits() == FREE_TIER_LIMITS
        QuotaRegistry.set_quota_provider(_FixedProvider({QuotaResource.SEATS: 100}))
        assert QuotaRegistry.get_limits() == {QuotaResource.SEATS: 100}


class TestReset:
    def test_reinstalls_default_provider(self, clean_registry):
        QuotaRegistry.set_quota_provider(_FixedProvider({QuotaResource.SEATS: 100}))
        QuotaRegistry.reset()
        assert isinstance(QuotaRegistry._provider, DefaultQuotaProvider)
        assert QuotaRegistry.get_limits() == FREE_TIER_LIMITS


class TestQuotaProviderProtocol:
    def test_default_provider_satisfies_protocol(self):
        provider: QuotaProvider = DefaultQuotaProvider()
        assert provider.get_limits() == FREE_TIER_LIMITS
