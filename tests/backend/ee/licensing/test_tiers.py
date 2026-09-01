"""Tests for the tier catalog :mod:`rhesis.backend.ee.licensing.tiers`.

These lock in the "single source of truth + token-authoritative" contract:
the catalog defines what each tier includes, and a token minted from a tier
verifies to entitlements that grant exactly those features.
"""

from __future__ import annotations

import pytest
import yaml

from rhesis.backend.app.features import FeatureName
from rhesis.backend.app.quota import (
    FREE_TIER_LIMITS,
    OveragePolicy,
    QuotaPolicy,
    QuotaResource,
    limits_to_wire,
)
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
    _BUNDLED_CONFIG,
    EDITION_ENTITLEMENTS,
    SELLABLE_EDITIONS,
    TierSpec,
    _assert_catalog_complete,
    _fallback_catalog,
    _load_tier_config,
    all_sellable,
    is_sellable,
    resolve_policy,
    resolve_tier,
    tier_to_lic_claim,
)
from rhesis.backend.ee.licensing.verify import verify_token


@pytest.fixture
def bundled_catalog(monkeypatch):
    """Reload the catalog from the bundled YAML, ignoring any ambient override.

    Tests that assert the *shipped* tier numbers must not read whatever
    ``RHESIS_TIER_CONFIG`` happens to point at. That variable is a documented
    local workflow (``tier_config.dev.yaml`` sets deliberately tiny limits for
    exercising enforcement by hand) and the app calls ``load_dotenv``, so
    putting it in ``apps/backend/.env`` -- the natural way to switch it on --
    otherwise fails these tests with numbers that are correct for the config
    actually loaded.
    """
    monkeypatch.setenv(ENV_TIER_CONFIG, str(_BUNDLED_CONFIG))
    return _load_tier_config()


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

    def test_community_limits_match_core_free_tier_defaults(self, bundled_catalog):
        """The YAML's community entry must stay in sync with core's
        FREE_TIER_LIMITS -- the two are duplicated by necessity (core can't
        import EE), so drift between them would only show up here."""
        assert bundled_catalog[LicenseEdition.COMMUNITY].limits == FREE_TIER_LIMITS

    def test_published_limits_match_the_pricing_page(self, bundled_catalog):
        """These numbers are advertised publicly, so they are a promise, not a default.

        Pinned as literals here and again in the website repo
        (``src/data/pricing.test.ts``), deliberately duplicated across the two
        repos because neither build can see the other. The pricing page presents
        them as terms of service: a number published there but not enforced here
        is a promise we break, and a lower number enforced here than published
        there blocks a customer at a ceiling they were never told about.

        Change these together with ``src/data/pricing.ts`` -> ``PLAN_LIMITS``,
        or not at all.
        """
        assert bundled_catalog[LicenseEdition.COMMUNITY].limits == {
            QuotaResource.TEST_EXECUTIONS: 500,
            QuotaResource.TRACING_SPANS: 50_000,
            QuotaResource.TEST_GENERATION: 100,
            QuotaResource.MODEL_TOKENS: 1_000_000,
            QuotaResource.SEATS: 3,
            QuotaResource.PROJECTS: 3,
            QuotaResource.ENDPOINTS: 3,
        }
        assert bundled_catalog[LicenseEdition.COMMUNITY].retention_days == 14

        assert bundled_catalog[LicenseEdition.TEAM].limits == {
            QuotaResource.TEST_EXECUTIONS: 100_000,
            QuotaResource.TRACING_SPANS: 1_000_000,
            QuotaResource.TEST_GENERATION: 50_000,
            QuotaResource.MODEL_TOKENS: 25_000_000,
            QuotaResource.SEATS: None,
            QuotaResource.PROJECTS: None,
            QuotaResource.ENDPOINTS: None,
        }
        assert bundled_catalog[LicenseEdition.TEAM].retention_days == 90

    def test_enterprise_publishes_custom_via_unlimited_defaults(self, bundled_catalog):
        """The page says "custom" for enterprise, which is the absence of a
        catalog number, not a number of its own.

        A negotiated cap is minted per-org into the token's ``custom_limits``
        claim and overlaid on this tier (see ``quota_provider.py``). Putting a
        finite default here instead would silently cap every enterprise customer
        at whatever one contract happened to negotiate.
        """
        limits = bundled_catalog[LicenseEdition.ENTERPRISE].limits
        assert set(limits) == set(QuotaResource)
        assert all(value is None for value in limits.values())

    def test_no_tier_advertises_less_than_the_free_tier(self, bundled_catalog):
        """Team must never get a smaller allowance than community. Mirrors the
        website's own "never advertises a smaller allowance on a bigger plan"
        check, so an edit that inverts two tiers fails on this side too."""
        free = bundled_catalog[LicenseEdition.COMMUNITY].limits
        team = bundled_catalog[LicenseEdition.TEAM].limits
        for resource in QuotaResource:
            free_limit, team_limit = free[resource], team[resource]
            if team_limit is None:
                continue  # unlimited beats any finite free-tier number
            assert free_limit is not None, (
                f"{resource.value}: free is unlimited but team is capped at {team_limit}"
            )
            assert team_limit > free_limit, (
                f"{resource.value}: team ({team_limit}) must exceed free ({free_limit})"
            )

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
        """Parse *content* as a tier config, filling any `limits` mapping
        out to full QuotaResource coverage (defaulting to null/unlimited)
        before writing it.

        `_parse_limits` now requires every QuotaResource to have an explicit
        entry (see its docstring). Most tests in this class are about some
        other behavior -- a malformed shape, an unknown edition, an overage
        value -- and write a minimal `limits: {seats: 3}` block that would
        otherwise fail that unrelated coverage check for a reason the test
        isn't exercising. Backfilling here keeps those fixtures minimal
        without any test asserting on QuotaResource coverage by accident.
        """
        parsed = yaml.safe_load(content) or {}
        for spec in parsed.values():
            if isinstance(spec, dict) and isinstance(spec.get("limits"), dict):
                for resource in QuotaResource:
                    spec["limits"].setdefault(resource.value, None)

        config_file = tmp_path / "tier_config.yaml"
        config_file.write_text(yaml.safe_dump(parsed))
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

    @pytest.mark.parametrize(
        "value,description",
        [
            ('"100"', "string"),
            ("-1", "negative"),
            ("true", "bool"),
            ("1.5", "float"),
            ("[]", "list"),
        ],
    )
    def test_invalid_limit_values_are_rejected(self, tmp_path, monkeypatch, value, description):
        """yaml.safe_load accepts these happily, but none is a usable quota.

        A string limit raises TypeError the first time enforcement compares
        `used >= limit`, `true` silently means a limit of 1 (bool is an int
        subclass), and a negative limit blocks every request. They also flow
        into the JWT lic.limits claim and the /features response.
        """
        with pytest.raises(ValueError, match="[Ii]nvalid limit"):
            self._load_from(
                tmp_path,
                monkeypatch,
                f"community:\n  limits:\n    seats: {value}\n",
            )

    def test_zero_and_null_limits_are_valid(self, tmp_path, monkeypatch):
        """0 is a legitimate limit (nothing allowed); null means unlimited."""
        catalog = self._load_from(
            tmp_path,
            monkeypatch,
            "community:\n  limits:\n    seats: 0\n    projects: null\n",
        )
        limits = catalog[LicenseEdition.COMMUNITY].limits
        assert limits[QuotaResource.SEATS] == 0
        assert limits[QuotaResource.PROJECTS] is None

    def test_limits_missing_a_resource_raises(self, tmp_path, monkeypatch):
        """A `limits` block that omits a resource must fail loud, not read as
        unlimited for that resource -- the same failure mode an unknown key
        already fails loud for, just the opposite typo. Bypasses `_load_from`
        (which backfills missing resources for every other test in this
        class) to exercise the real, unfilled-in loader path."""
        config_file = tmp_path / "tier_config.yaml"
        config_file.write_text(f"community:\n  limits:\n    {QuotaResource.SEATS.value}: 3\n")
        monkeypatch.setenv(ENV_TIER_CONFIG, str(config_file))

        with pytest.raises(ValueError, match="missing resource"):
            _load_tier_config()

    def test_invalid_all_features_value_is_rejected(self, tmp_path, monkeypatch):
        """`bool("false")` is `True` -- an unvalidated quoted string here
        would mint a token unlocking every EE feature for a tier the config
        says shouldn't have them."""
        with pytest.raises(ValueError, match="all_features"):
            self._load_from(
                tmp_path,
                monkeypatch,
                'community:\n  all_features: "false"\n  limits:\n    seats: 3\n',
            )

    def test_real_all_features_bool_is_accepted(self, tmp_path, monkeypatch):
        catalog = self._load_from(
            tmp_path,
            monkeypatch,
            "community:\n  all_features: true\n  limits:\n    seats: 3\n",
        )
        assert catalog[LicenseEdition.COMMUNITY].all_features is True

    def test_unrecognized_overage_value_raises(self, tmp_path, monkeypatch):
        with pytest.raises(ValueError, match="[Ii]nvalid overage policy"):
            self._load_from(
                tmp_path,
                monkeypatch,
                "community:\n  limits:\n    seats: 3\n  overage: lenient\n",
            )

    def test_overage_and_tolerance_are_parsed_from_the_entry(self, tmp_path, monkeypatch):
        catalog = self._load_from(
            tmp_path,
            monkeypatch,
            "community:\n  limits:\n    seats: 3\n"
            "  overage: soft\n  overage_tolerance_percent: 10\n",
        )
        spec = catalog[LicenseEdition.COMMUNITY]
        assert spec.overage is OveragePolicy.SOFT
        assert spec.overage_tolerance_percent == 10

    def test_omitted_overage_fields_use_tierspec_defaults(self, tmp_path, monkeypatch):
        """HARD / 0% -- unchanged behavior for a tier that doesn't opt in."""
        catalog = self._load_from(
            tmp_path,
            monkeypatch,
            "community:\n  limits:\n    seats: 3\n",
        )
        spec = catalog[LicenseEdition.COMMUNITY]
        assert spec.overage is OveragePolicy.HARD
        assert spec.overage_tolerance_percent == 0

    @pytest.mark.parametrize(
        "value,description",
        [("-1", "negative"), ("true", "bool"), ('"25"', "string"), ("1.5", "float")],
    )
    def test_invalid_overage_tolerance_values_are_rejected(
        self, tmp_path, monkeypatch, value, description
    ):
        with pytest.raises(ValueError, match="overage_tolerance_percent"):
            self._load_from(
                tmp_path,
                monkeypatch,
                f"community:\n  limits:\n    seats: 3\n"
                f"  overage: soft\n  overage_tolerance_percent: {value}\n",
            )


class TestTierSpecToPolicy:
    def test_carries_limits_overage_and_tolerance(self):
        spec = TierSpec(
            edition=LicenseEdition.TEAM,
            limits={QuotaResource.SEATS: 10},
            overage=OveragePolicy.SOFT,
            overage_tolerance_percent=25,
        )

        policy = spec.to_policy()

        assert isinstance(policy, QuotaPolicy)
        assert policy.limits == {QuotaResource.SEATS: 10}
        assert policy.overage is OveragePolicy.SOFT
        assert policy.overage_tolerance_percent == 25
        assert policy.ceiling_for(10) == 12


class TestResolvePolicy:
    def test_real_team_tier_is_soft_with_25_percent_tolerance(self):
        """Locks in the shipped tier_config.yaml values the plan calls for:
        team warns at the limit and hard-blocks at limit + 25%."""
        policy = resolve_policy(LicenseEdition.TEAM)

        assert policy.overage is OveragePolicy.SOFT
        assert policy.overage_tolerance_percent == 25
        assert policy.ceiling_for(100_000) == 125_000

    def test_real_enterprise_tier_is_soft_with_25_percent_tolerance(self):
        policy = resolve_policy(LicenseEdition.ENTERPRISE)

        assert policy.overage is OveragePolicy.SOFT
        assert policy.overage_tolerance_percent == 25

    def test_real_community_tier_is_hard_with_no_tolerance(self):
        """Free tier gets no grace band -- blocks exactly at the limit."""
        policy = resolve_policy(LicenseEdition.COMMUNITY)

        assert policy.overage is OveragePolicy.HARD
        assert policy.overage_tolerance_percent == 0
        assert policy.ceiling_for(1_000) == 1_000

    @pytest.mark.parametrize("edition", [None, LicenseEdition.UNKNOWN])
    def test_unresolvable_edition_falls_back_to_a_populated_community_tier(self, edition):
        """Comparing only against ``resolve_policy(COMMUNITY)`` would not be
        enough: both sides come from the same function, so the assertion also
        holds when the community entry has vanished and both are an empty
        dict. An empty limits dict reads as *unlimited* downstream, so that
        fail-open case is exactly what needs catching -- hence the second
        assertion that every resource is actually covered.

        Deliberately no assertion on the numbers themselves: ``resolve_policy``
        reads the catalog loaded at import time, which honours an ambient
        ``RHESIS_TIER_CONFIG`` (see the ``bundled_catalog`` fixture)."""
        policy = resolve_policy(edition)

        assert policy.limits == resolve_policy(LicenseEdition.COMMUNITY).limits
        assert set(policy.limits) == set(QuotaResource)


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
        _assert_catalog_complete(_fallback_catalog())

    def test_a_plain_community_only_dict_is_not_exempt(self):
        """The gate distinguishes the *marked* fallback from a real config
        that merely collapsed to the same shape -- e.g. every paid tier got
        dropped by _load_tier_config's per-entry checks while community
        stayed valid. A bare dict with the identical keys must still raise;
        only the actual _fallback_catalog() marker is exempt (see
        _FallbackCatalog's docstring for why this used to silently pass)."""
        degraded = {LicenseEdition.COMMUNITY: TierSpec(edition=LicenseEdition.COMMUNITY)}
        with pytest.raises(RuntimeError, match="missing an entry"):
            _assert_catalog_complete(degraded)

    def test_missing_community_entry_raises(self):
        """A catalog with every paid tier but no community entry must fail.

        resolve_limits() falls back to the community entry for unlicensed
        orgs; without it that returns an empty dict, which reads downstream
        as unlimited. This is the fail-open case the gate exists to stop."""
        paid_only = {e: TierSpec(edition=e) for e in SELLABLE_EDITIONS}
        with pytest.raises(RuntimeError, match="community"):
            _assert_catalog_complete(paid_only)

    def test_real_bundled_config_is_complete(self):
        """The shipped tier_config.yaml satisfies the gate."""
        _assert_catalog_complete(EDITION_ENTITLEMENTS)
        assert all_sellable() <= set(EDITION_ENTITLEMENTS)


class TestBundledConfigIsPackaged:
    """The bundled YAML must ship as package data, not just exist in the repo.

    _BUNDLED_CONFIG resolves relative to the module file, so if a future
    build-config change stops including non-Python files in the EE wheel,
    _load_tier_config() silently falls back to the community-only catalog
    and every paid tier becomes unsellable. That failure is quiet, so guard
    it here.
    """

    def test_bundled_config_file_exists(self):
        assert _BUNDLED_CONFIG.is_file(), (
            f"{_BUNDLED_CONFIG} is missing. If the EE build config changed, "
            f"confirm tier_config.yaml is still included as package data."
        )

    def test_default_catalog_is_not_the_fallback(self):
        """Loading with no override must yield the real multi-tier catalog,
        not the community-only safety net."""
        assert set(EDITION_ENTITLEMENTS) != {LicenseEdition.COMMUNITY}
        assert all_sellable() <= set(EDITION_ENTITLEMENTS)


class TestTierToLicClaim:
    def test_team_claim_lists_rbac(self):
        claim = tier_to_lic_claim(LicenseEdition.TEAM)
        assert claim[LIC_EDITION] == "team"
        assert claim[LIC_STATUS] == "active"
        assert claim[LIC_ALL_FEATURES] is False
        assert claim[LIC_FEATURES] == [FeatureName.RBAC.value]

    def test_team_claim_has_quota_limits(self, bundled_catalog):
        limits = limits_to_wire(bundled_catalog[LicenseEdition.TEAM].limits)
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
