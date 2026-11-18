"""Tests for SSRF-safe HTTP client."""

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import pytest

from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.utils.ssrf_http_client import (
    SafeHttpClient,
    SSRFError,
    validate_endpoint_origin,
    validate_jwks_uri_origin,
    validate_url_safety,
)

#: A public address, in the shape getaddrinfo returns. Tests that need a
#: hostname to resolve use this instead of asking a resolver: what is under
#: test is the blocklist, not DNS, and a suite that reaches the internet fails
#: in an air-gapped build for a reason that has nothing to do with the code.
PUBLIC_ADDR_INFO = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


@pytest.fixture(autouse=True)
def clear_application_settings_cache():
    get_application_settings.cache_clear()
    yield
    get_application_settings.cache_clear()


@pytest.fixture
def private_targets_off(monkeypatch):
    monkeypatch.setenv("OUTBOUND_ALLOW_PRIVATE_NETWORKS", "false")
    get_application_settings.cache_clear()


@pytest.fixture
def private_targets_on(monkeypatch):
    monkeypatch.setenv("BACKEND_ENV", "production")
    monkeypatch.setenv("OUTBOUND_ALLOW_PRIVATE_NETWORKS", "true")
    get_application_settings.cache_clear()


class TestValidateUrlSafety:
    """Test URL safety validation for SSRF protection."""

    def test_public_hostname_allowed(self):
        with patch(
            "rhesis.backend.app.utils.ssrf_http_client.socket.getaddrinfo",
            return_value=PUBLIC_ADDR_INFO,
        ):
            validate_url_safety("https://accounts.google.com/.well-known/openid-configuration")

    def test_no_hostname_blocked(self):
        with pytest.raises(SSRFError, match="no hostname"):
            validate_url_safety("https://")

    def test_metadata_hostname_blocked(self):
        with pytest.raises(SSRFError, match="Blocked hostname"):
            validate_url_safety("https://metadata.google.internal/path")

    def test_localhost_blocked_in_production(self, monkeypatch):
        monkeypatch.setenv("BACKEND_ENV", "production")
        get_application_settings.cache_clear()

        with pytest.raises(SSRFError):
            validate_url_safety("https://127.0.0.1/path")

    def test_localhost_name_blocked_in_production(self, monkeypatch):
        monkeypatch.setenv("BACKEND_ENV", "production")
        get_application_settings.cache_clear()

        with pytest.raises(SSRFError):
            validate_url_safety("https://localhost/path")

    def test_localhost_allowed_in_dev(self, monkeypatch):
        monkeypatch.setenv("BACKEND_ENV", "development")
        get_application_settings.cache_clear()

        validate_url_safety("http://localhost:8180/realms/dev")

    def test_localhost_ip_allowed_in_local(self, monkeypatch):
        monkeypatch.setenv("BACKEND_ENV", "local")
        get_application_settings.cache_clear()

        validate_url_safety("http://127.0.0.1:8180/realms/dev")

    def test_private_10_blocked(self, private_targets_off):
        with pytest.raises(SSRFError):
            validate_url_safety("https://10.0.0.1/path")

    def test_private_172_blocked(self, private_targets_off):
        with pytest.raises(SSRFError):
            validate_url_safety("https://172.16.0.1/path")

    def test_private_192_blocked(self, private_targets_off):
        with pytest.raises(SSRFError):
            validate_url_safety("https://192.168.1.1/path")

    def test_link_local_blocked(self):
        with pytest.raises(SSRFError):
            validate_url_safety("https://169.254.169.254/latest/meta-data")

    def test_this_network_zero_blocked(self, private_targets_off):
        with pytest.raises(SSRFError):
            validate_url_safety("https://0.0.0.0/path")

    def test_cgnat_blocked(self, private_targets_off):
        with pytest.raises(SSRFError):
            validate_url_safety("https://100.64.0.1/path")

    def test_ietf_reserved_blocked(self, private_targets_off):
        with pytest.raises(SSRFError):
            validate_url_safety("https://192.0.0.1/path")

    def test_benchmarking_blocked(self, private_targets_off):
        with pytest.raises(SSRFError):
            validate_url_safety("https://198.18.0.1/path")

    def test_error_message_does_not_leak_resolved_ip(self, private_targets_off):
        """The exception message says 'blocked address' without the actual IP."""
        with pytest.raises(SSRFError, match="blocked address"):
            validate_url_safety("https://10.0.0.1/path")


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


def _resolve_to(host: str, ip: str):
    """Resolve ``host`` to ``ip``; anything else goes to the real resolver."""
    real = socket.getaddrinfo

    def resolve(name, port, *args, **kwargs):
        if name == host:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 0))]
        return real(name, port, *args, **kwargs)

    return patch(
        "rhesis.backend.app.utils.ssrf_http_client.socket.getaddrinfo", side_effect=resolve
    )


@pytest.fixture
def discovery_server():
    """A fake OIDC discovery document served on loopback."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"issuer": "x", "jwks_uri": "x"}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_port
    server.shutdown()


class TestSafeHttpClientPrivateNetworks:
    """GitHub issue #3188: an on-premise IdP whose name resolves to a private address."""

    IDP = "keycloak.corp.test"

    async def test_private_idp_blocked_when_setting_off(
        self, private_targets_off, discovery_server
    ):
        with _resolve_to(self.IDP, "127.0.0.1"), pytest.raises(SSRFError):
            await SafeHttpClient().get(f"http://{self.IDP}:{discovery_server}/.well-known")

    async def test_private_idp_reached_when_setting_on(self, private_targets_on, discovery_server):
        # Goes over a real socket, so the connect-time check in the transport runs too.
        with _resolve_to(self.IDP, "127.0.0.1"):
            resp = await SafeHttpClient().get(f"http://{self.IDP}:{discovery_server}/.well-known")
        assert resp.status_code == 200
        assert resp.json()["jwks_uri"] == "x"

    @pytest.mark.parametrize("ip", ["10.0.0.5", "172.16.3.4", "192.168.1.1", "100.64.0.1"])
    def test_private_ranges_pass_when_setting_on(self, private_targets_on, ip):
        with _resolve_to(self.IDP, ip):
            validate_url_safety(f"https://{self.IDP}/realms/acme")

    @pytest.mark.parametrize("ip", ["169.254.169.254", "168.63.129.16", "100.100.100.200"])
    def test_metadata_still_blocked_when_setting_on(self, private_targets_on, ip):
        with _resolve_to(self.IDP, ip), pytest.raises(SSRFError):
            validate_url_safety(f"https://{self.IDP}/realms/acme")

    def test_tls_still_verified_for_private_idp(self, private_targets_on):
        with _resolve_to(self.IDP, "10.0.0.5"):
            assert SafeHttpClient()._verify(f"https://{self.IDP}/") is True
            assert SafeHttpClient(verify_ssl=False)._verify(f"https://{self.IDP}/") is False
