"""Tests for SSO router helpers and endpoint logic.

Pure unit tests that mock DB and encryption -- no network or Postgres needed.
"""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from rhesis.backend.app.config.settings import get_application_settings


@pytest.fixture(autouse=True)
def clear_application_settings_cache():
    get_application_settings.cache_clear()
    yield
    get_application_settings.cache_clear()


# ---------------------------------------------------------------------------
# _validate_return_to
# ---------------------------------------------------------------------------

class TestValidateReturnTo:

    def _validate(self, val):
        from rhesis.backend.ee.sso.router import _validate_return_to
        return _validate_return_to(val)

    def test_none_defaults_to_dashboard(self):
        assert self._validate(None) == "/architect"

    def test_empty_defaults_to_dashboard(self):
        assert self._validate("") == "/architect"

    def test_valid_relative_path(self):
        assert self._validate("/settings") == "/settings"

    def test_valid_nested_path(self):
        assert self._validate("/org/settings/sso") == "/org/settings/sso"

    def test_absolute_http_blocked(self):
        assert self._validate("http://evil.com") == "/architect"

    def test_absolute_https_blocked(self):
        assert self._validate("https://evil.com/foo") == "/architect"

    def test_protocol_relative_blocked(self):
        assert self._validate("//evil.com") == "/architect"

    def test_javascript_scheme_blocked(self):
        assert self._validate("javascript:alert(1)") == "/architect"

    def test_data_scheme_blocked(self):
        assert self._validate("data:text/html,<h1>x</h1>") == "/architect"

    def test_backslash_blocked(self):
        assert self._validate("\\\\evil.com") == "/architect"

    def test_encoded_double_slash_blocked(self):
        assert self._validate("/%2f/evil.com") == "/architect"

    def test_double_encoded_blocked(self):
        assert self._validate("/%252f%252fevil.com") == "/architect"


# ---------------------------------------------------------------------------
# _generate_pkce
# ---------------------------------------------------------------------------

class TestGeneratePkce:

    def test_returns_verifier_and_challenge(self):
        from rhesis.backend.ee.sso.router import _generate_pkce

        verifier, challenge = _generate_pkce()
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) > 40
        assert len(challenge) > 20

    def test_each_call_unique(self):
        from rhesis.backend.ee.sso.router import _generate_pkce

        a = _generate_pkce()
        b = _generate_pkce()
        assert a[0] != b[0]
        assert a[1] != b[1]


# ---------------------------------------------------------------------------
# check_sso_available
# ---------------------------------------------------------------------------

class TestCheckSSOAvailable:

    def test_available_with_encryption_key(self):
        from rhesis.backend.ee.sso.router import check_sso_available
        assert check_sso_available() is True

    @patch(
        "rhesis.backend.ee.sso.encryption.is_sso_encryption_available",
        return_value=False,
    )
    def test_unavailable_without_encryption(self, _mock):
        from rhesis.backend.ee.sso.router import check_sso_available
        assert check_sso_available() is False


# ---------------------------------------------------------------------------
# SSOConfigRequest with slug
# ---------------------------------------------------------------------------

class TestSSOConfigRequestSlug:

    def test_slug_included(self):
        from rhesis.backend.ee.sso.router import SSOConfigRequest

        req = SSOConfigRequest(
            issuer_url="https://idp.example.com",
            client_id="test",
            slug="acme-corp",
        )
        assert req.slug == "acme-corp"

    def test_slug_defaults_to_none(self):
        from rhesis.backend.ee.sso.router import SSOConfigRequest

        req = SSOConfigRequest(
            issuer_url="https://idp.example.com",
            client_id="test",
        )
        assert req.slug is None


# ---------------------------------------------------------------------------
# _get_sso_config - decryption and parsing
# ---------------------------------------------------------------------------

class TestGetSSOConfig:

    def test_no_config_returns_none(self):
        from rhesis.backend.ee.sso.router import _get_sso_config

        org = SimpleNamespace(id=uuid4(), sso_config=None)
        assert _get_sso_config(org) is None

    def test_empty_dict_returns_none(self):
        from rhesis.backend.ee.sso.router import _get_sso_config

        org = SimpleNamespace(id=uuid4(), sso_config={})
        assert _get_sso_config(org) is None

    def test_valid_config_with_encrypted_secret(self):
        from rhesis.backend.ee.sso.encryption import sso_encrypt
        from rhesis.backend.ee.sso.router import _get_sso_config

        encrypted = sso_encrypt("my-secret")
        org = SimpleNamespace(
            id=uuid4(),
            sso_config={
                "enabled": True,
                "provider_type": "oidc",
                "issuer_url": "https://idp.example.com",
                "client_id": "my-client",
                "client_secret": encrypted,
                "scopes": "openid email profile",
                "auto_provision_users": False,
                "allowed_domains": None,
                "allowed_auth_methods": None,
            },
        )
        config = _get_sso_config(org)
        assert config is not None
        assert config.client_id == "my-client"
        assert config.get_secret_value() == "my-secret"

    def test_plaintext_secret_fallback_in_dev(self, monkeypatch):
        from rhesis.backend.ee.sso.router import _get_sso_config

        monkeypatch.setenv("BACKEND_ENV", "development")
        get_application_settings.cache_clear()

        org = SimpleNamespace(
            id=uuid4(),
            sso_config={
                "enabled": True,
                "provider_type": "oidc",
                "issuer_url": "http://localhost:8180/realms/dev",
                "client_id": "dev-client",
                "client_secret": "plain-text-secret",
                "scopes": "openid email profile",
                "auto_provision_users": False,
            },
        )
        config = _get_sso_config(org)
        assert config is not None
        assert config.get_secret_value() == "plain-text-secret"

    def test_corrupt_config_returns_none(self):
        from rhesis.backend.ee.sso.router import _get_sso_config

        org = SimpleNamespace(
            id=uuid4(),
            sso_config={"issuer_url": "not-valid", "client_id": "x"},
        )
        assert _get_sso_config(org) is None
