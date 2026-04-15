"""Tests for SSOConfig Pydantic validation."""

import os

import pytest
from pydantic import SecretStr


class TestSSOConfigValidation:
    """Test issuer_url, provider_type, domain, and auth method validation."""

    def test_valid_https_issuer(self):
        from rhesis.backend.app.schemas.sso_config import SSOConfig

        config = SSOConfig(
            issuer_url="https://idp.example.com/realms/test",
            client_id="my-client",
            client_secret=SecretStr("my-secret"),
        )
        assert config.issuer_url == "https://idp.example.com/realms/test"

    def test_http_issuer_rejected_in_production(self, monkeypatch):
        from rhesis.backend.app.schemas.sso_config import SSOConfig

        monkeypatch.setenv("ENVIRONMENT", "production")

        with pytest.raises(ValueError, match="HTTPS"):
            SSOConfig(
                issuer_url="http://insecure-idp.example.com",
                client_id="my-client",
                client_secret=SecretStr("my-secret"),
            )

    def test_http_localhost_allowed_in_local(self, monkeypatch):
        from rhesis.backend.app.schemas.sso_config import SSOConfig

        monkeypatch.setenv("ENVIRONMENT", "local")

        config = SSOConfig(
            issuer_url="http://localhost:8080/realms/test",
            client_id="my-client",
            client_secret=SecretStr("my-secret"),
        )
        assert "localhost" in config.issuer_url

    def test_metadata_service_blocked(self):
        from rhesis.backend.app.schemas.sso_config import SSOConfig

        with pytest.raises(ValueError, match="metadata"):
            SSOConfig(
                issuer_url="https://metadata.google.internal/computeMetadata",
                client_id="my-client",
                client_secret=SecretStr("my-secret"),
            )

    def test_private_ip_blocked(self):
        from rhesis.backend.app.schemas.sso_config import SSOConfig

        with pytest.raises(ValueError, match="private"):
            SSOConfig(
                issuer_url="https://10.0.0.1/realms/test",
                client_id="my-client",
                client_secret=SecretStr("my-secret"),
            )

    def test_trailing_slash_stripped(self):
        from rhesis.backend.app.schemas.sso_config import SSOConfig

        config = SSOConfig(
            issuer_url="https://idp.example.com/realms/test/",
            client_id="my-client",
            client_secret=SecretStr("my-secret"),
        )
        assert not config.issuer_url.endswith("/")

    def test_invalid_provider_type_rejected(self):
        from rhesis.backend.app.schemas.sso_config import SSOConfig

        with pytest.raises(ValueError, match="Unsupported provider_type"):
            SSOConfig(
                issuer_url="https://idp.example.com",
                client_id="my-client",
                client_secret=SecretStr("my-secret"),
                provider_type="saml",
            )

    def test_empty_allowed_auth_methods_rejected(self):
        from rhesis.backend.app.schemas.sso_config import SSOConfig

        with pytest.raises(ValueError, match="cannot be empty"):
            SSOConfig(
                issuer_url="https://idp.example.com",
                client_id="my-client",
                client_secret=SecretStr("my-secret"),
                allowed_auth_methods=[],
            )

    def test_unknown_auth_method_rejected(self):
        from rhesis.backend.app.schemas.sso_config import SSOConfig

        with pytest.raises(ValueError, match="Unknown auth method"):
            SSOConfig(
                issuer_url="https://idp.example.com",
                client_id="my-client",
                client_secret=SecretStr("my-secret"),
                allowed_auth_methods=["sso", "magic_link"],
            )

    def test_domains_normalized(self):
        from rhesis.backend.app.schemas.sso_config import SSOConfig

        config = SSOConfig(
            issuer_url="https://idp.example.com",
            client_id="my-client",
            client_secret=SecretStr("my-secret"),
            allowed_domains=[" .EXAMPLE.COM ", "Test.Org"],
        )
        assert config.allowed_domains == ["example.com", "test.org"]

    def test_masked_dict_hides_secret(self):
        from rhesis.backend.app.schemas.sso_config import SSOConfig

        config = SSOConfig(
            issuer_url="https://idp.example.com",
            client_id="my-client",
            client_secret=SecretStr("super-secret-value"),
        )
        masked = config.masked_dict()
        assert masked["client_secret"] == "****alue"
        assert "super-secret-value" not in str(masked)

    def test_non_443_port_rejected_in_production(self, monkeypatch):
        from rhesis.backend.app.schemas.sso_config import SSOConfig

        monkeypatch.setenv("ENVIRONMENT", "production")

        with pytest.raises(ValueError, match="port 443"):
            SSOConfig(
                issuer_url="https://idp.example.com:8443/realms/test",
                client_id="my-client",
                client_secret=SecretStr("my-secret"),
            )
