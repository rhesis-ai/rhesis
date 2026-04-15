"""Tests for SSRF-safe HTTP client."""

import pytest

from rhesis.backend.app.auth.sso_http_client import (
    SSRFError,
    _pin_url_to_ip,
    _resolve_and_validate,
    validate_endpoint_origin,
    validate_jwks_uri_origin,
    validate_url_safety,
)


class TestValidateUrlSafety:
    """Test URL safety validation for SSRF protection."""

    def test_public_hostname_allowed(self):
        # google.com resolves to a public IP in CI and local environments
        validate_url_safety("https://accounts.google.com/.well-known/openid-configuration")

    def test_no_hostname_blocked(self):
        with pytest.raises(SSRFError, match="no hostname"):
            validate_url_safety("https://")

    def test_metadata_hostname_blocked(self):
        with pytest.raises(SSRFError, match="Blocked hostname"):
            validate_url_safety("https://metadata.google.internal/path")

    def test_localhost_blocked(self):
        with pytest.raises(SSRFError):
            validate_url_safety("https://127.0.0.1/path")

    def test_private_10_blocked(self):
        with pytest.raises(SSRFError):
            validate_url_safety("https://10.0.0.1/path")

    def test_private_172_blocked(self):
        with pytest.raises(SSRFError):
            validate_url_safety("https://172.16.0.1/path")

    def test_private_192_blocked(self):
        with pytest.raises(SSRFError):
            validate_url_safety("https://192.168.1.1/path")

    def test_link_local_blocked(self):
        with pytest.raises(SSRFError):
            validate_url_safety("https://169.254.169.254/latest/meta-data")

    def test_this_network_zero_blocked(self):
        with pytest.raises(SSRFError):
            validate_url_safety("https://0.0.0.0/path")

    def test_cgnat_blocked(self):
        with pytest.raises(SSRFError):
            validate_url_safety("https://100.64.0.1/path")

    def test_ietf_reserved_blocked(self):
        with pytest.raises(SSRFError):
            validate_url_safety("https://192.0.0.1/path")

    def test_benchmarking_blocked(self):
        with pytest.raises(SSRFError):
            validate_url_safety("https://198.18.0.1/path")

    def test_error_message_does_not_leak_resolved_ip(self):
        """The exception message says 'blocked address' without the actual IP."""
        with pytest.raises(SSRFError, match="blocked address"):
            validate_url_safety("https://10.0.0.1/path")


class TestPinUrlToIp:
    """Test that URL pinning produces correct results."""

    def test_pin_replaces_hostname(self):
        import socket

        addr_infos = socket.getaddrinfo(
            "accounts.google.com", None, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
        pinned, original = _pin_url_to_ip(
            "https://accounts.google.com/path?q=1", addr_infos
        )
        assert original == "accounts.google.com"
        assert "accounts.google.com" not in pinned
        assert "/path?q=1" in pinned

    def test_pin_preserves_port(self):
        import socket

        fake_addr = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]
        pinned, original = _pin_url_to_ip(
            "https://example.com:8443/path", fake_addr
        )
        assert ":8443" in pinned
        assert original == "example.com"


class TestValidateEndpointOrigin:
    """Test endpoint origin validation (generalized from JWKS-only)."""

    def test_same_origin_allowed(self):
        validate_endpoint_origin(
            "https://idp.example.com/certs",
            "https://idp.example.com/realms/test",
        )

    def test_different_host_blocked(self):
        with pytest.raises(SSRFError, match="hostname"):
            validate_endpoint_origin(
                "https://attacker.com/fake-jwks",
                "https://idp.example.com/realms/test",
            )

    def test_different_scheme_blocked(self):
        with pytest.raises(SSRFError, match="scheme"):
            validate_endpoint_origin(
                "http://idp.example.com/certs",
                "https://idp.example.com/realms/test",
            )

    def test_javascript_scheme_blocked(self):
        with pytest.raises(SSRFError, match="disallowed scheme"):
            validate_endpoint_origin(
                "javascript:alert(1)",
                "https://idp.example.com/realms/test",
            )

    def test_data_scheme_blocked(self):
        with pytest.raises(SSRFError, match="disallowed scheme"):
            validate_endpoint_origin(
                "data:text/html,<h1>hi</h1>",
                "https://idp.example.com/realms/test",
            )

    def test_alias_works(self):
        """validate_jwks_uri_origin is an alias for validate_endpoint_origin."""
        validate_jwks_uri_origin(
            "https://idp.example.com/certs",
            "https://idp.example.com/realms/test",
        )
