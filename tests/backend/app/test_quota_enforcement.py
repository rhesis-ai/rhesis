"""Tests for :mod:`rhesis.backend.app.quota.enforcement`.

The single blocking rule every enforcement point shares -- see the module's
own docstring. Flow-resource tests use the real `usage` table via `test_db`
(Postgres-backed, SAVEPOINT-isolated); stock-resource tests create Project
rows directly, mirroring `tests/backend/services/test_usage.py`.
"""

from __future__ import annotations

import pytest

from rhesis.backend.app.models.project import Project
from rhesis.backend.app.quota import OveragePolicy, QuotaPolicy, QuotaRegistry, QuotaResource
from rhesis.backend.app.quota.enforcement import (
    BACKSTOP_MULTIPLIER,
    QuotaExceededError,
    check_backstop,
    check_quota,
    enforce_quota,
    quota_exceeded_response_body,
)
from rhesis.backend.app.services.usage import increment_usage


class _FixedPolicyProvider:
    """Installs one fixed `QuotaPolicy` regardless of org, for deterministic
    boundary testing -- the real EE provider resolves this from YAML, which
    is exercised separately in `tests/backend/ee/licensing/test_tiers.py`."""

    def __init__(self, policy: QuotaPolicy):
        self._policy = policy

    def get_policy(self, org=None) -> QuotaPolicy:
        return self._policy


@pytest.fixture
def clean_registry():
    """Reset the registry before and after, mirroring test_quota_registry.py."""
    saved_provider = QuotaRegistry._provider
    QuotaRegistry.reset()
    yield
    QuotaRegistry._provider = saved_provider


def _install(policy: QuotaPolicy) -> None:
    QuotaRegistry.set_quota_provider(_FixedPolicyProvider(policy))


class TestCheckQuotaUnlimited:
    def test_none_limit_is_always_allowed(self, test_db, test_org_id, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: None}))
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 1_000_000)

        verdict = check_quota(test_db, test_org_id, None, QuotaResource.TEST_EXECUTIONS)

        assert verdict.allowed is True
        assert verdict.over_limit is False
        assert verdict.limit is None

    def test_resource_absent_from_policy_is_unlimited(self, test_db, test_org_id, clean_registry):
        """A resource the policy simply doesn't mention is unlimited, same
        as an explicit `None` -- `QuotaPolicy.limits.get()` returns `None`
        either way."""
        _install(QuotaPolicy(limits={}))

        verdict = check_quota(test_db, test_org_id, None, QuotaResource.TEST_EXECUTIONS)

        assert verdict.allowed is True
        assert verdict.limit is None


class TestCheckQuotaHard:
    def test_below_limit_is_allowed(self, test_db, test_org_id, clean_registry):
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 10}, overage=OveragePolicy.HARD)
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 9)

        verdict = check_quota(test_db, test_org_id, None, QuotaResource.TEST_EXECUTIONS)

        assert verdict.allowed is True
        assert verdict.over_limit is False

    def test_at_limit_is_blocked(self, test_db, test_org_id, clean_registry):
        """HARD's ceiling is the limit itself -- see `QuotaPolicy.ceiling_for`."""
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 10}, overage=OveragePolicy.HARD)
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 10)

        verdict = check_quota(test_db, test_org_id, None, QuotaResource.TEST_EXECUTIONS)

        assert verdict.allowed is False
        assert verdict.over_limit is True

    def test_zero_tolerance_soft_behaves_like_hard(self, test_db, test_org_id, clean_registry):
        """SOFT with `overage_tolerance_percent=0` collapses to the same
        ceiling as HARD -- one expression, no branch at the call site."""
        _install(
            QuotaPolicy(
                limits={QuotaResource.TEST_EXECUTIONS: 10},
                overage=OveragePolicy.SOFT,
                overage_tolerance_percent=0,
            )
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 10)

        verdict = check_quota(test_db, test_org_id, None, QuotaResource.TEST_EXECUTIONS)

        assert verdict.allowed is False


class TestCheckQuotaSoftBoundary:
    """The 25% grace band. Ceiling = limit * 125 // 100 = 125 for limit=100.

    Off-by-one here is the difference between a 25% grace and a 25%-plus-one
    grace, so the ceiling-1 / ceiling boundary gets its own explicit test.
    """

    def _install_soft_100(self):
        _install(
            QuotaPolicy(
                limits={QuotaResource.TEST_EXECUTIONS: 100},
                overage=OveragePolicy.SOFT,
                overage_tolerance_percent=25,
            )
        )

    def test_below_limit_is_allowed_not_over_limit(self, test_db, test_org_id, clean_registry):
        self._install_soft_100()
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 99)

        verdict = check_quota(test_db, test_org_id, None, QuotaResource.TEST_EXECUTIONS)

        assert verdict.allowed is True
        assert verdict.over_limit is False

    def test_at_limit_is_allowed_and_over_limit(self, test_db, test_org_id, clean_registry):
        """Past the advertised limit but still inside the grace band: allowed,
        but `over_limit` so a caller can surface a warning."""
        self._install_soft_100()
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 100)

        verdict = check_quota(test_db, test_org_id, None, QuotaResource.TEST_EXECUTIONS)

        assert verdict.allowed is True
        assert verdict.over_limit is True

    def test_one_below_ceiling_is_allowed(self, test_db, test_org_id, clean_registry):
        self._install_soft_100()
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 124)

        verdict = check_quota(test_db, test_org_id, None, QuotaResource.TEST_EXECUTIONS)

        assert verdict.allowed is True
        assert verdict.over_limit is True

    def test_at_ceiling_is_blocked(self, test_db, test_org_id, clean_registry):
        self._install_soft_100()
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 125)

        verdict = check_quota(test_db, test_org_id, None, QuotaResource.TEST_EXECUTIONS)

        assert verdict.allowed is False
        assert verdict.over_limit is True


class TestCheckQuotaStockResources:
    """Stock resources are a live `COUNT(*)`, not an accrued counter --
    no accrual lag, so there is no separate warning-band concern to test
    beyond the same boundary rule already covered for flow resources."""

    def test_reads_a_live_project_count(self, test_db, test_org_id, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.PROJECTS: 1}, overage=OveragePolicy.HARD))
        test_db.add(Project(name="quota-enforcement-test-project", organization_id=test_org_id))
        test_db.commit()

        verdict = check_quota(test_db, test_org_id, None, QuotaResource.PROJECTS)

        assert verdict.used >= 1
        assert verdict.allowed is False

    def test_under_the_stock_limit_is_allowed(self, test_db, test_org_id, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.PROJECTS: 100}, overage=OveragePolicy.HARD))

        verdict = check_quota(test_db, test_org_id, None, QuotaResource.PROJECTS)

        assert verdict.allowed is True


class TestEnforceQuota:
    def test_returns_the_verdict_when_allowed(self, test_db, test_org_id, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 10}))

        verdict = enforce_quota(test_db, test_org_id, None, QuotaResource.TEST_EXECUTIONS)

        assert verdict.allowed is True

    def test_raises_when_blocked(self, test_db, test_org_id, clean_registry):
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 10}, overage=OveragePolicy.HARD)
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 10)

        with pytest.raises(QuotaExceededError) as exc_info:
            enforce_quota(test_db, test_org_id, None, QuotaResource.TEST_EXECUTIONS)

        assert exc_info.value.verdict.resource is QuotaResource.TEST_EXECUTIONS
        assert exc_info.value.verdict.allowed is False


class TestQuotaExceededResponseBody:
    def test_shape_matches_the_shared_402_contract(self, test_db, test_org_id, clean_registry):
        _install(
            QuotaPolicy(limits={QuotaResource.TEST_EXECUTIONS: 10}, overage=OveragePolicy.HARD)
        )
        increment_usage(test_db, test_org_id, QuotaResource.TEST_EXECUTIONS, 10)
        verdict = check_quota(test_db, test_org_id, None, QuotaResource.TEST_EXECUTIONS)

        body = quota_exceeded_response_body(verdict)

        assert body["error"] == "quota_exceeded"
        assert body["resource"] == QuotaResource.TEST_EXECUTIONS.value
        assert body["used"] == 10
        assert body["limit"] == 10
        assert body["kind"] == "flow"
        assert body["period_end"] == verdict.period_end
        assert "test runs" in body["message"]


class TestCheckBackstopUnlimited:
    """An unlimited tier (limit is None) is never backstopped."""

    def test_unlimited_is_always_allowed(self, test_db, test_org_id, clean_registry):
        _install(QuotaPolicy(limits={QuotaResource.TRACING_SPANS: None}))
        increment_usage(test_db, test_org_id, QuotaResource.TRACING_SPANS, 999_999_999)

        verdict = check_backstop(test_db, test_org_id, None, QuotaResource.TRACING_SPANS)

        assert verdict.allowed is True
        assert verdict.limit is None


class TestCheckBackstopBoundary:
    """The backstop fires at BACKSTOP_MULTIPLIER x the tier limit (10x by default).

    With a limit of 100, the backstop ceiling is 1,000. Off-by-one matters:
    999 is allowed, 1,000 is blocked.
    """

    def _install_100(self):
        _install(QuotaPolicy(limits={QuotaResource.TRACING_SPANS: 100}))

    def test_below_backstop_is_allowed(self, test_db, test_org_id, clean_registry):
        self._install_100()
        increment_usage(test_db, test_org_id, QuotaResource.TRACING_SPANS, 999)

        verdict = check_backstop(test_db, test_org_id, None, QuotaResource.TRACING_SPANS)

        assert verdict.allowed is True

    def test_at_backstop_is_blocked(self, test_db, test_org_id, clean_registry):
        self._install_100()
        backstop = 100 * BACKSTOP_MULTIPLIER
        increment_usage(test_db, test_org_id, QuotaResource.TRACING_SPANS, backstop)

        verdict = check_backstop(test_db, test_org_id, None, QuotaResource.TRACING_SPANS)

        assert verdict.allowed is False
        assert verdict.limit == backstop

    def test_above_the_tier_limit_but_below_backstop_is_allowed(
        self, test_db, test_org_id, clean_registry
    ):
        """The backstop is not normal enforcement. Usage past the tier limit
        but below 10x is allowed -- the published limit is enforced by
        notifications and retention, not rejection."""
        self._install_100()
        increment_usage(test_db, test_org_id, QuotaResource.TRACING_SPANS, 500)

        verdict = check_backstop(test_db, test_org_id, None, QuotaResource.TRACING_SPANS)

        assert verdict.allowed is True
        assert verdict.over_limit is True

    def test_verdict_limit_is_the_backstop_ceiling_not_the_tier_limit(
        self, test_db, test_org_id, clean_registry
    ):
        """The verdict.limit field carries the backstop ceiling so a 402 body
        built from it shows the actual threshold that was crossed, not the
        published tier limit the org passed long ago."""
        self._install_100()
        backstop = 100 * BACKSTOP_MULTIPLIER
        increment_usage(test_db, test_org_id, QuotaResource.TRACING_SPANS, backstop)

        verdict = check_backstop(test_db, test_org_id, None, QuotaResource.TRACING_SPANS)

        assert verdict.limit == backstop
