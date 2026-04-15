"""Pydantic validation schema for per-organization SSO configuration."""

import ipaddress
import os
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, SecretStr, field_validator

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

_BLOCKED_HOSTNAMES = {
    "metadata.google.internal",
    "metadata.internal",
}


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

    @field_validator("issuer_url")
    @classmethod
    def issuer_must_be_https_and_not_internal(cls, v: str) -> str:
        """Validate issuer URL: HTTPS required, no internal/private destinations."""
        is_local = os.getenv("ENVIRONMENT", "").lower() in ("local", "test")

        if not v.startswith("https://"):
            if not (is_local and "localhost" in v):
                raise ValueError("issuer_url must use HTTPS")

        parsed = urlparse(v)
        hostname = parsed.hostname or ""

        if hostname.lower() in _BLOCKED_HOSTNAMES:
            raise ValueError("issuer_url cannot point to cloud metadata services")

        try:
            addr = ipaddress.ip_address(hostname)
            for network in _BLOCKED_NETWORKS:
                if addr in network:
                    raise ValueError(
                        "issuer_url cannot point to private or reserved IP addresses"
                    )
        except ValueError as e:
            if "cannot point to" in str(e):
                raise
            # hostname is not an IP literal -- DNS resolution
            # is validated at connect time by SSOHttpClient

        if not is_local:
            port = parsed.port
            if port is not None and port != 443:
                raise ValueError("issuer_url must use port 443 in production")

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
