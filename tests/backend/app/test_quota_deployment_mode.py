"""Tests for self-hosted deployment mode (USAGE_QUOTAS_ENABLED=false).

With quotas off, every resource is unlimited, nothing enforces, and
everything still counts. These tests use the ``quotas_disabled`` fixture
to opt out of the suite-wide quotas-enabled patch from conftest.py.
"""

from __future__ import annotations

import pytest

from rhesis.backend.app.quota import (
    QuotaPolicy,
    QuotaRegistry,
    QuotaResource,
    UNLIMITED_LIMITS,
)
from rhesis.backend.app.quota.enforcement import (
    QuotaExceededError,
    check_quota,
    enforce_quota,
)
from rhesis.backend.app.services.usage import increment_usage


class _FixedPolicyProvider:
    """Always returns a limited policy, to prove the flag overrides it."""

    def __init__(self, policy: QuotaPolicy):
        self._policy = policy

    def get_policy(self, org=None) -> QuotaPolicy:
        return self._policy


@pytest.fixture
def limited_registry(quotas_disabled):
    """Install a provider with tight limits, but quotas are off."""
    saved = QuotaRegistry._provider
    QuotaRegistry.set_quota_provider(
        _FixedPolicyProvider(
            QuotaPolicy(
                limits={
                    QuotaResource.TEST_EXECUTIONS: 10,
                    QuotaResource.MODEL_TOKENS: 100,
                    QuotaResource.TRACING_SPANS: 5,
                    QuotaResource.TEST_GENERATION: 5,
                    QuotaResource.SEATS: 1,
                    QuotaResource.PROJECTS: 1,
                    QuotaResource.ENDPOINTS: 1,
                }
            )
        )
    )
    yield
    QuotaRegistry._provider = saved


class TestGetPolicyWithQuotasOff:
    def test_returns_unlimited_for_all_resources(self, limited_registry):
        policy = QuotaRegistry.get_policy()
        for r in QuotaResource:
            assert policy.limits[r] is None, f"{r} should be unlimited"

    def test_keys_match_all_quota_resources(self, limited_registry):
        policy = QuotaRegistry.get_policy()
        assert set(policy.limits.keys()) == set(QuotaResource)


class TestCheckQuotaWithQuotasOff:
    def test_allows_usage_far_past_the_former_limit(
        self, test_db, test_org_id, limited_registry
    ):
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 1_000_000)

        verdict = check_quota(
            test_db, test_org_id, None, QuotaResource.TEST_EXECUTIONS
        )

        assert verdict.allowed is True
        assert verdict.limit is None

    def test_used_still_reflects_real_usage(
        self, test_db, test_org_id, limited_registry
    ):
        increment_usage(test_db, test_org_id, QuotaResource.MODEL_TOKENS, 42)

        verdict = check_quota(
            test_db, test_org_id, None, QuotaResource.MODEL_TOKENS
        )

        assert verdict.used == 42
        assert verdict.limit is None


class TestEnforceQuotaWithQuotasOff:
    def test_does_not_raise(self, test_db, test_org_id, limited_registry):
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 1_000_000)

        enforce_quota(test_db, test_org_id, None, QuotaResource.TEST_EXECUTIONS)


class TestUnlimitedLimitsConstant:
    def test_covers_all_resources(self):
        assert set(UNLIMITED_LIMITS.keys()) == set(QuotaResource)

    def test_all_values_are_none(self):
        assert all(v is None for v in UNLIMITED_LIMITS.values())
