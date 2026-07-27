"""Shared fixtures for EE licensing tests.

Provides:

- ``ed25519_keypair`` — a throwaway private + public key pair generated fresh
  for each test session; never touches the baked-in prod/nonprod keys.
- ``mint_token`` — a helper that issues a signed JWT against the throwaway
  keypair, suitable for all licensing scenario tests.
- ``patch_public_keys`` — patches :func:`~rhesis.backend.ee.licensing.keys.get_public_keys`
  so verification uses the throwaway key rather than the baked-in ones.
"""

from __future__ import annotations

import time
from typing import Any, Optional
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from rhesis.backend.ee.licensing.entitlements import (
    CLAIM_AUDIENCE,
    CLAIM_EXPIRY,
    CLAIM_ISSUED_AT,
    CLAIM_ISSUER,
    CLAIM_JWT_ID,
    CLAIM_LICENSE,
    CLAIM_SUBJECT,
    LIC_ALL_FEATURES,
    LIC_EDITION,
    LIC_FEATURES,
    LIC_LIMITS,
    LIC_STATUS,
    LICENSE_ALGORITHM,
    LICENSE_AUDIENCE,
    LICENSE_ISSUER,
)
from rhesis.backend.ee.licensing.verify import _parse_token

# Test key id baked into every minted token and the patched key map.
TEST_KID = "test-v1"


@pytest.fixture(scope="session")
def ed25519_keypair():
    """Generate a throwaway Ed25519 keypair for the test session."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture(scope="session")
def mint_token(ed25519_keypair):
    """Return a factory function that mints signed license JWTs.

    Usage::

        token = mint_token(sub="org-uuid", edition="enterprise", status="active")
        token = mint_token(sub="*", exp=int(time.time()) - 1)  # already expired
    """
    private_key, _ = ed25519_keypair

    def _mint(
        sub: str = "00000000-0000-0000-0000-000000000001",
        edition: str = "enterprise",
        status: str = "active",
        all_features: bool = True,
        features: Optional[list] = None,
        limits: Optional[dict] = None,
        exp: Optional[int] = None,
        iss: str = LICENSE_ISSUER,
        aud: str = LICENSE_AUDIENCE,
        kid: str = TEST_KID,
        jti: str = "test-jti-0001",
        extra_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        now = int(time.time())
        payload: dict[str, Any] = {
            CLAIM_ISSUER: iss,
            CLAIM_AUDIENCE: aud,
            CLAIM_SUBJECT: sub,
            CLAIM_ISSUED_AT: now,
            CLAIM_EXPIRY: exp if exp is not None else now + 3600,
            CLAIM_JWT_ID: jti,
            CLAIM_LICENSE: {
                LIC_EDITION: edition,
                LIC_STATUS: status,
                LIC_ALL_FEATURES: all_features,
                LIC_FEATURES: features or [],
                LIC_LIMITS: limits or {},
            },
        }
        if extra_claims:
            payload.update(extra_claims)
        return jwt.encode(
            payload,
            private_key,
            algorithm=LICENSE_ALGORITHM,
            headers={"kid": kid},
        )

    return _mint


@pytest.fixture(autouse=True)
def patch_public_keys(ed25519_keypair):
    """Patch get_public_keys() to return only the throwaway test key.

    Also clears the _parse_token LRU cache before and after each test so
    stale cache entries from other tests do not interfere.
    """
    _, public_key = ed25519_keypair

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    test_keys: dict[str, Ed25519PublicKey] = {TEST_KID: public_key}

    _parse_token.cache_clear()
    with patch(
        "rhesis.backend.ee.licensing.verify.get_public_keys",
        return_value=test_keys,
    ):
        yield
    _parse_token.cache_clear()
