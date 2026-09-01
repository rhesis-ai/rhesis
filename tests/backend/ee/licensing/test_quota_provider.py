"""Unit tests for :class:`~rhesis.backend.ee.licensing.quota_provider.ConfigQuotaProvider`.

Two things are under test here, and the second is the reason this file exists:

1. The tier baseline — an org's edition resolves to its ``tier_config.yaml`` limits.
2. The bespoke overlay — a license token's ``custom_limits`` claim overrides
   individual resources on top of that baseline. This is what backs the pricing
   page's "custom" enterprise limits, and it has to hold two properties that are
   easy to break: an override must not leak into resources it does not name, and
   the mint-time ``limits`` snapshot must never be treated as an override (which
   would pin every org to the numbers its token was minted with).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from rhesis.backend.app.features import FeatureRegistry
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.ee.licensing.entitlements import LicenseEdition
from rhesis.backend.ee.licensing.provider import SignedTokenLicenseProvider
from rhesis.backend.ee.licensing.quota_provider import ConfigQuotaProvider
from rhesis.backend.ee.licensing.tiers import resolve_limits, resolve_tier

pytestmark = pytest.mark.skipif(
    not pytest.importorskip(
        "rhesis.backend.ee",
        reason="EE package not installed",
    ),
    reason="EE package not installed",
)

_ORG_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

# Every resource the catalog meters, so a test can assert an override touched
# exactly one of them and left the rest alone.
_ALL_RESOURCES = tuple(QuotaResource)


def _make_org(license_token: str | None = None) -> MagicMock:
    org = MagicMock()
    org.id = UUID(_ORG_UUID)
    org.license = license_token
    return org


@pytest.fixture
def provider():
    return ConfigQuotaProvider()


@pytest.fixture
def licensed_registry():
    """Install the real EE license provider, so info() comes from a real token.

    The overlay is only meaningful end to end: the claim has to survive minting,
    signature verification, and the provider's ``info()`` before the quota
    provider ever sees it. Stubbing ``license_info`` would skip exactly the wiring
    this file is here to cover.
    """
    saved = FeatureRegistry._license
    FeatureRegistry.set_license_provider(SignedTokenLicenseProvider())
    yield
    FeatureRegistry._license = saved


def _policy_for(provider, mint_token, licensed_registry, **mint_kwargs):
    """Resolve a policy for an org holding a token minted with *mint_kwargs*."""
    token = mint_token(sub=_ORG_UUID, **mint_kwargs)
    org = _make_org(license_token=token)
    with patch.dict("os.environ", {"RHESIS_LICENSE": ""}):
        return provider.get_policy(org)


class TestTierBaseline:
    def test_unlicensed_org_gets_community_limits(self, provider):
        """No token at all -- the free tier, not unlimited."""
        org = _make_org(license_token=None)
        with patch.dict("os.environ", {"RHESIS_LICENSE": ""}):
            policy = provider.get_policy(org)
        assert policy.limits == resolve_limits(LicenseEdition.COMMUNITY)

    def test_no_org_gets_community_limits(self, provider):
        assert provider.get_policy(None).limits == resolve_limits(LicenseEdition.COMMUNITY)

    @pytest.mark.parametrize("edition", [LicenseEdition.TEAM, LicenseEdition.ENTERPRISE])
    def test_licensed_org_gets_its_tier(self, provider, mint_token, licensed_registry, edition):
        policy = _policy_for(provider, mint_token, licensed_registry, edition=edition.value)
        assert policy.limits == resolve_tier(edition).limits

    def test_enterprise_is_unlimited_without_an_override(
        self, provider, mint_token, licensed_registry
    ):
        """The default enterprise posture, and what every already-minted
        enterprise token keeps doing after this change."""
        policy = _policy_for(provider, mint_token, licensed_registry, edition="enterprise")
        assert all(policy.limits[r] is None for r in _ALL_RESOURCES)

    @pytest.mark.parametrize("status", ["canceled", "bogus-status"])
    def test_revoked_license_drops_to_community_limits(
        self, provider, mint_token, licensed_registry, status
    ):
        """Billing status has to actually end the paid allowance.

        ``info()`` still reports ``edition: enterprise`` for a revoked license so
        the UI can name what expired. Resolving limits from that name alone left
        a canceled enterprise org on unlimited quota indefinitely. An
        unrecognized status counts as revoked, matching ``ACTIVE_STATUSES``.
        """
        policy = _policy_for(
            provider,
            mint_token,
            licensed_registry,
            edition="enterprise",
            status=status,
        )
        assert policy.limits == resolve_limits(LicenseEdition.COMMUNITY)

    def test_past_due_keeps_its_tier(self, provider, mint_token, licensed_registry):
        """Deliberate, per ``ACTIVE_STATUSES``: a temporary payment problem must
        not cut a paying customer off mid-work. Only an explicit cancellation
        (or an unknown status) revokes the allowance."""
        policy = _policy_for(
            provider,
            mint_token,
            licensed_registry,
            edition="team",
            status="past_due",
        )
        assert policy.limits == resolve_tier(LicenseEdition.TEAM).limits


class TestCustomLimitOverlay:
    def test_override_caps_a_single_enterprise_resource(
        self, provider, mint_token, licensed_registry
    ):
        """The "custom" enterprise case: one negotiated cap, everything else
        still unlimited."""
        policy = _policy_for(
            provider,
            mint_token,
            licensed_registry,
            edition="enterprise",
            custom_limits={"test_executions": 500_000},
        )
        assert policy.limits[QuotaResource.TEST_EXECUTIONS] == 500_000
        others = [r for r in _ALL_RESOURCES if r is not QuotaResource.TEST_EXECUTIONS]
        assert all(policy.limits[r] is None for r in others)

    def test_override_can_raise_a_team_limit(self, provider, mint_token, licensed_registry):
        tier_seats = resolve_tier(LicenseEdition.TEAM).limits[QuotaResource.SEATS]
        policy = _policy_for(
            provider,
            mint_token,
            licensed_registry,
            edition="team",
            custom_limits={"test_executions": 5_000_000},
        )
        assert policy.limits[QuotaResource.TEST_EXECUTIONS] == 5_000_000
        # Untouched resources still track the published tier.
        assert policy.limits[QuotaResource.SEATS] == tier_seats
        assert (
            policy.limits[QuotaResource.TRACING_SPANS]
            == resolve_tier(LicenseEdition.TEAM).limits[QuotaResource.TRACING_SPANS]
        )

    def test_explicit_null_override_means_unlimited(self, provider, mint_token, licensed_registry):
        policy = _policy_for(
            provider,
            mint_token,
            licensed_registry,
            edition="team",
            custom_limits={"test_executions": None},
        )
        assert policy.limits[QuotaResource.TEST_EXECUTIONS] is None

    def test_override_preserves_the_tier_overage_policy(
        self, provider, mint_token, licensed_registry
    ):
        """A negotiated cap changes the ceiling, not whether there is a grace band."""
        tier = resolve_tier(LicenseEdition.TEAM)
        policy = _policy_for(
            provider,
            mint_token,
            licensed_registry,
            edition="team",
            custom_limits={"test_executions": 1_000},
        )
        assert policy.overage is tier.overage
        assert policy.overage_tolerance_percent == tier.overage_tolerance_percent

    def test_mint_time_limits_snapshot_is_never_an_override(
        self, provider, mint_token, licensed_registry
    ):
        """The regression this design exists to prevent.

        ``lic.limits`` is a snapshot of the tier as it stood at minting. If it
        were enforced, a token minted under older pricing would keep overriding
        the catalog forever, and every published limit change would silently
        miss existing customers. Here the token claims numbers unlike the live
        team tier; the live tier must win.
        """
        tier_limits = resolve_tier(LicenseEdition.TEAM).limits
        stale = {r.value: 42 for r in _ALL_RESOURCES}

        policy = _policy_for(
            provider,
            mint_token,
            licensed_registry,
            edition="team",
            limits=stale,
        )
        assert policy.limits == tier_limits
        assert 42 not in policy.limits.values()

    @pytest.mark.parametrize(
        "junk",
        [
            {"not_a_resource": 10},
            {"seats": "many"},
            {"seats": True},
            {"seats": -1},
            "not-a-mapping",
        ],
        ids=["unknown-key", "string", "bool", "negative", "non-mapping"],
    )
    def test_unreadable_override_falls_back_to_the_tier(
        self, provider, mint_token, licensed_registry, junk
    ):
        """A token is signed, not schema-checked, and is read on the request
        path -- so junk is dropped and the tier applies, rather than 500ing
        every request for that org."""
        policy = _policy_for(
            provider,
            mint_token,
            licensed_registry,
            edition="team",
            custom_limits=junk,
        )
        assert policy.limits == resolve_tier(LicenseEdition.TEAM).limits

    def test_override_is_ignored_for_an_inactive_license(
        self, provider, mint_token, licensed_registry
    ):
        """A canceled license falls back to community, and must not carry its
        bespoke enterprise allowances along with it."""
        policy = _policy_for(
            provider,
            mint_token,
            licensed_registry,
            edition="enterprise",
            status="canceled",
            custom_limits={"test_executions": 5_000_000},
        )
        assert policy.limits == resolve_limits(LicenseEdition.COMMUNITY)
