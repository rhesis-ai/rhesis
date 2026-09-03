"""Adversarial tests for the licensing and quota system.

Everything here asks one question: **can a customer end up with more than they
paid for?** Either more features, a higher tier, or a higher (or absent) usage
ceiling. Each test states the escalation it is trying to achieve, so a failure
reads as "this attack now works" rather than "an assertion changed".

The threat model, stated explicitly because it decides what is in scope:

- A customer controls their own API requests and request bodies, and anything
  the API lets them write. They do **not** hold the license signing key.
- ``organization.license`` is server-side state. It is not in the Organization
  Pydantic schema, so it cannot be set over the wire -- that exclusion is
  itself load-bearing and is asserted here (see
  :class:`TestLicenseColumnIsNotClientWritable`), because adding the field to
  the schema later would hand customers the ability to install their own token.
- So the realistic attacks are: present a token we did not sign, replay a token
  we signed for someone else, or exploit a *logic* gap that turns a valid
  low-tier license into a high-tier one.

Fail-closed is the invariant throughout: anything we cannot verify resolves to
``community`` limits and no features, never to unlimited.
"""

from __future__ import annotations

import time
from typing import Any, Optional
from unittest.mock import MagicMock, patch
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.ee.licensing.entitlements import (
    CLAIM_AUDIENCE,
    CLAIM_EXPIRY,
    CLAIM_ISSUED_AT,
    CLAIM_ISSUER,
    CLAIM_JWT_ID,
    CLAIM_LICENSE,
    CLAIM_SUBJECT,
    LIC_ALL_FEATURES,
    LIC_CUSTOM_LIMITS,
    LIC_EDITION,
    LIC_FEATURES,
    LIC_LIMITS,
    LIC_STATUS,
    LICENSE_AUDIENCE,
    LICENSE_ISSUER,
    LicenseEdition,
)
from rhesis.backend.ee.licensing.provider import SignedTokenLicenseProvider
from rhesis.backend.ee.licensing.quota_provider import ConfigQuotaProvider
from rhesis.backend.ee.licensing.tiers import resolve_limits, resolve_policy, resolve_tier
from rhesis.backend.ee.licensing.verify import _parse_token, verify_token

pytestmark = pytest.mark.skipif(
    not pytest.importorskip(
        "rhesis.backend.ee",
        reason="EE package not installed",
    ),
    reason="EE package not installed",
)

_VICTIM_ORG = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_OTHER_ORG = "11111111-2222-3333-4444-555555555555"

_SSO = Feature(name=FeatureName.SSO, display_name="SSO")

_COMMUNITY_LIMITS = resolve_limits(LicenseEdition.COMMUNITY)
_ENTERPRISE_LIMITS = resolve_tier(LicenseEdition.ENTERPRISE).limits


def _make_org(org_id: str = _VICTIM_ORG, license_token: str | None = None) -> MagicMock:
    org = MagicMock()
    org.id = UUID(org_id)
    org.license = license_token
    return org


def _lic_claim(
    edition: str = "enterprise",
    status: str = "active",
    all_features: Any = True,
    features: Optional[list] = None,
    limits: Optional[dict] = None,
    custom_limits: Optional[dict] = None,
) -> dict:
    claim: dict[str, Any] = {
        LIC_EDITION: edition,
        LIC_STATUS: status,
        LIC_ALL_FEATURES: all_features,
        LIC_FEATURES: features if features is not None else [],
        LIC_LIMITS: limits or {},
    }
    if custom_limits is not None:
        claim[LIC_CUSTOM_LIMITS] = custom_limits
    return claim


def _payload(sub: str = _VICTIM_ORG, exp_offset: int = 3600, **claim_kwargs) -> dict:
    now = int(time.time())
    return {
        CLAIM_ISSUER: LICENSE_ISSUER,
        CLAIM_AUDIENCE: LICENSE_AUDIENCE,
        CLAIM_SUBJECT: sub,
        CLAIM_ISSUED_AT: now,
        CLAIM_EXPIRY: now + exp_offset,
        CLAIM_JWT_ID: "loophole-test",
        CLAIM_LICENSE: _lic_claim(**claim_kwargs),
    }


def _b64url(raw: bytes) -> str:
    """Base64url with padding stripped, as JWT requires."""
    import base64

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _hs256_token(payload: dict, secret: bytes) -> str:
    """Hand-build an HS256 JWT, bypassing PyJWT's encode-side key guard."""
    import hashlib
    import hmac
    import json

    signing_input = ".".join(
        (
            _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()),
            _b64url(json.dumps(payload).encode()),
        )
    )
    signature = hmac.new(secret, signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


@pytest.fixture
def attacker_key():
    """A keypair we never registered as trusted -- stands in for any key a
    customer could generate themselves."""
    return Ed25519PrivateKey.generate()


@pytest.fixture
def provider():
    return SignedTokenLicenseProvider()


@pytest.fixture
def quota_provider():
    return ConfigQuotaProvider()


@pytest.fixture
def licensed_registry():
    """Install the real EE license provider so quota resolution reads real tokens."""
    saved = FeatureRegistry._license
    FeatureRegistry.set_license_provider(SignedTokenLicenseProvider())
    yield
    FeatureRegistry._license = saved


@pytest.fixture(autouse=True)
def _no_env_license():
    """Neutralize RHESIS_LICENSE for every test here.

    A blanket env token grants its tier to *every* org, so leaving one set would
    mask exactly the per-org checks these tests exist to exercise.
    """
    with patch.dict("os.environ", {"RHESIS_LICENSE": ""}):
        yield


def _limits_for(quota_provider, org) -> dict:
    return quota_provider.get_policy(org).limits


def _retention_for(quota_provider, org) -> int | None:
    return quota_provider.get_policy(org).retention_days


# ---------------------------------------------------------------------------
# 1. Tokens we did not sign
# ---------------------------------------------------------------------------


class TestForgedTokens:
    """Escalation attempt: mint your own enterprise license.

    Each token here claims ``edition: enterprise`` with ``all_features``. All of
    them must resolve to no features and community limits.
    """

    def _assert_rejected(self, token, provider, quota_provider):
        org = _make_org(license_token=token)
        assert verify_token(token) is None
        assert provider.allows_feature(_SSO, org) is False
        assert _limits_for(quota_provider, org) == _COMMUNITY_LIMITS

        # Asserted field by field rather than as one dict, so adding a field to
        # `info()` cannot make this pass vacuously -- and so each claim reads as
        # its own security property.
        info = provider.info(org)
        assert info["edition"] == "community"
        assert info["licensed"] is False
        # A forged *paid* token must not report a paid tier either. `is_paid`
        # drives the plan badge and the crown, so leaking it here would let a
        # forged token buy the appearance of a paid plan even with community
        # limits enforced.
        assert info.get("is_paid") is False

    def test_unsigned_alg_none_token_is_rejected(self, provider, quota_provider):
        """The classic: strip the signature and set ``alg: none``.

        Blocked because ``jwt.decode`` pins ``algorithms=["EdDSA"]``.
        """
        token = jwt.encode(_payload(), key="", algorithm="none")
        self._assert_rejected(token, provider, quota_provider)

    def test_hmac_algorithm_confusion_is_rejected(self, ed25519_keypair, provider, quota_provider):
        """Algorithm confusion: re-sign with HS256 using the *public* key as the
        HMAC secret.

        The public key is not secret, so against a verifier that trusts the
        token's own ``alg`` header this forges anything. Built by hand rather
        than with ``jwt.encode``, which refuses an asymmetric key as an HMAC
        secret -- that guard protects our own signing code, not us from an
        attacker who is not using PyJWT.
        """
        _, public_key = ed25519_keypair
        secret = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        token = _hs256_token(_payload(), secret)
        self._assert_rejected(token, provider, quota_provider)

    def test_token_signed_by_an_untrusted_key_is_rejected(
        self, attacker_key, provider, quota_provider
    ):
        """Correct algorithm, correct claim shape, wrong signing key."""
        token = jwt.encode(_payload(), key=attacker_key, algorithm="EdDSA")
        self._assert_rejected(token, provider, quota_provider)

    def test_forged_token_with_a_trusted_kid_is_rejected(
        self, attacker_key, provider, quota_provider
    ):
        """Claiming a trusted ``kid`` must not select a key that then verifies a
        signature made with a different one. ``kid`` picks the candidate key; it
        never substitutes for the signature check.
        """
        token = jwt.encode(
            _payload(), key=attacker_key, algorithm="EdDSA", headers={"kid": "test-v1"}
        )
        self._assert_rejected(token, provider, quota_provider)

    def test_tampered_payload_with_a_valid_signature_is_rejected(
        self, mint_token, provider, quota_provider
    ):
        """Swap the payload of a legitimately signed community token for an
        enterprise one, keeping the original signature."""
        import base64
        import json

        legit = mint_token(sub=_VICTIM_ORG, edition="community", all_features=False)
        header_b64, _payload_b64, signature_b64 = legit.split(".")

        def _b64(raw: bytes) -> str:
            return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

        forged_payload = _b64(json.dumps(_payload()).encode())
        token = f"{header_b64}.{forged_payload}.{signature_b64}"
        self._assert_rejected(token, provider, quota_provider)

    @pytest.mark.parametrize(
        "overrides",
        [
            {CLAIM_ISSUER: "attacker-issuer"},
            {CLAIM_AUDIENCE: "attacker-audience"},
        ],
        ids=["wrong-issuer", "wrong-audience"],
    )
    def test_wrong_issuer_or_audience_is_rejected(
        self, ed25519_keypair, provider, quota_provider, overrides
    ):
        """Even signed by the real key, a token issued for something else must
        not be accepted here."""
        private_key, _ = ed25519_keypair
        payload = {**_payload(), **overrides}
        token = jwt.encode(payload, key=private_key, algorithm="EdDSA", headers={"kid": "test-v1"})
        self._assert_rejected(token, provider, quota_provider)

    @pytest.mark.parametrize("drop", [CLAIM_SUBJECT, CLAIM_EXPIRY], ids=["no-sub", "no-exp"])
    def test_missing_required_claims_are_rejected(
        self, ed25519_keypair, provider, quota_provider, drop
    ):
        """A token with no ``sub`` would otherwise have nothing to bind it to an
        org; one with no ``exp`` would never expire."""
        private_key, _ = ed25519_keypair
        payload = {k: v for k, v in _payload().items() if k != drop}
        token = jwt.encode(payload, key=private_key, algorithm="EdDSA", headers={"kid": "test-v1"})
        self._assert_rejected(token, provider, quota_provider)


# ---------------------------------------------------------------------------
# 2. Replaying tokens we did sign, for someone else
# ---------------------------------------------------------------------------


class TestTokenReplay:
    """Escalation attempt: obtain a real enterprise token and use it as your own."""

    def test_another_orgs_token_does_not_apply_to_you(
        self, mint_token, provider, quota_provider, licensed_registry
    ):
        token = mint_token(sub=_OTHER_ORG, edition="enterprise")
        org = _make_org(_VICTIM_ORG, license_token=token)

        # The token itself is perfectly valid -- it just is not ours.
        assert verify_token(token) is not None
        assert provider.allows_feature(_SSO, org) is False
        assert _limits_for(quota_provider, org) == _COMMUNITY_LIMITS

    def test_blanket_token_in_the_org_column_does_not_apply(
        self, mint_token, provider, quota_provider, licensed_registry
    ):
        """A blanket ``sub:"*"`` license is an operator-level, single-tenant
        deployment mechanism, honoured only from the ``RHESIS_LICENSE`` env var.

        If the org column accepted it too, any customer who ever saw a blanket
        token (a self-hosted licensee, say) could paste it into a cloud tenant
        and self-upgrade. The column path requires ``sub == org.id``, and ``"*"``
        is not a UUID.
        """
        token = mint_token(sub="*", edition="enterprise")
        org = _make_org(_VICTIM_ORG, license_token=token)

        assert verify_token(token) is not None
        assert provider.allows_feature(_SSO, org) is False
        assert _limits_for(quota_provider, org) == _COMMUNITY_LIMITS

    def test_expired_enterprise_token_gives_community_quota(
        self, mint_token, quota_provider, licensed_registry
    ):
        token = mint_token(sub=_VICTIM_ORG, edition="enterprise", exp=int(time.time()) - 3600)
        org = _make_org(license_token=token)
        assert _limits_for(quota_provider, org) == _COMMUNITY_LIMITS

    @pytest.mark.parametrize("status", ["canceled", "unknown", "not-a-status"])
    def test_revoked_license_gives_community_quota_not_its_old_tier(
        self, mint_token, quota_provider, licensed_registry, status
    ):
        """Stopping payment must stop the allowance.

        ``info()`` deliberately keeps reporting the lapsed edition so the UI can
        name what expired, which makes it tempting to resolve limits from that
        name -- and that left a canceled enterprise org on unlimited quota
        indefinitely.
        """
        token = mint_token(sub=_VICTIM_ORG, edition="enterprise", status=status)
        org = _make_org(license_token=token)
        limits = _limits_for(quota_provider, org)

        assert limits == _COMMUNITY_LIMITS
        assert limits != _ENTERPRISE_LIMITS
        assert limits[QuotaResource.TEST_EXECUTIONS] is not None


# ---------------------------------------------------------------------------
# 3. Tier escalation through claim values
# ---------------------------------------------------------------------------


class TestEditionEscalation:
    """Escalation attempt: name a tier that resolves to more than it should.

    These all require our signing key, so they are defense-in-depth against a
    minting mistake rather than a customer-reachable attack. They matter because
    the failure mode is silent and generous.
    """

    @pytest.mark.parametrize(
        "edition",
        ["ENTERPRISE", "Enterprise", " enterprise", "enterprise ", "unknown", "", "nope"],
    )
    def test_unrecognized_edition_falls_back_to_community_not_unlimited(
        self, mint_token, quota_provider, licensed_registry, edition
    ):
        """``LicenseEdition._missing_`` coerces anything unrecognized to
        ``UNKNOWN``, which must resolve to community limits.

        The dangerous alternative is an empty limits dict: every consumer reads a
        missing resource as *unlimited*, so a typo'd edition would hand out
        unmetered access rather than the free tier.
        """
        token = mint_token(sub=_VICTIM_ORG, edition=edition, all_features=False)
        org = _make_org(license_token=token)
        limits = _limits_for(quota_provider, org)

        assert limits == _COMMUNITY_LIMITS
        assert all(limits[r] is not None for r in (QuotaResource.TEST_EXECUTIONS,))

    def test_unknown_edition_never_resolves_to_the_internal_master_tier(
        self, mint_token, quota_provider, licensed_registry
    ):
        """``master`` is an internal all-features, all-unlimited tier. No
        fallback path may land on it."""
        token = mint_token(sub=_VICTIM_ORG, edition="mastr", all_features=False)
        org = _make_org(license_token=token)
        assert _limits_for(quota_provider, org) != resolve_tier(LicenseEdition.MASTER).limits

    def test_missing_edition_claim_falls_back_to_community(
        self, ed25519_keypair, quota_provider, licensed_registry
    ):
        private_key, _ = ed25519_keypair
        payload = _payload(all_features=False)
        del payload[CLAIM_LICENSE][LIC_EDITION]
        token = jwt.encode(payload, key=private_key, algorithm="EdDSA", headers={"kid": "test-v1"})
        org = _make_org(license_token=token)
        assert _limits_for(quota_provider, org) == _COMMUNITY_LIMITS


class TestFeatureClaimCoercion:
    """Escalation attempt: get ``allows_feature`` to say yes without a grant."""

    @pytest.mark.parametrize(
        "all_features",
        [False, None, 0, "", "false", "no", "0", [], {}],
        ids=[
            "false",
            "none",
            "zero",
            "empty-string",
            "string-false",
            "string-no",
            "string-zero",
            "empty-list",
            "empty-dict",
        ],
    )
    def test_only_a_real_true_unlocks_every_feature(self, mint_token, provider, all_features):
        """``all_features`` is a blanket grant over every registered EE feature,
        so it must be read strictly.

        ``bool("false")`` is ``True`` in Python, so a plain ``bool()`` coercion
        turns the *string* ``"false"`` into a full grant -- the exact trap the
        tier-YAML loader already guards against in ``_parse_all_features``. This
        pins the token side to the same standard: only a literal JSON ``true``
        counts.
        """
        token = mint_token(sub=_VICTIM_ORG, edition="team", all_features=all_features, features=[])
        org = _make_org(license_token=token)
        assert provider.allows_feature(_SSO, org) is False

    def test_a_real_true_still_unlocks_features(self, mint_token, provider):
        """The guard above must not break the legitimate grant."""
        token = mint_token(sub=_VICTIM_ORG, edition="enterprise", all_features=True)
        org = _make_org(license_token=token)
        assert provider.allows_feature(_SSO, org) is True

    @pytest.mark.parametrize(
        "features",
        ["sso", {"sso": True}, None],
        ids=["bare-string", "dict", "null"],
    )
    def test_a_malformed_feature_list_grants_nothing(self, mint_token, provider, features):
        """A bare string would iterate per character, and a dict per key. Neither
        should accidentally yield a grant, and neither should raise."""
        token = mint_token(sub=_VICTIM_ORG, edition="team", all_features=False, features=features)
        org = _make_org(license_token=token)
        assert provider.allows_feature(_SSO, org) is False


# ---------------------------------------------------------------------------
# 4. Quota escalation through the custom_limits overlay
# ---------------------------------------------------------------------------


class TestCustomLimitEscalation:
    """Escalation attempt: use the bespoke-limits overlay to unmeter yourself.

    The overlay exists so a negotiated enterprise cap can be enforced. The risk
    it introduces is the opposite of its purpose: an override that fails to
    parse must not become "no limit".
    """

    @pytest.mark.parametrize(
        "junk",
        [
            {"test_executions": "unlimited"},
            {"test_executions": True},
            {"test_executions": -1},
            {"not_a_resource": 999},
            {"test_executions": 1.5},
            "not-a-mapping",
            [],
        ],
        ids=[
            "string",
            "bool",
            "negative",
            "unknown-key",
            "float",
            "non-mapping",
            "list",
        ],
    )
    def test_an_unparseable_override_keeps_the_tier_limit(
        self, mint_token, quota_provider, licensed_registry, junk
    ):
        """Falls back to the tier's own number, never to ``None``.

        ``None`` means unlimited to every consumer, so "we could not read the
        override" must not be spelled the same way as "this org has no ceiling".
        """
        token = mint_token(sub=_VICTIM_ORG, edition="team", custom_limits=junk)
        org = _make_org(license_token=token)
        limits = _limits_for(quota_provider, org)

        assert limits == resolve_tier(LicenseEdition.TEAM).limits
        assert limits[QuotaResource.TEST_EXECUTIONS] is not None

    def test_a_malformed_override_does_not_cost_the_org_its_license(
        self, mint_token, provider, licensed_registry
    ):
        """The other direction of the same failure: a non-mapping claim used to
        raise inside entitlement parsing, rejecting the whole token and silently
        demoting a paying enterprise org to community."""
        token = mint_token(sub=_VICTIM_ORG, edition="enterprise", custom_limits="not-a-mapping")
        org = _make_org(license_token=token)

        assert provider.allows_feature(_SSO, org) is True
        assert provider.info(org)["edition"] == "enterprise"

    def test_another_orgs_override_does_not_apply_to_you(
        self, mint_token, quota_provider, licensed_registry
    ):
        token = mint_token(
            sub=_OTHER_ORG,
            edition="enterprise",
            custom_limits={"test_executions": 10_000_000},
        )
        org = _make_org(_VICTIM_ORG, license_token=token)
        assert _limits_for(quota_provider, org) == _COMMUNITY_LIMITS

    def test_an_override_on_a_revoked_license_does_not_apply(
        self, mint_token, quota_provider, licensed_registry
    ):
        """A canceled license must not keep its bespoke allowances."""
        token = mint_token(
            sub=_VICTIM_ORG,
            edition="enterprise",
            status="canceled",
            custom_limits={"test_executions": 10_000_000},
        )
        org = _make_org(license_token=token)
        limits = _limits_for(quota_provider, org)

        assert limits == _COMMUNITY_LIMITS
        assert (
            limits[QuotaResource.TEST_EXECUTIONS]
            == _COMMUNITY_LIMITS[QuotaResource.TEST_EXECUTIONS]
        )

    def test_the_mint_time_snapshot_cannot_raise_a_limit(
        self, mint_token, quota_provider, licensed_registry
    ):
        """``lic.limits`` is an audit snapshot and must never be enforced.

        If it were, a token minted under older, more generous pricing would keep
        overriding the catalog for good -- and a published limit *reduction*
        would silently miss every existing customer.
        """
        inflated = {r.value: 10_000_000 for r in QuotaResource}
        token = mint_token(sub=_VICTIM_ORG, edition="team", limits=inflated)
        org = _make_org(license_token=token)

        assert _limits_for(quota_provider, org) == resolve_tier(LicenseEdition.TEAM).limits

    def test_an_override_cannot_change_the_overage_policy(
        self, mint_token, quota_provider, licensed_registry
    ):
        """Community is a hard block at the limit. An override must not turn that
        into a soft tier with a grace band on top of the free allowance."""
        token = mint_token(
            sub=_VICTIM_ORG, edition="community", custom_limits={"test_executions": 500}
        )
        org = _make_org(license_token=token)
        policy = quota_provider.get_policy(org)

        # Unlicensed/community resolution ignores the token entirely, so the
        # community hard policy stands and the ceiling equals the limit.
        assert policy.ceiling_for(500) == 500


# ---------------------------------------------------------------------------
# 5. Ways to end up unlimited without a license at all
# ---------------------------------------------------------------------------


class TestNoLicenseIsNeverUnlimited:
    """The fail-open cases. Each asserts a *finite* free-tier ceiling."""

    @pytest.mark.parametrize(
        "license_value",
        [None, "", "   ", "not-a-jwt", "a.b.c", "null", "{}"],
        ids=["none", "empty", "whitespace", "garbage", "three-parts", "null", "braces"],
    )
    def test_absent_or_junk_license_resolves_to_finite_community_limits(
        self, quota_provider, licensed_registry, license_value
    ):
        org = _make_org(license_token=license_value)
        limits = _limits_for(quota_provider, org)

        assert limits == _COMMUNITY_LIMITS
        for resource in (
            QuotaResource.TEST_EXECUTIONS,
            QuotaResource.TRACING_SPANS,
            QuotaResource.SEATS,
        ):
            assert limits[resource] is not None, f"{resource.value} must be metered"

    def test_no_public_keys_fails_closed(self, mint_token, provider, quota_provider):
        """If key loading breaks, verification must deny rather than skip.

        A verifier that treats "no keys" as "nothing to check" would hand every
        org whatever its token claims.
        """
        token = mint_token(sub=_VICTIM_ORG, edition="enterprise")
        org = _make_org(license_token=token)

        _parse_token.cache_clear()
        with patch("rhesis.backend.ee.licensing.verify.get_public_keys", return_value={}):
            assert verify_token(token) is None
            assert provider.allows_feature(_SSO, org) is False
            assert _limits_for(quota_provider, org) == _COMMUNITY_LIMITS
        _parse_token.cache_clear()


class TestLicenseColumnIsNotClientWritable:
    """The assumption the whole threat model rests on.

    Every test above assumes a customer cannot install a token of their choosing.
    That holds only because ``license`` is absent from the Organization request
    schemas. Adding it -- easy to do by widening a base schema -- would let a
    customer install any token they have seen, so it is asserted rather than
    trusted.
    """

    def test_license_is_not_an_accepted_organization_input_field(self):
        from rhesis.backend.app import schemas

        for schema_name in ("OrganizationCreate", "OrganizationUpdate", "OrganizationBase"):
            schema = getattr(schemas, schema_name, None)
            if schema is None:
                continue
            assert "license" not in schema.model_fields, (
                f"{schema_name} accepts a client-supplied 'license'. That lets an "
                f"organization install its own license token and pick its own tier."
            )


# ---------------------------------------------------------------------------
# 6. Retention escalation through custom_retention_days
# ---------------------------------------------------------------------------


_COMMUNITY_RETENTION = resolve_policy(None).retention_days
_ENTERPRISE_RETENTION = resolve_policy(LicenseEdition.ENTERPRISE).retention_days


class TestRetentionEscalation:
    """Escalation attempt: use the custom_retention_days claim to avoid data
    deletion, or inherit unlimited retention without paying for it.

    ``retention_days`` controls how long trace data is kept before the sweep
    hard-deletes it. ``None`` means unlimited. An invalid override must fall
    back to the tier's own value, never to ``None``.
    """

    @pytest.mark.parametrize(
        "junk",
        [
            "unlimited",
            True,
            False,
            -1,
            0,
            1.5,
            [],
            {},
            "365",
        ],
        ids=[
            "string",
            "bool-true",
            "bool-false",
            "negative",
            "zero",
            "float",
            "list",
            "dict",
            "numeric-string",
        ],
    )
    def test_an_unparseable_override_keeps_the_tier_retention(
        self, mint_token, quota_provider, licensed_registry, junk
    ):
        """A bad custom_retention_days must not become None (unlimited)."""
        token = mint_token(sub=_VICTIM_ORG, edition="team", custom_retention_days=junk)
        org = _make_org(license_token=token)
        retention = _retention_for(quota_provider, org)

        team_retention = resolve_policy(LicenseEdition.TEAM).retention_days
        assert retention == team_retention
        assert retention is not None

    def test_a_valid_override_applies(
        self, mint_token, quota_provider, licensed_registry
    ):
        token = mint_token(sub=_VICTIM_ORG, edition="enterprise", custom_retention_days=180)
        org = _make_org(license_token=token)

        assert _retention_for(quota_provider, org) == 180

    def test_another_orgs_retention_override_does_not_apply_to_you(
        self, mint_token, quota_provider, licensed_registry
    ):
        token = mint_token(
            sub=_OTHER_ORG,
            edition="enterprise",
            custom_retention_days=730,
        )
        org = _make_org(_VICTIM_ORG, license_token=token)
        assert _retention_for(quota_provider, org) == _COMMUNITY_RETENTION

    def test_retention_override_on_a_revoked_license_does_not_apply(
        self, mint_token, quota_provider, licensed_registry
    ):
        token = mint_token(
            sub=_VICTIM_ORG,
            edition="enterprise",
            status="canceled",
            custom_retention_days=730,
        )
        org = _make_org(license_token=token)
        retention = _retention_for(quota_provider, org)

        assert retention == _COMMUNITY_RETENTION
        assert retention is not None

    def test_absent_or_junk_license_gives_finite_community_retention(
        self, quota_provider, licensed_registry
    ):
        org = _make_org(license_token=None)
        retention = _retention_for(quota_provider, org)

        assert retention == _COMMUNITY_RETENTION
        assert retention is not None, "unlicensed org must have finite retention"

    def test_expired_enterprise_token_gives_community_retention(
        self, mint_token, quota_provider, licensed_registry
    ):
        import time

        token = mint_token(
            sub=_VICTIM_ORG, edition="enterprise", exp=int(time.time()) - 3600
        )
        org = _make_org(license_token=token)

        assert _retention_for(quota_provider, org) == _COMMUNITY_RETENTION
