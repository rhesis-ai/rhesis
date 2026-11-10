"""Outbound requests to tenant-supplied URLs cannot reach internal addresses.

Every path that sends a request to a URL a tenant controls -- the REST and
WebSocket invokers behind /endpoints/test, invoke, test runs, preflight and the
explorer; the OAuth token request; model ``api_base``; auto-configure -- goes
through the guard in ``app/utils/ssrf_http_client.py``. These tests run with
``OUTBOUND_ALLOW_PRIVATE_NETWORKS`` off, as staging and production do, and
assert that a blocked target is refused before any socket opens.

DNS is faked: what is under test is the address policy, not a resolver.
"""

import asyncio
import re
import socket
from pathlib import Path
from unittest.mock import Mock, patch

import httpcore
import pytest

from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.model import Model
from rhesis.backend.app.services.endpoint.auto_configure import AutoConfigureService
from rhesis.backend.app.services.invokers.auth.manager import AuthenticationManager
from rhesis.backend.app.services.invokers.rest_invoker import RestEndpointInvoker
from rhesis.backend.app.services.invokers.websocket_invoker import WebSocketEndpointInvoker
from rhesis.backend.app.services.model_connection import ModelConnectionService
from rhesis.backend.app.services.tool.url_validation import validate_base_url
from rhesis.backend.app.utils.model_errors import ModelConfigurationError
from rhesis.backend.app.utils.ssrf_http_client import (
    SSRFError,
    guarded_async_client,
    guarded_ws_connect,
    is_blocked_address,
)
from rhesis.backend.app.utils.user_model_utils import _build_configured_model

PUBLIC_IP = "93.184.216.34"

FAKE_DNS = {
    "public.example": PUBLIC_IP,
    "internal.example": "10.0.0.5",
    "mapped.example": "::ffff:169.254.169.254",
}

BLOCKED_HOSTS = [
    "127.0.0.1:8080",
    "169.254.169.254",
    "[::ffff:169.254.169.254]",
    "[::ffff:10.0.0.1]",
    "10.0.0.1",
    "192.168.1.10",
    "100.64.0.1",
    "0.0.0.0:8080",
    "[::1]",
    "[fd00:ec2::254]",
    "[64:ff9b::a9fe:a9fe]",
    "metadata.google.internal",
    "internal.example",
    "mapped.example",
]


def _fake_getaddrinfo(real):
    def resolve(host, port, *args, **kwargs):
        if host in FAKE_DNS:
            ip = FAKE_DNS[host]
            family = socket.AF_INET6 if ":" in ip else socket.AF_INET
            sockaddr = (ip, port or 0, 0, 0) if family == socket.AF_INET6 else (ip, port or 0)
            return [(family, socket.SOCK_STREAM, 6, "", sockaddr)]
        # IP literals, and the test database's own host.
        return real(host, port, *args, **kwargs)

    return resolve


@pytest.fixture(autouse=True)
def strict_egress(monkeypatch):
    """Private targets off, as in staging/production; fake DNS; record any connect."""
    monkeypatch.setenv("BACKEND_ENV", "production")
    monkeypatch.setenv("OUTBOUND_ALLOW_PRIVATE_NETWORKS", "false")
    get_application_settings.cache_clear()
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(socket.getaddrinfo))

    opened: list = []

    async def async_connect(self, host, port, *args, **kwargs):
        opened.append((host, port))
        raise httpcore.ConnectError("test: connect not allowed")

    def sync_connect(self, host, port, *args, **kwargs):
        opened.append((host, port))
        raise httpcore.ConnectError("test: connect not allowed")

    async def loop_connect(self, *args, **kwargs):
        opened.append((kwargs.get("host"), kwargs.get("port")))
        raise OSError("test: connect not allowed")

    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", async_connect)
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", sync_connect)
    monkeypatch.setattr(asyncio.BaseEventLoop, "create_connection", loop_connect)
    yield opened
    get_application_settings.cache_clear()


def _rest_endpoint(url: str) -> Endpoint:
    return Endpoint(
        name="ssrf",
        connection_type="REST",
        method="GET",
        url=url,
        endpoint_path="/health",
        request_headers={"Metadata-Flavor": "Google"},
        request_mapping={"q": "{{ input }}"},
        response_mapping={},
    )


# ---------------------------------------------------------------------------
# Address policy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ip",
    ["::ffff:169.254.169.254", "::ffff:127.0.0.1", "2002:a9fe:a9fe::1", "64:ff9b::a00:1"],
)
def test_tunnelled_ipv6_is_judged_by_its_ipv4_address(ip):
    assert is_blocked_address(ip)


def test_link_local_and_metadata_stay_blocked_when_private_targets_are_allowed():
    for ip in ("169.254.169.254", "fd00:ec2::254", "fe80::1", "::ffff:169.254.169.254"):
        assert is_blocked_address(ip, allow_private=True)
    for ip in ("127.0.0.1", "10.0.0.1", "172.17.0.2", "::1"):
        assert not is_blocked_address(ip, allow_private=True)


def test_public_address_is_allowed():
    assert not is_blocked_address(PUBLIC_IP)


# ---------------------------------------------------------------------------
# Every invoker refuses a blocked target before any socket opens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("host", BLOCKED_HOSTS)
async def test_rest_invoker_refuses_blocked_target(host, strict_egress):
    result = await RestEndpointInvoker().invoke(
        Mock(), _rest_endpoint(f"http://{host}"), {"input": "x"}
    )

    assert result.error_type == "network_error"
    assert "not allowed" in result.output
    assert result.response_content is None
    assert strict_egress == []


@pytest.mark.asyncio
@pytest.mark.parametrize("host", BLOCKED_HOSTS)
async def test_websocket_invoker_refuses_blocked_target(host, strict_egress):
    endpoint = Endpoint(
        name="ssrf-ws",
        connection_type="WebSocket",
        url=f"ws://{host}/socket",
        request_mapping={"q": "{{ input }}"},
        response_mapping={},
    )

    result = await WebSocketEndpointInvoker()._async_invoke(Mock(), endpoint, {"input": "x"})

    assert result.error_type == "websocket_connection_error"
    assert "not allowed" in result.output
    assert strict_egress == []


@pytest.mark.parametrize(
    "token_url", ["https://169.254.169.254/token", "https://internal.example/token"]
)
def test_token_request_refuses_blocked_target(token_url, strict_egress):
    from rhesis.backend.app.error_handlers import UpstreamHTTPException

    endpoint = Endpoint(
        name="ssrf-oauth",
        connection_type="REST",
        url="https://public.example",
        auth_type="client_credentials",
        client_id="id",
        client_secret="secret",
        token_url=token_url,
    )

    with pytest.raises(UpstreamHTTPException) as exc_info:
        AuthenticationManager.get_client_credentials_token(Mock(), endpoint)

    assert "not allowed" in str(exc_info.value.detail)
    assert strict_egress == []


def test_token_request_does_not_follow_redirects():
    from rhesis.backend.app.services.invokers.auth import manager

    assert manager._token_session.follow_redirects is False


@pytest.mark.asyncio
@pytest.mark.parametrize("host", ["169.254.169.254", "10.0.0.1", "mapped.example"])
async def test_model_connection_test_refuses_blocked_api_base(host, strict_egress):
    with patch("rhesis.sdk.models.factory.get_model") as get_model:
        result = await ModelConnectionService.test_connection(
            provider="openai",
            model_name="gpt-4o",
            api_key="sk-test",
            endpoint=f"http://{host}/v1",
        )

    assert result.success is False
    assert "not allowed" in result.message
    get_model.assert_not_called()


def test_stored_model_with_blocked_api_base_is_not_built():
    model = Model(name="internal", endpoint="http://169.254.169.254/v1")

    with patch("rhesis.backend.app.utils.user_model_utils.get_model") as get_model:
        with pytest.raises(ModelConfigurationError, match="not allowed"):
            _build_configured_model(model, "openai", "gpt-4o", "sk-test", "language")

    get_model.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("host", ["169.254.169.254", "127.0.0.1:8080", "internal.example"])
async def test_auto_configure_probe_refuses_blocked_target(host, strict_egress):
    with patch("rhesis.backend.app.services.endpoint.auto_configure.resolve_model"):
        service = AutoConfigureService(Mock(), Mock())

    outcome = await service._probe_endpoint(f"http://{host}/chat", "POST", {}, {})

    assert outcome.success is False
    assert "not allowed" in (outcome.error or "")
    assert strict_egress == []


@pytest.mark.parametrize(
    "url",
    ["https://metadata.google.internal", "https://mapped.example", "http://169.254.169.254"],
)
def test_tool_base_url_never_reaches_metadata(url, monkeypatch):
    monkeypatch.setenv("OUTBOUND_ALLOW_PRIVATE_NETWORKS", "true")
    get_application_settings.cache_clear()

    with pytest.raises(ValueError):
        validate_base_url(url, "JIRA_URL", require_https=False)


def test_tool_base_url_private_host_follows_the_setting(monkeypatch):
    with pytest.raises(ValueError, match="not allowed"):
        validate_base_url("https://internal.example", "JIRA_URL")

    monkeypatch.setenv("OUTBOUND_ALLOW_PRIVATE_NETWORKS", "true")
    get_application_settings.cache_clear()
    validate_base_url("https://internal.example", "JIRA_URL")
    # GitLab's URL never had the HTTPS or hostname rules; adding the check keeps that.
    validate_base_url("http://10.0.0.5:8080/api/v4", "GITLAB_API_URL", require_https=False)


def test_tool_base_url_keeps_https_rule_where_it_had_one():
    with pytest.raises(ValueError, match="HTTPS"):
        validate_base_url("http://public.example", "JIRA_URL")


# ---------------------------------------------------------------------------
# Connect-time pinning and redirects
# ---------------------------------------------------------------------------


class _CannedStream(httpcore.AsyncNetworkStream):
    def __init__(self, response: bytes):
        self._buffer = response

    async def read(self, max_bytes, timeout=None):
        data, self._buffer = self._buffer[:max_bytes], self._buffer[max_bytes:]
        return data

    async def write(self, buffer, timeout=None):
        return None

    async def aclose(self):
        return None

    def get_extra_info(self, info):
        return None


@pytest.mark.asyncio
async def test_connects_to_the_checked_ip_and_rechecks_each_redirect(monkeypatch):
    connected = []

    async def connect(self, host, port, *args, **kwargs):
        connected.append(host)
        return _CannedStream(
            b"HTTP/1.1 302 Found\r\nLocation: http://internal.example/next\r\n"
            b"Content-Length: 0\r\n\r\n"
        )

    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect)

    async with guarded_async_client(follow_redirects=True) as client:
        with pytest.raises(SSRFError):
            await client.get("http://public.example/start")

    # The first hop went to the address that was checked, not to a fresh lookup
    # of the name; the redirect to a private address never connected.
    assert connected == [PUBLIC_IP]


@pytest.mark.asyncio
async def test_a_name_that_rebinds_is_resolved_once_per_connection(monkeypatch):
    answers = iter([PUBLIC_IP, "10.0.0.5"])
    lookups = []

    def rebinding(host, port, *args, **kwargs):
        lookups.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (next(answers), port))]

    connected = []

    async def connect(self, host, port, *args, **kwargs):
        connected.append(host)
        return _CannedStream(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")

    monkeypatch.setattr(socket, "getaddrinfo", rebinding)
    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", connect)

    async with guarded_async_client() as client:
        response = await client.get("http://rebind.example/")

    assert response.text == "ok"
    assert lookups == ["rebind.example"]
    assert connected == [PUBLIC_IP]


@pytest.mark.asyncio
async def test_websocket_connects_to_the_checked_ip(strict_egress):
    with pytest.raises(OSError):
        await guarded_ws_connect("ws://public.example/socket")

    assert strict_egress == [(PUBLIC_IP, 80)]


# ---------------------------------------------------------------------------
# The HTTP route the audit used
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_endpoints_test_route_refuses_loopback(authenticated_client, strict_egress):
    response = authenticated_client.post(
        "/endpoints/test",
        json={
            "connection_type": "REST",
            "url": "http://127.0.0.1:8080",
            "endpoint_path": "/health",
            "method": "GET",
            "request_headers": {"Metadata-Flavor": "Google"},
            "request_mapping": {},
            "response_mapping": {},
            "auth_type": "bearer_token",
            "input_data": {"input": "x"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["error_type"] == "network_error"
    assert "not allowed" in body["output"]
    assert "raw_response" not in body
    # App startup makes unrelated outbound calls; none may reach the target.
    assert not [host for host, _port in strict_egress if host == "127.0.0.1"]


# ---------------------------------------------------------------------------
# Gate: no outbound client is built around the guard
# ---------------------------------------------------------------------------

_APP = Path(__file__).resolve().parents[3] / "apps/backend/src/rhesis/backend/app"

# Files that send requests to tenant-supplied URLs. Each must use the guarded
# clients from app/utils/ssrf_http_client.py, never a bare one. services/github.py
# is not here: it only calls fixed GitHub hosts after a strict github.com URL check.
_GUARDED_PATHS = [
    _APP / "services/invokers",
    _APP / "services/endpoint/auto_configure.py",
    _APP / "services/model_connection.py",
    _APP / "services/tool/rest/jira.py",
    _APP / "services/tool/rest/confluence.py",
]

_BARE_CLIENT = re.compile(
    r"httpx\.(Async)?Client\(|httpx\.(get|post|put|delete|request|stream)\(|"
    r"\brequests\.(get|post|put|delete|request|Session)\b|^\s*import requests\b|"
    r"aiohttp|urllib\.request|"
    r"websockets(\.asyncio)?\.client import connect\b|websockets\.connect\("
)


# Names exception classes only; sends nothing.
_ALLOWED = {_APP / "services/invokers/common/connection_errors.py"}


def _python_files():
    for path in _GUARDED_PATHS:
        files = path.rglob("*.py") if path.is_dir() else [path]
        yield from (f for f in files if f not in _ALLOWED)


def test_gate_covers_real_files():
    assert all(path.exists() for path in _GUARDED_PATHS)


@pytest.mark.parametrize("path", list(_python_files()), ids=lambda p: str(p.relative_to(_APP)))
def test_no_bare_http_client_in_outbound_paths(path):
    offending = [
        f"{path.name}:{number}: {line.strip()}"
        for number, line in enumerate(path.read_text().splitlines(), 1)
        if _BARE_CLIENT.search(line) and not line.lstrip().startswith("#")
    ]
    assert offending == [], (
        "Use guarded_async_client / guarded_client / guarded_ws_connect from "
        "app/utils/ssrf_http_client.py for tenant-supplied URLs:\n" + "\n".join(offending)
    )
