"""SSRF-safe outbound HTTP and WebSocket clients for addresses a tenant supplies.

Anywhere a customer names the host we call -- an endpoint URL, a model
``api_base``, an OAuth token URL, an OIDC issuer, a self-managed Jira -- the
address is untrusted input, and the obvious target is something only the
server can reach: a VPC neighbour, a Kubernetes service, or the cloud metadata
endpoint on 169.254.169.254.

The guard sits at the connection, not the URL. The transports below resolve
the host, check every address it returns, and then connect to one of those
checked IPs, so a name cannot resolve to a public address for the check and a
private one for the connect (DNS rebinding). The URL keeps its hostname, so
``Host``, SNI and certificate verification are unchanged. Every redirect hop
opens a new connection and goes through the same check.

Private targets (loopback, RFC 1918, CGNAT, ULA) are allowed only when
``OUTBOUND_ALLOW_PRIVATE_NETWORKS`` is on, which is the default for local
development and self-hosting. Link-local, multicast and the cloud metadata
addresses stay blocked either way.
"""

import ipaddress
import logging
import socket
from typing import Any, List, Optional, Tuple
from urllib.parse import urlparse

import anyio
import httpcore
import httpx
from websockets.asyncio.client import connect as _ws_connect
from websockets.uri import parse_uri

from rhesis.backend.app.config.settings import get_application_settings

logger = logging.getLogger(__name__)

_LOCALHOST_NAMES = {"localhost", "127.0.0.1", "::1"}

# Blocked even when private targets are allowed: nothing legitimate lives here.
_METADATA_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fd00:ec2::254/128"),  # AWS IMDS over IPv6
    ipaddress.ip_network("100.100.100.200/32"),  # Alibaba Cloud metadata
    ipaddress.ip_network("168.63.129.16/32"),  # Azure WireServer
]

# Carrier-grade NAT; neither ``is_private`` nor ``is_global`` in Python.
_CGNAT = ipaddress.ip_network("100.64.0.0/10")
_NAT64 = ipaddress.ip_network("64:ff9b::/96")

_BLOCKED_HOSTNAMES = {
    "metadata.google.internal",
    "metadata.internal",
    "metadata",
    "instance-data",
    "fd00:ec2::254",
}
"""Hostnames blocked regardless of what IP they resolve to."""

BLOCKED_TARGET_MESSAGE = (
    "the address is not allowed: requests to private, loopback, link-local "
    "or cloud metadata addresses are blocked"
)


class SSRFError(Exception):
    """Raised when an outbound request targets a blocked destination."""

    pass


def private_targets_allowed() -> bool:
    """Whether tenant URLs may point at loopback or private networks."""
    return get_application_settings().allow_private_outbound


def _embedded_ipv4(addr: ipaddress.IPv6Address) -> Optional[ipaddress.IPv4Address]:
    """The IPv4 address an IPv6 address tunnels to (mapped, 6to4, NAT64), if any."""
    if addr.ipv4_mapped:
        return addr.ipv4_mapped
    if addr.sixtofour:
        return addr.sixtofour
    if addr in _NAT64:
        return ipaddress.IPv4Address(int(addr) & 0xFFFFFFFF)
    return None


def is_blocked_address(ip: str, allow_private: bool = False) -> bool:
    """Whether connecting to ``ip`` must be refused."""
    addr = ipaddress.ip_address(ip.split("%", 1)[0])
    if isinstance(addr, ipaddress.IPv6Address):
        addr = _embedded_ipv4(addr) or addr
    if addr.is_link_local or addr.is_multicast:
        return True
    if any(addr in network for network in _METADATA_NETWORKS):
        return True
    if addr.is_global:
        return False
    if not allow_private:
        return True
    return not (addr.is_loopback or addr.is_private or addr.is_unspecified or addr in _CGNAT)


def resolve_checked(
    host: str, port: Optional[int] = None, allow_private: bool = False
) -> List[str]:
    """Resolve ``host`` and return its addresses, or raise if any is blocked.

    One blocked address fails the whole name, so a multi-record answer cannot
    smuggle an internal address in next to a public one.
    """
    name = (host or "").strip("[]").rstrip(".").lower()
    if not name:
        raise SSRFError("URL has no hostname")
    if name in _BLOCKED_HOSTNAMES:
        raise SSRFError(f"Blocked hostname: {host}")

    try:
        addr_infos = socket.getaddrinfo(name, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise SSRFError(f"DNS resolution failed for: {host}")
    if not addr_infos:
        raise SSRFError(f"DNS resolution returned no results for: {host}")

    ips: List[str] = []
    for _family, _, _, _, sockaddr in addr_infos:
        ip = sockaddr[0]
        if is_blocked_address(ip, allow_private):
            logger.warning("SSRF block: %s resolved to %s", host, ip)
            raise SSRFError(f"Hostname {host} resolves to a blocked address")
        if ip not in ips:
            ips.append(ip)
    return ips


def _allow(allow_private: Optional[bool]) -> bool:
    return private_targets_allowed() if allow_private is None else allow_private


def validate_outbound_url(url: str, allow_private: Optional[bool] = None) -> None:
    """Raise ``SSRFError`` unless ``url`` is http(s)/ws(s) to an allowed address.

    For a check up front, before the URL is handed to a client this module does
    not control (LiteLLM for a model ``api_base``). The guarded clients below
    check again at connect time.
    """
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https", "ws", "wss"):
        raise SSRFError(f"URL uses disallowed scheme: {parsed.scheme or 'none'}")
    if not parsed.hostname:
        raise SSRFError("URL has no hostname")
    resolve_checked(parsed.hostname, None, _allow(allow_private))


# ---------------------------------------------------------------------------
# Guarded transports
# ---------------------------------------------------------------------------


class _GuardedAsyncBackend(httpcore.AsyncNetworkBackend):
    """Resolves and checks the host, then connects to a checked IP."""

    def __init__(self, allow_private: Optional[bool]):
        self._allow_private = allow_private
        self._inner = httpcore.AnyIOBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        ips = await anyio.to_thread.run_sync(
            resolve_checked, host, port, _allow(self._allow_private)
        )
        error: Optional[Exception] = None
        for ip in ips:
            try:
                return await self._inner.connect_tcp(
                    ip, port, timeout, local_address, socket_options
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                error = exc
        raise error  # type: ignore[misc]

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise SSRFError("Unix sockets are not allowed for outbound requests")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class _GuardedSyncBackend(httpcore.NetworkBackend):
    """Sync twin of ``_GuardedAsyncBackend``."""

    def __init__(self, allow_private: Optional[bool]):
        self._allow_private = allow_private
        self._inner = httpcore.SyncBackend()

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        ips = resolve_checked(host, port, _allow(self._allow_private))
        error: Optional[Exception] = None
        for ip in ips:
            try:
                return self._inner.connect_tcp(ip, port, timeout, local_address, socket_options)
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                error = exc
        raise error  # type: ignore[misc]

    def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise SSRFError("Unix sockets are not allowed for outbound requests")


class GuardedAsyncTransport(httpx.AsyncHTTPTransport):
    """``httpx.AsyncHTTPTransport`` whose connections go through the SSRF check."""

    def __init__(
        self,
        *,
        verify: bool = True,
        limits: httpx.Limits = httpx.Limits(max_connections=100, max_keepalive_connections=20),
        allow_private: Optional[bool] = None,
    ):
        # Built directly: httpx's own __init__ has no way to pass a network backend.
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=httpx.create_ssl_context(verify=verify),
            max_connections=limits.max_connections,
            max_keepalive_connections=limits.max_keepalive_connections,
            keepalive_expiry=limits.keepalive_expiry,
            network_backend=_GuardedAsyncBackend(allow_private),
        )


class GuardedTransport(httpx.HTTPTransport):
    """Sync twin of ``GuardedAsyncTransport``."""

    def __init__(
        self,
        *,
        verify: bool = True,
        limits: httpx.Limits = httpx.Limits(max_connections=100, max_keepalive_connections=20),
        allow_private: Optional[bool] = None,
    ):
        self._pool = httpcore.ConnectionPool(
            ssl_context=httpx.create_ssl_context(verify=verify),
            max_connections=limits.max_connections,
            max_keepalive_connections=limits.max_keepalive_connections,
            keepalive_expiry=limits.keepalive_expiry,
            network_backend=_GuardedSyncBackend(allow_private),
        )


def guarded_async_client(
    *, allow_private: Optional[bool] = None, verify: bool = True, **kwargs: Any
) -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` for tenant-supplied URLs.

    ``allow_private=None`` follows ``OUTBOUND_ALLOW_PRIVATE_NETWORKS``. Env
    proxies are ignored: through a proxy the check would see the proxy's address.
    """
    transport = GuardedAsyncTransport(verify=verify, allow_private=allow_private)
    return httpx.AsyncClient(transport=transport, trust_env=False, **kwargs)


def guarded_client(
    *, allow_private: Optional[bool] = None, verify: bool = True, **kwargs: Any
) -> httpx.Client:
    """Sync twin of ``guarded_async_client``."""
    transport = GuardedTransport(verify=verify, allow_private=allow_private)
    return httpx.Client(transport=transport, trust_env=False, **kwargs)


class guarded_ws_connect(_ws_connect):
    """``websockets`` ``connect`` that checks each hop's address and connects to it.

    Redirects re-enter ``create_connection`` with the new URI, so each hop is
    checked. Env proxies are off for the same reason as the HTTP clients.
    """

    def __init__(self, uri: str, *, allow_private: Optional[bool] = None, **kwargs: Any):
        kwargs.setdefault("proxy", None)
        super().__init__(uri, **kwargs)
        self._allow_private = allow_private

    async def create_connection(self):
        ws_uri = parse_uri(self.uri)
        ips = await anyio.to_thread.run_sync(
            resolve_checked, ws_uri.host, ws_uri.port, _allow(self._allow_private)
        )
        base_kwargs = self.connection_kwargs
        error: Optional[Exception] = None
        try:
            for ip in ips:
                # Swapped in per attempt only: a host left in connection_kwargs
                # would make websockets refuse cross-origin redirects.
                self.connection_kwargs = {**base_kwargs, "host": ip, "port": ws_uri.port}
                try:
                    return await super().create_connection()
                except OSError as exc:
                    error = exc
        finally:
            self.connection_kwargs = base_kwargs
        raise error  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SSO / webhook helpers
# ---------------------------------------------------------------------------


def _localhost_allowed(hostname: str) -> bool:
    """SSO and webhooks allow only the local machine, and only when private targets are."""
    return private_targets_allowed() and hostname.lower() in _LOCALHOST_NAMES


def _resolve_and_validate(hostname: str) -> List[str]:
    """Resolve ``hostname`` under the strict SSO/webhook policy and return its IPs."""
    return resolve_checked(hostname, None, allow_private=_localhost_allowed(hostname))


def validate_url_safety(url: str) -> None:
    """Validate that a URL is safe for outbound requests.

    Checks both the URL structure and DNS resolution.
    Kept for use in non-request contexts (e.g. validating JWKS URI origin).
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL has no hostname")

    _resolve_and_validate(hostname)


def validate_endpoint_origin(endpoint_url: str, issuer_url: str) -> None:
    """Ensure an endpoint URL from OIDC discovery is same-origin as the issuer.

    Prevents a compromised discovery document from redirecting requests or
    browser redirects to arbitrary destinations.
    """
    ep_parsed = urlparse(endpoint_url)
    issuer_parsed = urlparse(issuer_url)

    if ep_parsed.scheme not in ("https", "http"):
        raise SSRFError(f"Endpoint uses disallowed scheme: {ep_parsed.scheme}")

    if ep_parsed.scheme != issuer_parsed.scheme:
        raise SSRFError("Endpoint scheme does not match issuer URL")

    if ep_parsed.hostname != issuer_parsed.hostname:
        raise SSRFError(
            f"Endpoint hostname ({ep_parsed.hostname}) does not match "
            f"issuer hostname ({issuer_parsed.hostname})"
        )


# Keep the old name as an alias so existing callers don't break
validate_jwks_uri_origin = validate_endpoint_origin


class SafeHttpClient:
    """HTTP client for SSO and webhook targets, which must be public addresses.

    Stricter than the endpoint clients above: private networks are never
    allowed, only the local machine, and only when private targets are allowed
    (a local Keycloak on localhost:8180). The address is checked up front for a
    clear error, then again at connect time by the guarded transport.

    Set ``verify_ssl=False`` only for a host with a self-signed or internal-CA
    certificate, such as an on-premise Keycloak. Use it only where the network
    between Rhesis and the host is itself trusted.
    """

    def __init__(self, timeout: float = 10.0, verify_ssl: bool = True):
        self._timeout = timeout
        self._verify_ssl = verify_ssl

    def _prepare(self, url: str) -> Tuple[bool, bool]:
        """Check the URL; return (allow_private, verify) for the transport."""
        hostname = urlparse(url).hostname
        if not hostname:
            raise SSRFError("URL has no hostname")
        _resolve_and_validate(hostname)
        localhost = _localhost_allowed(hostname)
        return localhost, self._verify_ssl and not localhost

    def _client_kwargs(self, url: str, transport_cls: type) -> dict:
        allow_private, verify = self._prepare(url)
        return {
            "timeout": self._timeout,
            "verify": verify,
            "follow_redirects": False,
            "trust_env": False,
            "transport": transport_cls(verify=verify, allow_private=allow_private),
        }

    async def get(self, url: str, **kwargs) -> httpx.Response:
        async with httpx.AsyncClient(**self._client_kwargs(url, GuardedAsyncTransport)) as client:
            return await client.get(url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        async with httpx.AsyncClient(**self._client_kwargs(url, GuardedAsyncTransport)) as client:
            return await client.post(url, **kwargs)

    def post_sync(self, url: str, **kwargs) -> httpx.Response:
        """``post`` for sync callers such as Celery jobs. Never follows redirects."""
        with httpx.Client(**self._client_kwargs(url, GuardedTransport)) as client:
            return client.post(url, **kwargs)
