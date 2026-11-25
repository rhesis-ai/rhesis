"""The identity providers Rhesis knows by name: the one place they are listed.

The protocol is always OIDC; a provider only changes wording, setup hints and
where groups come from. The admin UI reads this catalog from the API and asks
the API which provider an issuer belongs to, so nothing else lists them.
"""

import re
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple
from urllib.parse import urlparse

GENERIC = "oidc"


@dataclass(frozen=True)
class ProviderSpec:
    key: str
    #: Short name used in sentences ("your Okta groups").
    name: str
    #: Full product name.
    title: str
    #: False when the provider never puts groups in the sign-in token.
    supports_groups: bool
    #: How to get a groups claim into the token.
    groups_hint: str
    #: Issuer hosts, as regexes matched against the whole hostname.
    hosts: Tuple[str, ...] = ()
    #: Issuer path, as a regex searched in the path.
    issuer_path: Optional[str] = None
    #: Searched in the discovery document's endpoints, for custom domains.
    endpoint_paths: Tuple[str, ...] = ()


# Order matters: the first match wins, and the UI lists them in this order.
PROVIDERS: Tuple[ProviderSpec, ...] = (
    ProviderSpec(
        key="google",
        name="Google Workspace",
        title="Google Workspace",
        supports_groups=False,
        groups_hint="",
        hosts=(r"accounts\.google\.com",),
    ),
    ProviderSpec(
        key="entra",
        name="Entra ID",
        title="Microsoft Entra ID",
        supports_groups=True,
        groups_hint=(
            "Add a groups claim under Token configuration. Entra sends group object IDs, "
            "so rules match on the ID."
        ),
        hosts=(r"login\.microsoftonline\.com", r".+\.ciamlogin\.com"),
    ),
    ProviderSpec(
        key="keycloak",
        name="Keycloak",
        title="Keycloak",
        supports_groups=True,
        groups_hint=(
            'Add a "Group Membership" mapper to the client (token claim name "groups", '
            'added to the ID token) and keep "Full group path" on. Short names can repeat '
            "under different parent groups."
        ),
        issuer_path=r"/realms/[^/]+/?$",
        endpoint_paths=("/protocol/openid-connect/",),
    ),
    ProviderSpec(
        key="okta",
        name="Okta",
        title="Okta",
        supports_groups=True,
        groups_hint=(
            'Add a "groups" claim with a group filter to the app, or to your authorization server.'
        ),
        hosts=(r".+\.(okta|oktapreview|okta-emea)\.com",),
        endpoint_paths=("/oauth2/v1/", "/v1/authorize"),
    ),
    ProviderSpec(
        key="auth0",
        name="Auth0",
        title="Auth0",
        supports_groups=True,
        groups_hint=(
            "Auth0 sends groups only when an Action adds them, usually under a URL claim "
            "name. Set that name under Advanced."
        ),
        hosts=(r".+\.auth0\.com",),
        endpoint_paths=("/oauth/token",),
    ),
    ProviderSpec(
        key=GENERIC,
        name="identity provider",
        title="Other OIDC provider",
        supports_groups=True,
        groups_hint=(
            "Set your provider up to send the groups claim in the ID token or at the "
            "userinfo endpoint."
        ),
    ),
)

PROVIDER_KEYS = frozenset(p.key for p in PROVIDERS)


def _matches(spec: ProviderSpec, host: str, path: str, endpoints: str) -> bool:
    if any(re.fullmatch(h, host) for h in spec.hosts):
        return True
    if spec.issuer_path and re.search(spec.issuer_path, path):
        return True
    return any(p in endpoints for p in spec.endpoint_paths)


def detect_provider(issuer: str, metadata: Optional[Mapping] = None) -> Optional[str]:
    """The provider key for an issuer, or None while it isn't a URL."""
    parsed = urlparse(issuer.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    host = parsed.hostname.lower()
    endpoints = " ".join(
        str((metadata or {}).get(k, "")) for k in ("authorization_endpoint", "token_endpoint")
    )
    for spec in PROVIDERS:
        if spec.key != GENERIC and _matches(spec, host, parsed.path, endpoints):
            return spec.key
    return GENERIC


def catalog() -> list:
    """The providers as the admin UI shows them."""
    return [
        {
            "key": p.key,
            "name": p.name,
            "title": p.title,
            "supports_groups": p.supports_groups,
            "groups_hint": p.groups_hint,
        }
        for p in PROVIDERS
    ]
