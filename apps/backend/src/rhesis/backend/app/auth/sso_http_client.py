"""SSRF-safe HTTP client for SSO outbound requests.

All outbound HTTP from SSO flows (OIDC discovery, JWKS fetch, token exchange,
test-connection) MUST go through this client. Direct use of httpx or requests
in SSO code is forbidden.

DNS resolution is performed once, validated against the blocklist, and the
resolved IP is pinned into the httpx request to eliminate TOCTOU / DNS
rebinding attacks.
"""

import ipaddress
import logging
import os
import socket
from typing import List, Tuple
from urllib.parse import urlparse, urlunparse

import httpx

logger = logging.getLogger(__name__)

_DEV_ENVIRONMENTS = ("local", "test", "development")
_LOCALHOST_NAMES = {"localhost", "127.0.0.1", "::1"}


def is_dev_environment() -> bool:
    """True when ENVIRONMENT is local, test, or development.

    Used by SSO modules to relax localhost/HTTPS restrictions that are only
    appropriate for production deployments.
    """
    return os.getenv("ENVIRONMENT", "").lower() in _DEV_ENVIRONMENTS

_BLOCKED_NETWORKS = [
    # RFC 1918 private address space -- VPCs, Kubernetes pods, Docker networks,
    # home/office LANs.  The primary SSRF target in cloud environments.
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # Link-local (RFC 3927) -- includes 169.254.169.254, the instance metadata
    # endpoint on AWS, GCP, and Azure.
    ipaddress.ip_network("169.254.0.0/16"),
    # Loopback -- prevents requests to services bound to localhost.
    ipaddress.ip_network("127.0.0.0/8"),
    # "This network" (RFC 1122) -- 0.0.0.0 on Linux resolves to all local
    # interfaces, effectively reaching localhost services.
    ipaddress.ip_network("0.0.0.0/8"),
    # Carrier-grade NAT (RFC 6598) -- used internally by some cloud providers
    # (AWS VPC endpoints, Tailscale) and must not be reachable.
    ipaddress.ip_network("100.64.0.0/10"),
    # IETF protocol assignments (RFC 6890).
    ipaddress.ip_network("192.0.0.0/24"),
    # Benchmarking (RFC 2544) -- sometimes used in internal test infra.
    ipaddress.ip_network("198.18.0.0/15"),
    # IPv6 loopback.
    ipaddress.ip_network("::1/128"),
    # IPv6 Unique Local Addresses (RFC 4193) -- the IPv6 equivalent of
    # RFC 1918 private space.
    ipaddress.ip_network("fc00::/7"),
    # IPv6 link-local.
    ipaddress.ip_network("fe80::/10"),
]
"""IP networks that must never be contacted by outbound SSO requests.

Covers RFC 1918 private space, loopback, link-local (cloud metadata),
carrier-grade NAT, IETF reserved, benchmarking, and IPv6 equivalents.
Any hostname that resolves to an address within these ranges is rejected
to prevent Server-Side Request Forgery (SSRF).
"""

_BLOCKED_HOSTNAMES = {
    # GCP metadata service -- resolved by name so it is caught even if GCP
    # maps it to a non-link-local IP in some configurations.
    "metadata.google.internal",
    "metadata.internal",
    # AWS IMDSv2 IPv6 endpoint (fd00:ec2::254 falls inside fc00::/7 above,
    # but the hostname is listed explicitly for defense-in-depth).
    "fd00:ec2::254",
}
"""Hostnames blocked regardless of what IP they resolve to.

Primarily targets cloud instance metadata services that may not always
resolve to the link-local 169.254.x.x range.
"""


class SSRFError(Exception):
    """Raised when an outbound request targets a blocked destination."""

    pass


def _resolve_and_validate(hostname: str) -> List[Tuple]:
    """Resolve hostname, validate all IPs against the blocklist, and return
    the raw getaddrinfo results for pinning into the transport.

    In development environments (ENVIRONMENT=local/test/development), localhost
    is allowed through the blocklist so that local IdP instances (e.g. Keycloak
    on localhost:8180) can be reached.

    Raises SSRFError if the hostname resolves to a blocked IP or cannot be
    resolved.
    """
    if hostname.lower() in _BLOCKED_HOSTNAMES:
        raise SSRFError(f"Blocked hostname: {hostname}")

    skip_blocklist = (
        is_dev_environment() and hostname.lower() in _LOCALHOST_NAMES
    )

    try:
        addr_infos = socket.getaddrinfo(
            hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
    except socket.gaierror:
        raise SSRFError(f"DNS resolution failed for: {hostname}")

    if not addr_infos:
        raise SSRFError(f"DNS resolution returned no results for: {hostname}")

    if not skip_blocklist:
        for _family, _, _, _, sockaddr in addr_infos:
            ip_str = sockaddr[0]
            try:
                addr = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            for network in _BLOCKED_NETWORKS:
                if addr in network:
                    logger.warning(
                        "SSRF block: %s resolved to %s (in %s)",
                        hostname,
                        ip_str,
                        network,
                    )
                    raise SSRFError(
                        f"Hostname {hostname} resolves to a blocked address"
                    )
    else:
        logger.info(
            "SSRF blocklist bypassed for localhost in dev environment: %s",
            hostname,
        )

    return addr_infos


def _pin_url_to_ip(url: str, addr_infos: List[Tuple]) -> Tuple[str, str]:
    """Replace the hostname in the URL with a validated resolved IP.

    Returns (pinned_url, original_hostname) so the caller can set the
    Host header correctly.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    port = parsed.port

    ip_str = addr_infos[0][4][0]
    addr = ipaddress.ip_address(ip_str)

    if isinstance(addr, ipaddress.IPv6Address):
        ip_host = f"[{ip_str}]"
    else:
        ip_host = ip_str

    if port:
        new_netloc = f"{ip_host}:{port}"
    else:
        new_netloc = ip_host

    pinned = urlunparse((
        parsed.scheme,
        new_netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        parsed.fragment,
    ))
    return pinned, hostname


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
        raise SSRFError(
            f"Endpoint uses disallowed scheme: {ep_parsed.scheme}"
        )

    if ep_parsed.scheme != issuer_parsed.scheme:
        raise SSRFError("Endpoint scheme does not match issuer URL")

    if ep_parsed.hostname != issuer_parsed.hostname:
        raise SSRFError(
            f"Endpoint hostname ({ep_parsed.hostname}) does not match "
            f"issuer hostname ({issuer_parsed.hostname})"
        )


# Keep the old name as an alias so existing callers don't break
validate_jwks_uri_origin = validate_endpoint_origin


class SSOHttpClient:
    """SSRF-safe HTTP client for all SSO outbound requests.

    Eliminates TOCTOU / DNS rebinding by resolving the hostname once,
    validating the resolved IPs, and pinning the validated IP directly
    into the outbound request URL. The original hostname is sent as the
    Host header so TLS SNI and virtual hosting still work.

    Set ``verify_ssl=False`` only for IdPs with self-signed certificates
    (e.g. on-premise Keycloak in dev/staging). TLS is always verified in
    production unless this flag is explicitly set on the SSOConfig.
    """

    def __init__(self, timeout: float = 10.0, verify_ssl: bool = True):
        self._timeout = timeout
        self._verify_ssl = verify_ssl

    def _prepare(self, url: str, kwargs: dict) -> Tuple[str, bool]:
        """Resolve, validate, and pin the URL. Injects the Host header.

        Returns (pinned_url, skip_tls). TLS is skipped when the caller
        passed verify_ssl=False, or when running in dev against localhost.
        """
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            raise SSRFError("URL has no hostname")

        addr_infos = _resolve_and_validate(hostname)
        pinned_url, original_host = _pin_url_to_ip(url, addr_infos)

        headers = dict(kwargs.pop("headers", {}) or {})
        port = parsed.port
        if port and port not in (80, 443):
            headers.setdefault("Host", f"{original_host}:{port}")
        else:
            headers.setdefault("Host", original_host)
        kwargs["headers"] = headers

        is_localhost_dev = (
            is_dev_environment()
            and hostname.lower() in _LOCALHOST_NAMES
        )
        skip_tls = is_localhost_dev or (not self._verify_ssl)
        return pinned_url, skip_tls

    async def get(self, url: str, **kwargs) -> httpx.Response:
        pinned_url, skip_tls = self._prepare(url, kwargs)
        async with httpx.AsyncClient(
            timeout=self._timeout, verify=not skip_tls
        ) as client:
            return await client.get(pinned_url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        pinned_url, skip_tls = self._prepare(url, kwargs)
        async with httpx.AsyncClient(
            timeout=self._timeout, verify=not skip_tls
        ) as client:
            return await client.post(pinned_url, **kwargs)
