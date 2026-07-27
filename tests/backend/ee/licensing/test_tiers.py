"""Tests for the tier catalog :mod:`rhesis.backend.ee.licensing.tiers`.

These lock in the "single source of truth + token-authoritative" contract:
the catalog defines what each tier includes, and a token minted from a tier
verifies to entitlements that grant exactly those features.
"""

from __future__ import annotations

import pytest

from rhesis.backend.app.features import FeatureName
from rhesis.backend.ee.licensing.entitlements import (
    LIC_ALL_FEATURES,
    LIC_EDITION,
    LIC_FEATURES,
    LIC_LIMITS,
    LIC_STATUS,
    LIMIT_SEATS,
    LicenseEdition,
    LicenseStatus,
)
from rhesis.backend.ee.licensing.tiers import (
    EDITION_ENTITLEMENTS,
    TierSpec,
    is_sellable,
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
        for edition in (
            LicenseEdition.COMMUNITY,
            LicenseEdition.UNKNOWN,
        ):
            assert not is_sellable(edition)
            with pytest.raises(KeyError):
                resolve_tier(edition)

    def test_sellable_editions_present(self):
        for edition in (
            LicenseEdition.STARTER,
            LicenseEdition.PREMIUM,
            LicenseEdition.ENTERPRISE,
            LicenseEdition.MASTER,
            LicenseEdition.TRIAL,
        ):
            assert is_sellable(edition)


class TestTierToLicClaim:
    def test_starter_claim_lists_only_sso(self):
        claim = tier_to_lic_claim(LicenseEdition.STARTER)
        assert claim[LIC_EDITION] == "starter"
        assert claim[LIC_STATUS] == "active"
        assert claim[LIC_ALL_FEATURES] is False
        assert claim[LIC_FEATURES] == [FeatureName.SSO.value]
        assert claim[LIC_LIMITS] == {LIMIT_SEATS: 5}

    def test_premium_claim_lists_both_features(self):
        claim = tier_to_lic_claim(LicenseEdition.PREMIUM)
        assert set(claim[LIC_FEATURES]) == {
            FeatureName.SSO.value,
            FeatureName.API_CLIENTS.value,
        }
        assert claim[LIC_ALL_FEATURES] is False

    def test_enterprise_claim_is_all_features(self):
        claim = tier_to_lic_claim(LicenseEdition.ENTERPRISE)
        assert claim[LIC_ALL_FEATURES] is True

    def test_status_override(self):
        claim = tier_to_lic_claim(LicenseEdition.PREMIUM, status=LicenseStatus.PAST_DUE)
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

    def test_starter_grants_sso_only(self, mint_token):
        token = self._mint_from_tier(mint_token, LicenseEdition.STARTER)
        ent = verify_token(token)
        assert ent is not None
        assert ent.edition is LicenseEdition.STARTER
        assert ent.allows(FeatureName.SSO.value) is True
        assert ent.allows(FeatureName.API_CLIENTS.value) is False
        assert ent.limits == {LIMIT_SEATS: 5}

    def test_premium_grants_both(self, mint_token):
        token = self._mint_from_tier(mint_token, LicenseEdition.PREMIUM)
        ent = verify_token(token)
        assert ent is not None
        assert ent.allows(FeatureName.SSO.value) is True
        assert ent.allows(FeatureName.API_CLIENTS.value) is True

    def test_enterprise_grants_everything(self, mint_token):
        token = self._mint_from_tier(mint_token, LicenseEdition.ENTERPRISE)
        ent = verify_token(token)
        assert ent is not None
        assert ent.all_features is True
        # all_features short-circuits allows() for any feature, including ones
        # not yet registered — future-proof against new EE features.
        assert ent.allows("some_future_feature") is True
