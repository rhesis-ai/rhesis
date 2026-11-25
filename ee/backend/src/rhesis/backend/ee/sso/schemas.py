"""Pydantic validation schema for per-organization SSO configuration."""

import ipaddress
from typing import List, Literal, Optional, Union
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

from rhesis.backend.app.auth.url_utils import LOOPBACK_HOSTS
from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.utils.ssrf_http_client import BLOCKED_HOSTNAMES, is_blocked_address

#: A claim name, or path segments for a nested claim (``["realm_access", "roles"]``).
#: Segments are never split on dots: Auth0 claim names are URLs.
ClaimPath = Union[str, List[str]]

MAX_RULES = 200
MAX_PROJECTS_PER_RULE = 50
MAX_CLAIM_DEPTH = 4


#: Set on the sign-in claims when the groups claim could not be fetched.
GROUPS_UNAVAILABLE = "_rhesis_groups_unavailable"


class ProjectGrant(BaseModel):
    project_id: UUID
    role_id: UUID


class MappingRule(BaseModel):
    """People whose token carries ``group`` get ``role_id`` and the project roles."""

    group: str = Field(min_length=1, max_length=256)
    role_id: Optional[UUID] = None
    projects: List[ProjectGrant] = Field(default_factory=list, max_length=MAX_PROJECTS_PER_RULE)

    @model_validator(mode="after")
    def grants_something(self) -> "MappingRule":
        if self.role_id is None and not self.projects:
            raise ValueError(f"Group {self.group!r} needs an organization role or a project")
        seen = [p.project_id for p in self.projects]
        if len(seen) != len(set(seen)):
            raise ValueError(f"Group {self.group!r} lists the same project twice")
        return self


class RoleMapping(BaseModel):
    enabled: bool = False
    claim: ClaimPath = "groups"
    apply: Literal["every_sign_in", "on_create"] = "every_sign_in"
    rules: List[MappingRule] = Field(default_factory=list, max_length=MAX_RULES)
    #: For people in no mapped group: leave their role, set one, or refuse sign-in.
    everyone_else: Literal["keep", "Viewer", "None", "block"] = "keep"

    @field_validator("claim")
    @classmethod
    def valid_claim(cls, v: ClaimPath) -> ClaimPath:
        segments = [v] if isinstance(v, str) else v
        if not 1 <= len(segments) <= MAX_CLAIM_DEPTH:
            raise ValueError(f"claim must have 1 to {MAX_CLAIM_DEPTH} segments")
        if any(not s.strip() or len(s) > 256 for s in segments):
            raise ValueError("claim segments must be non-empty")
        return v

    @field_validator("rules")
    @classmethod
    def unique_groups(cls, v: List[MappingRule]) -> List[MappingRule]:
        groups = [r.group for r in v]
        dupes = sorted({g for g in groups if groups.count(g) > 1})
        if dupes:
            raise ValueError(f"Each group can appear once: {', '.join(dupes)}")
        return v


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
    #: A key from ``providers.PROVIDERS``; only a hint, the protocol is always OIDC.
    provider: str = "oidc"
    role_mapping: Optional[RoleMapping] = None

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

    @field_validator("provider")
    @classmethod
    def known_provider(cls, v: str) -> str:
        from rhesis.backend.ee.sso.providers import PROVIDER_KEYS

        if v not in PROVIDER_KEYS:
            raise ValueError(f"Unknown provider: {v}")
        return v

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
                raise ValueError("allowed_auth_methods cannot be empty (would lock all users out)")
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
        d["client_secret"] = f"****{secret[-4:]}" if len(secret) >= 4 else "****"
        return d
