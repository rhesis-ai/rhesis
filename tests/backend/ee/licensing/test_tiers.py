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
    ENV_TIER_CONFIG,
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
    SELLABLE_EDITIONS,
    TierSpec,
    _assert_catalog_complete,
    _load_tier_config,
    all_sellable,
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
        """Every sellable edition has a catalog entry.

        Driven off all_sellable() rather than a literal list so adding a
        tier does not require editing this test -- the startup gate in
        _assert_catalog_complete() enforces the same invariant, and this
        confirms it holds for the real bundled config."""
        for edition in all_sellable():
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


class TestLoadTierConfig:
    """_load_tier_config() must degrade gracefully on malformed input --
    a bad entry should skip just that tier, never crash the whole loader
    or silently misparse into a wrong-but-valid-looking TierSpec."""

    def _load_from(self, tmp_path, monkeypatch, content: str) -> dict:
        config_file = tmp_path / "tier_config.yaml"
        config_file.write_text(content)
        monkeypatch.setenv(ENV_TIER_CONFIG, str(config_file))
        return _load_tier_config()

    def test_null_edition_value_is_skipped_not_crashed(self, tmp_path, monkeypatch):
        """`team:` with no value parses to None, not a dict."""
        catalog = self._load_from(
            tmp_path,
            monkeypatch,
            "community:\n  limits:\n    seats: 3\nteam: null\n",
        )
        assert LicenseEdition.COMMUNITY in catalog
        assert LicenseEdition.TEAM not in catalog

    def test_non_mapping_limits_is_skipped(self, tmp_path, monkeypatch):
        catalog = self._load_from(
            tmp_path,
            monkeypatch,
            "community:\n  limits:\n    seats: 3\nenterprise:\n  limits: not_a_mapping\n",
        )
        assert LicenseEdition.COMMUNITY in catalog
        assert LicenseEdition.ENTERPRISE not in catalog

    def test_non_list_features_is_skipped(self, tmp_path, monkeypatch):
        """A string `features` value would otherwise iterate per-character
        and silently resolve to an empty feature set instead of failing."""
        catalog = self._load_from(
            tmp_path,
            monkeypatch,
            "community:\n  limits:\n    seats: 3\n"
            "master:\n  features: not_a_list\n  limits:\n    seats: null\n",
        )
        assert LicenseEdition.COMMUNITY in catalog
        assert LicenseEdition.MASTER not in catalog

    def test_valid_entries_still_load_alongside_malformed_ones(self, tmp_path, monkeypatch):
        catalog = self._load_from(
            tmp_path,
            monkeypatch,
            "community:\n  limits:\n    seats: 3\n"
            "team: null\n"
            "enterprise:\n  all_features: true\n  limits:\n    seats: null\n",
        )
        assert set(catalog.keys()) == {LicenseEdition.COMMUNITY, LicenseEdition.ENTERPRISE}

    def test_undeclared_edition_key_raises(self, tmp_path, monkeypatch):
        """A config naming a tier that isn't in LicenseEdition must fail loud.

        LicenseEdition._missing_ coerces unrecognized values to UNKNOWN
        instead of raising, so a naive ``LicenseEdition(key)`` would bind
        the undeclared tier's limits onto the UNKNOWN sentinel -- and every
        org whose license carries an unrecognized edition resolves to
        UNKNOWN, so it would silently inherit those limits.
        """
        with pytest.raises(ValueError, match="pro"):
            self._load_from(
                tmp_path,
                monkeypatch,
                "community:\n  limits:\n    seats: 3\npro:\n  limits:\n    seats: 25\n",
            )

    def test_unknown_sentinel_cannot_be_configured(self, tmp_path, monkeypatch):
        """UNKNOWN is a decode-time sentinel, never a configurable tier."""
        with pytest.raises(ValueError, match="unknown"):
            self._load_from(
                tmp_path,
                monkeypatch,
                "community:\n  limits:\n    seats: 3\nunknown:\n  limits:\n    seats: 999\n",
            )


class TestCatalogCompleteness:
    """The enum and the tier config must agree; neither half ships alone."""

    def test_declared_edition_without_config_entry_raises(self):
        """A LicenseEdition member with no YAML entry fails at startup
        rather than late, with a KeyError, the first time someone mints it."""
        partial = {
            LicenseEdition.COMMUNITY: TierSpec(edition=LicenseEdition.COMMUNITY),
            LicenseEdition.TEAM: TierSpec(edition=LicenseEdition.TEAM),
        }
        with pytest.raises(RuntimeError, match="missing an entry"):
            _assert_catalog_complete(partial)

    def test_error_names_the_missing_editions(self):
        partial = {
            LicenseEdition.COMMUNITY: TierSpec(edition=LicenseEdition.COMMUNITY),
            LicenseEdition.TEAM: TierSpec(edition=LicenseEdition.TEAM),
        }
        with pytest.raises(RuntimeError) as exc_info:
            _assert_catalog_complete(partial)
        message = str(exc_info.value)
        for missing in SELLABLE_EDITIONS - {LicenseEdition.TEAM}:
            assert missing.value in message

    def test_community_only_fallback_is_exempt(self):
        """_fallback_catalog() is community-only by design; the gate must
        not turn a degraded-but-working config into a boot failure."""
        fallback = {LicenseEdition.COMMUNITY: TierSpec(edition=LicenseEdition.COMMUNITY)}
        _assert_catalog_complete(fallback)

    def test_real_bundled_config_is_complete(self):
        """The shipped tier_config.yaml satisfies the gate."""
        _assert_catalog_complete(EDITION_ENTITLEMENTS)
        assert all_sellable() <= set(EDITION_ENTITLEMENTS)


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
