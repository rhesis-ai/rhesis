"""Tests for the tier catalog :mod:`rhesis.backend.ee.licensing.tiers`.

These lock in the "single source of truth + token-authoritative" contract:
the catalog defines what each tier includes, and a token minted from a tier
verifies to entitlements that grant exactly those features.
"""

from __future__ import annotations

import pytest

from rhesis.backend.app.features import FeatureName
from rhesis.backend.app.quota import FREE_TIER_LIMITS, QuotaResource
from rhesis.backend.ee.licensing.entitlements import (
    LIC_ALL_FEATURES,
    LIC_EDITION,
    LIC_FEATURES,
    LIC_LIMITS,
    LIC_STATUS,
    LicenseEdition,
    LicenseStatus,
)
from rhesis.backend.ee.licensing.tiers import (
    EDITION_ENTITLEMENTS,
    TierSpec,
    is_sellable,
    resolve_limits,
    resolve_tier,
    tier_to_lic_claim,
)
from rhesis.backend.ee.licensing.verify import verify_token

pytestmark = pytest.mark.skipif(
    not pytest.importorskip(
        "rhesis.backend.ee",
        reason="EE package not installed",
    ),
    reason="EE package not installed",
)


class TestCatalogShape:
    def test_every_catalog_entry_is_self_consistent(self):
        """Each spec's edition key matches the spec's edition field."""
        for edition, spec in EDITION_ENTITLEMENTS.items():
            assert spec.edition is edition
            assert isinstance(spec, TierSpec)

    def test_non_sellable_editions_absent(self):
        """COMMUNITY and UNKNOWN are never mintable, even though COMMUNITY
        has a catalog entry (needed for limits lookups on unlicensed orgs)."""
        for edition in (LicenseEdition.COMMUNITY, LicenseEdition.UNKNOWN):
            assert not is_sellable(edition)
            with pytest.raises(KeyError):
                resolve_tier(edition)

    def test_sellable_editions_present(self):
        for edition in (
            LicenseEdition.TEAM,
            LicenseEdition.ENTERPRISE,
            LicenseEdition.MASTER,
        ):
            assert is_sellable(edition)

    def test_community_entry_exists_for_limits_lookup(self):
        """COMMUNITY is in the catalog (for resolve_limits) despite being non-sellable."""
        assert LicenseEdition.COMMUNITY in EDITION_ENTITLEMENTS

    def test_community_limits_match_core_free_tier_defaults(self):
        """The YAML's community entry must stay in sync with core's
        FREE_TIER_LIMITS -- the two are duplicated by necessity (core can't
        import EE), so drift between them would only show up here."""
        assert resolve_limits(LicenseEdition.COMMUNITY) == FREE_TIER_LIMITS

    def test_limit_keys_are_quota_resources(self):
        """All limit keys in every tier spec are QuotaResource members."""
        for edition, spec in EDITION_ENTITLEMENTS.items():
            for key in spec.limits:
                assert isinstance(key, QuotaResource), (
                    f"Limit key {key!r} in {edition} is not a QuotaResource"
                )


class TestTierToLicClaim:
    def test_team_claim_lists_rbac(self):
        claim = tier_to_lic_claim(LicenseEdition.TEAM)
        assert claim[LIC_EDITION] == "team"
        assert claim[LIC_STATUS] == "active"
        assert claim[LIC_ALL_FEATURES] is False
        assert claim[LIC_FEATURES] == [FeatureName.RBAC.value]

    def test_team_claim_has_quota_limits(self):
        claim = tier_to_lic_claim(LicenseEdition.TEAM)
        limits = claim[LIC_LIMITS]
        assert limits[str(QuotaResource.TEST_EXECUTIONS)] == 100_000
        assert limits[str(QuotaResource.SEATS)] is None

    def test_enterprise_claim_is_all_features(self):
        claim = tier_to_lic_claim(LicenseEdition.ENTERPRISE)
        assert claim[LIC_ALL_FEATURES] is True

    def test_status_override(self):
        claim = tier_to_lic_claim(LicenseEdition.TEAM, status=LicenseStatus.PAST_DUE)
        assert claim[LIC_STATUS] == "past_due"


class TestMintVerifyRoundTrip:
    """Mint a token from a tier spec and confirm it verifies to entitlements
    that grant exactly the catalog's features."""

    def _mint_from_tier(self, mint_token, edition):
        claim = tier_to_lic_claim(edition)
        return mint_token(
            sub="*",
            edition=claim[LIC_EDITION],
            status=claim[LIC_STATUS],
            all_features=claim[LIC_ALL_FEATURES],
            features=claim[LIC_FEATURES],
            limits=claim[LIC_LIMITS],
        )

    def test_team_grants_rbac(self, mint_token):
        token = self._mint_from_tier(mint_token, LicenseEdition.TEAM)
        ent = verify_token(token)
        assert ent is not None
        assert ent.edition is LicenseEdition.TEAM
        assert ent.allows(FeatureName.RBAC.value) is True
        assert ent.allows(FeatureName.SSO.value) is False

    def test_enterprise_grants_everything(self, mint_token):
        token = self._mint_from_tier(mint_token, LicenseEdition.ENTERPRISE)
        ent = verify_token(token)
        assert ent is not None
        assert ent.all_features is True
        assert ent.allows("some_future_feature") is True
