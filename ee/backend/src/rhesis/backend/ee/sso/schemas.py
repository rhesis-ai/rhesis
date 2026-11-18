"""Pydantic validation schema for per-organization SSO configuration."""

import ipaddress
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, SecretStr, field_validator

from rhesis.backend.app.auth.url_utils import LOOPBACK_HOSTS
from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.utils.ssrf_http_client import BLOCKED_HOSTNAMES, is_blocked_address


class SSOConfig(BaseModel):
    enabled: bool = False
    provider_type: str = "oidc"
    issuer_url: str
    client_id: str
    client_secret: SecretStr
    scopes: str = "openid email profile"
    auto_provision_users: bool = False
    allowed_domains: Optional[List[str]] = None
    allowed_auth_methods: Optional[List[str]] = None
    allow_insecure_tls: bool = False

    @field_validator("issuer_url")
    @classmethod
    def issuer_must_be_https_and_not_internal(cls, v: str) -> str:
        """HTTPS required; private addresses only when OUTBOUND_ALLOW_PRIVATE_NETWORKS is on."""
        parsed = urlparse(v)
        hostname = parsed.hostname or ""
        settings = get_application_settings()

        if parsed.scheme != "https":
            if not (
                parsed.scheme == "http"
                and hostname.lower() in LOOPBACK_HOSTS
                and settings.is_local_development
            ):
                raise ValueError("issuer_url must use HTTPS")

        if hostname.lower() in BLOCKED_HOSTNAMES:
            raise ValueError("issuer_url cannot point to cloud metadata services")

        try:
            ipaddress.ip_address(hostname)
            is_ip_literal = True
        except ValueError:
            # A hostname: its addresses are checked at connect time by SafeHttpClient.
            is_ip_literal = False
        if is_ip_literal and is_blocked_address(hostname, settings.allow_private_outbound):
            raise ValueError("issuer_url cannot point to private or reserved IP addresses")

        # On-premise IdPs often listen on another port (Keycloak's 8443).
        if not (settings.is_local_development or settings.allow_private_outbound):
            port = parsed.port
            if port is not None and port != 443:
                raise ValueError("issuer_url must use port 443 outside local development")

        return v.rstrip("/")

    @field_validator("provider_type")
    @classmethod
    def valid_provider_type(cls, v: str) -> str:
        if v not in ("oidc",):
            raise ValueError(f"Unsupported provider_type: {v}")
        return v

    @field_validator("allowed_auth_methods")
    @classmethod
    def valid_auth_methods(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            if len(v) == 0:
                raise ValueError(
                    "allowed_auth_methods cannot be empty (would lock all users out)"
                )
            valid = {"sso", "email", "google", "github"}
            for m in v:
                if m not in valid:
                    raise ValueError(f"Unknown auth method: {m}")
        return v

    @field_validator("allowed_domains")
    @classmethod
    def normalize_domains(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Lowercase and strip dots from domain entries."""
        if v is not None:
            return [d.lower().strip().lstrip(".") for d in v if d.strip()]
        return v

    def get_secret_value(self) -> str:
        """Convenience accessor for the plaintext client_secret."""
        return self.client_secret.get_secret_value()

    def masked_dict(self) -> dict:
        """Return config dict with client_secret masked (last 4 chars only).

        Safe for API responses. Never returns the full secret.
        Uses mode="json" so SecretStr is serialized as a string, not an object.
        """
        d = self.model_dump(mode="json")
        secret = self.client_secret.get_secret_value()
        d["client_secret"] = (
            f"****{secret[-4:]}" if len(secret) >= 4 else "****"
        )
        return d
