"""Unit tests for :mod:`rhesis.backend.ee.licensing.verify`."""

from __future__ import annotations

import time

import pytest

from rhesis.backend.ee.licensing.entitlements import (
    CLAIM_AUDIENCE,
    CLAIM_EXPIRY,
    CLAIM_ISSUER,
    CLAIM_LICENSE,
    CLAIM_SUBJECT,
    LICENSE_ALGORITHM,
    LICENSE_AUDIENCE,
    LICENSE_ISSUER,
)
from rhesis.backend.ee.licensing.verify import verify_token

from .conftest import TEST_KID

pytestmark = pytest.mark.skipif(
    not pytest.importorskip(
        "rhesis.backend.ee",
        reason="EE package not installed",
    ),
    reason="EE package not installed",
)


class TestVerifyTokenValid:
    def test_valid_token_returns_entitlements(self, mint_token):
        token = mint_token()
        result = verify_token(token)
        assert result is not None
        assert result.edition == "enterprise"
        assert result.status == "active"
        assert result.all_features is True

    def test_blanket_sub_star(self, mint_token):
        token = mint_token(sub="*")
        result = verify_token(token)
        assert result is not None
        assert result.sub == "*"

    def test_specific_features_list(self, mint_token):
        token = mint_token(all_features=False, features=["sso", "api_clients"])
        result = verify_token(token)
        assert result is not None
        assert result.all_features is False
        assert "sso" in result.features
        assert "api_clients" in result.features

    def test_limits_are_parsed(self, mint_token):
        token = mint_token(limits={"seats": 50})
        result = verify_token(token)
        assert result is not None
        assert result.limits == {"seats": 50}

    def test_expires_at_is_set(self, mint_token):
        future_exp = int(time.time()) + 7200
        token = mint_token(exp=future_exp)
        result = verify_token(token)
        assert result is not None
        assert result.expires_at is not None

    def test_jti_is_preserved(self, mint_token):
        token = mint_token(jti="unique-audit-id")
        result = verify_token(token)
        assert result is not None
        assert result.jti == "unique-audit-id"


class TestVerifyTokenExpired:
    def test_expired_token_returns_none(self, mint_token):
        past_exp = int(time.time()) - 7200
        token = mint_token(exp=past_exp)
        result = verify_token(token)
        assert result is None

    def test_token_within_leeway_returns_entitlements(self, mint_token):
        """Token expired less than EXPIRY_LEEWAY_SECONDS ago is still accepted."""
        from rhesis.backend.ee.licensing.entitlements import EXPIRY_LEEWAY_SECONDS

        # 30s within the leeway window (leeway is 60s)
        within_leeway = int(time.time()) - (EXPIRY_LEEWAY_SECONDS - 30)
        token = mint_token(exp=within_leeway)
        result = verify_token(token)
        assert result is not None


class TestVerifyTokenTampered:
    def test_tampered_payload_returns_none(self, mint_token):
        import base64
        import json

        token = mint_token()
        parts = token.split(".")
        # Flip one bit in the payload
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        payload["sub"] = "attacker-org"
        new_payload = (
            base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        )
        tampered = f"{parts[0]}.{new_payload}.{parts[2]}"
        assert verify_token(tampered) is None

    def test_wrong_signature_returns_none(self, mint_token, ed25519_keypair):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        # Sign with a different key
        other_key = Ed25519PrivateKey.generate()
        import jwt as pyjwt

        token = pyjwt.encode(
            {
                CLAIM_SUBJECT: "x",
                CLAIM_ISSUER: LICENSE_ISSUER,
                CLAIM_AUDIENCE: LICENSE_AUDIENCE,
                CLAIM_EXPIRY: int(time.time()) + 3600,
                CLAIM_LICENSE: {},
            },
            other_key,
            algorithm=LICENSE_ALGORITHM,
            headers={"kid": TEST_KID},
        )
        assert verify_token(token) is None


class TestVerifyTokenClaimMismatch:
    def test_wrong_issuer_returns_none(self, mint_token):
        token = mint_token(iss="evil-issuer")
        assert verify_token(token) is None

    def test_wrong_audience_returns_none(self, mint_token):
        token = mint_token(aud="wrong-audience")
        assert verify_token(token) is None

    def test_garbage_string_returns_none(self):
        assert verify_token("not.a.jwt") is None

    def test_empty_string_returns_none(self):
        assert verify_token("") is None

    @pytest.mark.parametrize(
        "missing", [CLAIM_ISSUER, CLAIM_AUDIENCE, CLAIM_SUBJECT, CLAIM_EXPIRY]
    )
    def test_missing_required_claim_returns_none(self, ed25519_keypair, missing):
        """A token missing a required claim must fail closed (return None),
        not raise. PyJWT raises MissingRequiredClaimError here, which is an
        InvalidTokenError but NOT a DecodeError — the regression this guards.
        """
        import time

        import jwt as pyjwt

        from rhesis.backend.ee.licensing.entitlements import (
            LIC_ALL_FEATURES,
            LIC_EDITION,
            LIC_STATUS,
            LicenseEdition,
            LicenseStatus,
        )

        private_key, _ = ed25519_keypair
        claims = {
            CLAIM_ISSUER: LICENSE_ISSUER,
            CLAIM_AUDIENCE: LICENSE_AUDIENCE,
            CLAIM_SUBJECT: "*",
            CLAIM_EXPIRY: int(time.time()) + 3600,
            CLAIM_LICENSE: {
                LIC_EDITION: LicenseEdition.ENTERPRISE.value,
                LIC_STATUS: LicenseStatus.ACTIVE.value,
                LIC_ALL_FEATURES: True,
            },
        }
        claims.pop(missing)
        token = pyjwt.encode(
            claims, private_key, algorithm=LICENSE_ALGORITHM, headers={"kid": TEST_KID}
        )
        assert verify_token(token) is None


class TestVerifyTokenMissingKeys:
    def test_no_keys_returns_none(self, mint_token):
        from unittest.mock import patch

        from rhesis.backend.ee.licensing.verify import _parse_token

        _parse_token.cache_clear()
        token = mint_token()
        with patch("rhesis.backend.ee.licensing.verify.get_public_keys", return_value={}):
            result = verify_token(token)
        _parse_token.cache_clear()
        assert result is None
