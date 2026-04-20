"""Tests for the OIDC provider (discovery, PKCE, token validation).

All HTTP calls are mocked -- these are pure unit tests.
"""

import hashlib
import json
import time
from base64 import urlsafe_b64encode
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from pydantic import SecretStr

from rhesis.backend.app.auth.constants import AuthProviderType
from rhesis.backend.app.auth.providers.oidc import (
    METADATA_TTL,
    OIDCProvider,
    _JWKS_CACHE,
    _OIDC_METADATA_CACHE,
    create_signed_state,
    verify_signed_state,
)
from rhesis.backend.app.schemas.sso_config import SSOConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sso_config(**overrides):
    defaults = dict(
        issuer_url="https://idp.example.com/realms/test",
        client_id="test-client",
        client_secret=SecretStr("test-secret"),
        enabled=True,
        scopes="openid email profile",
    )
    defaults.update(overrides)
    return SSOConfig(**defaults)


def _generate_rsa_keypair():
    """Generate a fresh RSA keypair for test JWT signing."""
    from cryptography.hazmat.backends import default_backend

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    return private_key


def _jwks_from_private_key(private_key, kid="test-kid-1"):
    """Build a JWKS dict from an RSA private key."""
    from jwt.algorithms import RSAAlgorithm

    public_key = private_key.public_key()
    jwk_dict = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk_dict["kid"] = kid
    jwk_dict["use"] = "sig"
    jwk_dict["alg"] = "RS256"
    return {"keys": [jwk_dict]}


def _make_id_token(private_key, claims, kid="test-kid-1"):
    """Sign claims into a JWT with the given RSA private key."""
    return pyjwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )


def _metadata(issuer="https://idp.example.com/realms/test"):
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/protocol/openid-connect/auth",
        "token_endpoint": f"{issuer}/protocol/openid-connect/token",
        "userinfo_endpoint": f"{issuer}/protocol/openid-connect/userinfo",
        "jwks_uri": f"{issuer}/protocol/openid-connect/certs",
    }


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear OIDC metadata and JWKS caches between tests."""
    _OIDC_METADATA_CACHE.clear()
    _JWKS_CACHE.clear()
    yield
    _OIDC_METADATA_CACHE.clear()
    _JWKS_CACHE.clear()


# ---------------------------------------------------------------------------
# OIDCProvider.get_authorization_url
# ---------------------------------------------------------------------------

class TestGetAuthorizationUrl:

    @pytest.mark.asyncio
    async def test_builds_authorization_url_with_pkce(self):
        config = _sso_config()
        provider = OIDCProvider(config)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _metadata()
        provider._http = MagicMock()
        provider._http.get = AsyncMock(return_value=mock_resp)

        url = await provider.get_authorization_url(
            request=MagicMock(),
            redirect_uri="http://localhost:8080/auth/sso/callback",
            org_id="org-123",
            code_verifier="test-verifier",
            code_challenge="test-challenge",
            nonce="test-nonce",
            return_to="/dashboard",
        )

        assert "response_type=code" in url
        assert "client_id=test-client" in url
        assert "code_challenge=test-challenge" in url
        assert "code_challenge_method=S256" in url
        assert "nonce=test-nonce" in url
        assert "scope=openid+email+profile" in url

    @pytest.mark.asyncio
    async def test_disabled_provider_raises(self):
        config = _sso_config(enabled=False)
        provider = OIDCProvider(config)

        with pytest.raises(ValueError, match="not enabled"):
            await provider.get_authorization_url(
                request=MagicMock(),
                redirect_uri="http://localhost/callback",
            )


# ---------------------------------------------------------------------------
# OIDCProvider.authenticate (token exchange + ID token validation)
# ---------------------------------------------------------------------------

class TestAuthenticate:

    @pytest.mark.asyncio
    async def test_successful_authentication(self):
        private_key = _generate_rsa_keypair()
        jwks = _jwks_from_private_key(private_key)
        config = _sso_config()
        provider = OIDCProvider(config)

        now = int(time.time())
        id_token = _make_id_token(private_key, {
            "sub": "user-123",
            "email": "alice@example.com",
            "name": "Alice Smith",
            "given_name": "Alice",
            "family_name": "Smith",
            "iss": config.issuer_url,
            "aud": config.client_id,
            "exp": now + 300,
            "iat": now,
            "nonce": "test-nonce",
        })

        metadata = _metadata()

        discovery_resp = MagicMock()
        discovery_resp.raise_for_status = MagicMock()
        discovery_resp.json.return_value = metadata

        token_resp = MagicMock()
        token_resp.raise_for_status = MagicMock()
        token_resp.json.return_value = {
            "id_token": id_token,
            "access_token": "at-123",
        }

        jwks_resp = MagicMock()
        jwks_resp.raise_for_status = MagicMock()
        jwks_resp.json.return_value = jwks

        http = MagicMock()
        call_count = 0
        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "openid-configuration" in url:
                return discovery_resp
            return jwks_resp

        http.get = mock_get
        http.post = AsyncMock(return_value=token_resp)
        provider._http = http

        auth_user = await provider.authenticate(
            request=MagicMock(),
            code="auth-code-123",
            code_verifier="verifier",
            nonce="test-nonce",
            redirect_uri="http://localhost/callback",
        )

        assert auth_user.email == "alice@example.com"
        assert auth_user.name == "Alice Smith"
        assert auth_user.external_id == "user-123"
        assert auth_user.provider_type == AuthProviderType.OIDC

    @pytest.mark.asyncio
    async def test_missing_code_raises(self):
        config = _sso_config()
        provider = OIDCProvider(config)

        with pytest.raises(ValueError, match="Authorization code"):
            await provider.authenticate(
                request=MagicMock(),
                code="",
                code_verifier="v",
                nonce="n",
                redirect_uri="http://localhost/callback",
            )

    @pytest.mark.asyncio
    async def test_nonce_mismatch_raises(self):
        private_key = _generate_rsa_keypair()
        jwks = _jwks_from_private_key(private_key)
        config = _sso_config()
        provider = OIDCProvider(config)

        now = int(time.time())
        id_token = _make_id_token(private_key, {
            "sub": "user-123",
            "email": "alice@example.com",
            "iss": config.issuer_url,
            "aud": config.client_id,
            "exp": now + 300,
            "iat": now,
            "nonce": "wrong-nonce",
        })

        metadata = _metadata()

        discovery_resp = MagicMock()
        discovery_resp.raise_for_status = MagicMock()
        discovery_resp.json.return_value = metadata

        token_resp = MagicMock()
        token_resp.raise_for_status = MagicMock()
        token_resp.json.return_value = {"id_token": id_token, "access_token": "at"}

        jwks_resp = MagicMock()
        jwks_resp.raise_for_status = MagicMock()
        jwks_resp.json.return_value = jwks

        http = MagicMock()
        async def mock_get(url, **kwargs):
            if "openid-configuration" in url:
                return discovery_resp
            return jwks_resp

        http.get = mock_get
        http.post = AsyncMock(return_value=token_resp)
        provider._http = http

        with pytest.raises(ValueError, match="nonce"):
            await provider.authenticate(
                request=MagicMock(),
                code="code",
                code_verifier="v",
                nonce="expected-nonce",
                redirect_uri="http://localhost/callback",
            )

    @pytest.mark.asyncio
    async def test_missing_email_falls_back_to_userinfo(self):
        """When id_token has no email, provider fetches userinfo endpoint."""
        private_key = _generate_rsa_keypair()
        jwks = _jwks_from_private_key(private_key)
        config = _sso_config()
        provider = OIDCProvider(config)

        now = int(time.time())
        id_token = _make_id_token(private_key, {
            "sub": "user-456",
            "iss": config.issuer_url,
            "aud": config.client_id,
            "exp": now + 300,
            "iat": now,
            "nonce": "nonce",
        })

        metadata = _metadata()

        discovery_resp = MagicMock()
        discovery_resp.raise_for_status = MagicMock()
        discovery_resp.json.return_value = metadata

        token_resp = MagicMock()
        token_resp.raise_for_status = MagicMock()
        token_resp.json.return_value = {
            "id_token": id_token,
            "access_token": "at-456",
        }

        jwks_resp = MagicMock()
        jwks_resp.raise_for_status = MagicMock()
        jwks_resp.json.return_value = jwks

        userinfo_resp = MagicMock()
        userinfo_resp.raise_for_status = MagicMock()
        userinfo_resp.json.return_value = {"email": "bob@example.com"}

        http = MagicMock()
        async def mock_get(url, **kwargs):
            if "openid-configuration" in url:
                return discovery_resp
            if "certs" in url:
                return jwks_resp
            if "userinfo" in url:
                return userinfo_resp
            return jwks_resp

        http.get = mock_get
        http.post = AsyncMock(return_value=token_resp)
        provider._http = http

        auth_user = await provider.authenticate(
            request=MagicMock(),
            code="code",
            code_verifier="v",
            nonce="nonce",
            redirect_uri="http://localhost/callback",
        )

        assert auth_user.email == "bob@example.com"


# ---------------------------------------------------------------------------
# OIDCProvider properties
# ---------------------------------------------------------------------------

class TestOIDCProviderProperties:

    def test_name(self):
        provider = OIDCProvider(_sso_config())
        assert provider.name == "oidc"

    def test_display_name(self):
        provider = OIDCProvider(_sso_config())
        assert provider.display_name == "SSO"

    def test_is_oauth(self):
        provider = OIDCProvider(_sso_config())
        assert provider.is_oauth is True

    def test_is_enabled_true(self):
        provider = OIDCProvider(_sso_config(enabled=True))
        assert provider.is_enabled is True

    def test_is_enabled_false(self):
        provider = OIDCProvider(_sso_config(enabled=False))
        assert provider.is_enabled is False


# ---------------------------------------------------------------------------
# Metadata caching
# ---------------------------------------------------------------------------

class TestMetadataCaching:

    @pytest.mark.asyncio
    async def test_metadata_cached_between_calls(self):
        config = _sso_config()
        provider = OIDCProvider(config)
        metadata = _metadata()

        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = metadata

        call_count = 0
        async def counting_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return resp

        provider._http = MagicMock()
        provider._http.get = counting_get

        await provider._get_oidc_metadata()
        await provider._get_oidc_metadata()

        assert call_count == 1
