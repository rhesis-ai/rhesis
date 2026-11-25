"""The identity provider registry: detection from the issuer and the catalog (#3189)."""

import pytest

from rhesis.backend.ee.sso.providers import PROVIDER_KEYS, catalog, detect_provider


@pytest.mark.parametrize(
    "issuer,expected",
    [
        ("https://keycloak.acme.com/realms/acme", "keycloak"),
        ("http://localhost:8320/realms/acme/", "keycloak"),
        ("https://login.microsoftonline.com/tenant/v2.0", "entra"),
        ("https://acme.ciamlogin.com/tenant/v2.0", "entra"),
        ("https://acme.okta.com", "okta"),
        ("https://acme.oktapreview.com/oauth2/default", "okta"),
        ("https://acme.eu.auth0.com/", "auth0"),
        ("https://accounts.google.com", "google"),
        ("https://sso.acme.com", "oidc"),
        # Lookalikes must not pass for the real thing.
        ("https://evil.com/okta.com", "oidc"),
        ("https://login.microsoftonline.com.evil.com/x", "oidc"),
        ("https://accounts.google.com.evil.com", "oidc"),
        ("https://okta.com", "oidc"),
    ],
)
def test_detect_from_issuer(issuer, expected):
    assert detect_provider(issuer) == expected


@pytest.mark.parametrize("issuer", ["", "keycloak", "ftp://x.com", "https://"])
def test_not_a_url(issuer):
    assert detect_provider(issuer) is None


@pytest.mark.parametrize(
    "endpoint,expected",
    [
        ("https://sso.acme.com/realms/acme/protocol/openid-connect/auth", "keycloak"),
        ("https://sso.acme.com/oauth2/v1/authorize", "okta"),
        ("https://sso.acme.com/oauth/token", "auth0"),
        ("https://sso.acme.com/authorize", "oidc"),
    ],
)
def test_custom_domain_from_discovery(endpoint, expected):
    meta = {"authorization_endpoint": endpoint, "token_endpoint": endpoint}
    assert detect_provider("https://sso.acme.com", meta) == expected


def test_catalog_lists_every_provider_once():
    keys = [p["key"] for p in catalog()]
    assert set(keys) == PROVIDER_KEYS
    assert len(keys) == len(set(keys))
    assert keys[-1] == "oidc"
    google = next(p for p in catalog() if p["key"] == "google")
    assert google["supports_groups"] is False
