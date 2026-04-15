"""Generic OIDC Authentication Provider for per-org SSO.

NOT registered in ProviderRegistry -- instantiated per-request by the SSO router
with the org's SSOConfig. Works with any OIDC-compliant IdP (Keycloak, Okta, Azure AD).
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import jwt as pyjwt

from rhesis.backend.app.auth.constants import ALGORITHM, AuthProviderType
from rhesis.backend.app.auth.providers.base import AuthProvider, AuthUser
from rhesis.backend.app.auth.sso_http_client import (
    SSOHttpClient,
    SSRFError,
    validate_endpoint_origin,
)
from rhesis.backend.app.schemas.sso_config import SSOConfig

logger = logging.getLogger(__name__)

_OIDC_METADATA_CACHE: Dict[str, Tuple[dict, float]] = {}
_JWKS_CACHE: Dict[str, Tuple[dict, float]] = {}
_JWKS_REFRESH_COOLDOWN: Dict[str, float] = {}
_CACHE_LOCK = asyncio.Lock()

METADATA_TTL = 3600  # 1 hour
JWKS_TTL = 3600
JWKS_REFRESH_COOLDOWN_SECONDS = 300  # 5 minutes
CLOCK_SKEW_SECONDS = 30
STATE_MAX_AGE_SECONDS = 300  # 5 minutes


def _get_state_signing_key() -> bytes:
    """Derive a signing key for SSO state parameters from SESSION_SECRET_KEY."""
    session_key = os.getenv("SESSION_SECRET_KEY", "")
    return hashlib.sha256(f"sso-state-{session_key}".encode()).digest()


def create_signed_state(
    org_id: str,
    nonce: str,
    return_to: str = "/dashboard",
) -> str:
    """Create a signed, base64url-encoded state parameter.

    The state is ``base64url({json}|{hmac_hex})``. Base64url encoding
    ensures special characters (``/``, ``?``, ``=``) survive the
    round-trip through any OIDC IdP without re-encoding issues.
    """
    from base64 import urlsafe_b64encode

    payload = {
        "org_id": org_id,
        "nonce": nonce,
        "return_to": return_to,
        "ts": int(time.time()),
    }
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    key = _get_state_signing_key()
    sig = hmac.new(key, data.encode(), hashlib.sha256).hexdigest()
    raw = f"{data}|{sig}"
    return urlsafe_b64encode(raw.encode()).decode()


def verify_signed_state(state: str) -> dict:
    """Verify and decode a base64url-encoded signed state parameter.

    Returns the payload dict. Raises ValueError on invalid/expired state.
    Uses constant-time comparison to prevent timing attacks.
    """
    from base64 import urlsafe_b64decode

    try:
        # Add padding if needed (base64url may strip trailing '=')
        padded = state + "=" * (-len(state) % 4)
        raw = urlsafe_b64decode(padded).decode()
    except Exception:
        raise ValueError("Invalid state encoding")

    if "|" not in raw:
        raise ValueError("Invalid state format")

    data, sig = raw.rsplit("|", 1)
    key = _get_state_signing_key()
    expected_sig = hmac.new(key, data.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Invalid state signature")

    payload = json.loads(data)

    ts = payload.get("ts", 0)
    if time.time() - ts > STATE_MAX_AGE_SECONDS:
        raise ValueError("State parameter expired")

    return payload


class OIDCProvider(AuthProvider):
    """Generic OIDC provider instantiated per-request with org-specific config.

    All outbound HTTP is routed through SSOHttpClient for SSRF protection.
    PKCE (S256) is mandatory for all flows.
    """

    def __init__(self, sso_config: SSOConfig):
        self._config = sso_config
        self._http = SSOHttpClient()

    @property
    def name(self) -> str:
        return "oidc"

    @property
    def display_name(self) -> str:
        return "SSO"

    @property
    def is_enabled(self) -> bool:
        return self._config.enabled

    @property
    def is_oauth(self) -> bool:
        return True

    async def _get_oidc_metadata(self) -> dict:
        """Fetch and cache OIDC discovery metadata for the issuer."""
        issuer = self._config.issuer_url
        now = time.time()

        cached = _OIDC_METADATA_CACHE.get(issuer)
        if cached and (now - cached[1]) < METADATA_TTL:
            return cached[0]

        async with _CACHE_LOCK:
            # Double-check after acquiring lock (another coroutine may have filled it)
            cached = _OIDC_METADATA_CACHE.get(issuer)
            if cached and (now - cached[1]) < METADATA_TTL:
                return cached[0]

            discovery_url = f"{issuer}/.well-known/openid-configuration"
            try:
                resp = await self._http.get(discovery_url)
                resp.raise_for_status()
                metadata = resp.json()
            except SSRFError:
                raise
            except Exception as e:
                logger.error(
                    "OIDC discovery failed for %s: %s", issuer, type(e).__name__
                )
                raise ValueError(f"OIDC discovery failed for issuer: {issuer}")

            _OIDC_METADATA_CACHE[issuer] = (metadata, now)
            return metadata

    async def _get_jwks(self, force_refresh: bool = False) -> dict:
        """Fetch and cache JWKS for the issuer with refresh-on-failure and cooldown."""
        issuer = self._config.issuer_url
        now = time.time()

        if not force_refresh:
            cached = _JWKS_CACHE.get(issuer)
            if cached and (now - cached[1]) < JWKS_TTL:
                return cached[0]

        async with _CACHE_LOCK:
            # Double-check after acquiring lock
            if not force_refresh:
                cached = _JWKS_CACHE.get(issuer)
                if cached and (now - cached[1]) < JWKS_TTL:
                    return cached[0]

            if force_refresh:
                last_refresh = _JWKS_REFRESH_COOLDOWN.get(issuer, 0)
                if now - last_refresh < JWKS_REFRESH_COOLDOWN_SECONDS:
                    logger.warning(
                        "JWKS refresh cooldown active for %s, using cached keys",
                        issuer,
                    )
                    cached = _JWKS_CACHE.get(issuer)
                    if cached:
                        return cached[0]
                    raise ValueError(
                        "No cached JWKS available and refresh is on cooldown"
                    )

            metadata = await self._get_oidc_metadata()
            jwks_uri = metadata.get("jwks_uri")
            if not jwks_uri:
                raise ValueError("OIDC metadata missing jwks_uri")

            validate_endpoint_origin(jwks_uri, issuer)

            try:
                resp = await self._http.get(jwks_uri)
                resp.raise_for_status()
                jwks = resp.json()
            except SSRFError:
                raise
            except Exception as e:
                logger.error(
                    "JWKS fetch failed for %s: %s", issuer, type(e).__name__
                )
                raise ValueError(f"JWKS fetch failed for issuer: {issuer}")

            _JWKS_CACHE[issuer] = (jwks, now)
            if force_refresh:
                _JWKS_REFRESH_COOLDOWN[issuer] = now

            return jwks

    def _validate_id_token(self, id_token: str, jwks: dict, nonce: str) -> dict:
        """Validate an ID token against the issuer's JWKS.

        Checks: signature, exp, iat (with clock skew), iss, aud, nonce.
        """
        from jwt import PyJWKClient

        # Build a PyJWKClient from the cached JWKS data
        jwk_client = PyJWKClient("")
        jwk_client.fetch_data = lambda: jwks  # type: ignore[assignment]

        try:
            header = pyjwt.get_unverified_header(id_token)
            kid = header.get("kid")

            signing_key = None
            for key_data in jwks.get("keys", []):
                if key_data.get("kid") == kid or kid is None:
                    from jwt.algorithms import RSAAlgorithm

                    signing_key = RSAAlgorithm.from_jwk(key_data)
                    break

            if signing_key is None:
                raise ValueError("No matching key found in JWKS")

            claims = pyjwt.decode(
                id_token,
                signing_key,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384"],
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
                audience=self._config.client_id,
                issuer=self._config.issuer_url,
                leeway=CLOCK_SKEW_SECONDS,
            )
        except pyjwt.InvalidTokenError as e:
            raise ValueError(f"ID token validation failed: {e}")

        if nonce and claims.get("nonce") != nonce:
            raise ValueError("ID token nonce mismatch")

        return claims

    async def get_authorization_url(
        self,
        request: Any,
        redirect_uri: str,
        org_id: str = "",
        code_verifier: str = "",
        code_challenge: str = "",
        nonce: str = "",
        return_to: str = "/dashboard",
    ) -> str:
        """Build the IdP authorization URL with PKCE and signed state."""
        if not self.is_enabled:
            raise ValueError("SSO is not enabled for this organization")

        metadata = await self._get_oidc_metadata()
        auth_endpoint = metadata.get("authorization_endpoint")
        if not auth_endpoint:
            raise ValueError("OIDC metadata missing authorization_endpoint")

        validate_endpoint_origin(auth_endpoint, self._config.issuer_url)

        state = create_signed_state(org_id, nonce, return_to)

        params = {
            "response_type": "code",
            "client_id": self._config.client_id,
            "redirect_uri": redirect_uri,
            "scope": self._config.scopes,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        return f"{auth_endpoint}?{urlencode(params)}"

    async def authenticate(self, request: Any, **kwargs) -> AuthUser:
        """Exchange auth code for tokens and validate the ID token.

        Expected kwargs: code, code_verifier, nonce, redirect_uri
        """
        code = kwargs.get("code", "")
        code_verifier = kwargs.get("code_verifier", "")
        nonce = kwargs.get("nonce", "")
        redirect_uri = kwargs.get("redirect_uri", "")

        if not code:
            raise ValueError("Authorization code is required")

        metadata = await self._get_oidc_metadata()
        token_endpoint = metadata.get("token_endpoint")
        if not token_endpoint:
            raise ValueError("OIDC metadata missing token_endpoint")

        validate_endpoint_origin(token_endpoint, self._config.issuer_url)

        # Exchange code for tokens with PKCE verifier
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self._config.client_id,
            "client_secret": self._config.get_secret_value(),
            "code_verifier": code_verifier,
        }

        try:
            resp = await self._http.post(token_endpoint, data=token_data)
            resp.raise_for_status()
            token_response = resp.json()
        except SSRFError:
            raise
        except Exception as e:
            logger.error("Token exchange failed: %s", type(e).__name__)
            raise ValueError("Token exchange failed")

        id_token_str = token_response.get("id_token")
        if not id_token_str:
            raise ValueError("Token response missing id_token")

        # Validate ID token with JWKS (retry once on key mismatch)
        jwks = await self._get_jwks()
        try:
            claims = self._validate_id_token(id_token_str, jwks, nonce)
        except ValueError:
            # Key rotation: refresh JWKS and retry once
            jwks = await self._get_jwks(force_refresh=True)
            claims = self._validate_id_token(id_token_str, jwks, nonce)

        email = claims.get("email")
        if not email:
            userinfo_endpoint = metadata.get("userinfo_endpoint")
            if userinfo_endpoint:
                access_token = token_response.get("access_token", "")
                try:
                    ui_resp = await self._http.get(
                        userinfo_endpoint,
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    ui_resp.raise_for_status()
                    userinfo = ui_resp.json()
                    email = userinfo.get("email")
                except Exception:
                    pass

        if not email:
            raise ValueError("Could not determine user email from IdP")

        logger.info(
            "SSO OIDC authentication successful: provider=%s, org_config_issuer=%s",
            "oidc",
            self._config.issuer_url,
        )

        return AuthUser(
            provider_type=AuthProviderType.OIDC,
            external_id=claims.get("sub", ""),
            email=email,
            name=claims.get("name"),
            given_name=claims.get("given_name"),
            family_name=claims.get("family_name"),
            picture=claims.get("picture"),
            raw_data={
                k: v
                for k, v in claims.items()
                if k not in ("at_hash", "c_hash")
            },
        )
