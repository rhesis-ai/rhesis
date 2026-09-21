"""Outbound URL validation for user-supplied instance URLs.

Lives apart from ``rest/config.py`` so the REST clients that need it do not
have to import from the module that builds them. That cycle is why
``config.py`` used to import its client classes at the bottom of the file.

The blocklist covers the addresses an attacker would aim a tenant-supplied
"workspace URL" at: RFC 1918 space, loopback, and the link-local range that
carries the cloud instance-metadata endpoint.
"""

import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_NETS = [
    ipaddress.ip_network("0.0.0.0/8"),  # wildcard; routes to localhost on Linux
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / AWS metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def validate_base_url(url: str, field: str = "URL") -> None:
    """Raise ValueError if *url* is not a safe, public HTTPS endpoint.

    Checks:
    - scheme must be https
    - host must not be an IP literal
    - hostname must not resolve to a private/loopback/link-local address
    """
    if not url:
        raise ValueError(f"{field} must not be empty.")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"{field} must use HTTPS (got '{parsed.scheme}').")
    host = parsed.hostname or ""
    if not host:
        raise ValueError(f"{field} has no hostname.")
    # Reject raw IP literals
    try:
        ipaddress.ip_address(host)
        raise ValueError(f"{field} must be a hostname, not an IP address ({host}).")
    except ValueError as exc:
        # ip_address() raises ValueError for non-IP strings — that's expected
        if "must be a hostname" in str(exc):
            raise
    # DNS resolution check
    try:
        resolved = socket.getaddrinfo(host, None)
    except OSError:
        raise ValueError(f"{field} hostname '{host}' could not be resolved.")
    for _family, _type, _proto, _canonname, sockaddr in resolved:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        for net in _BLOCKED_NETS:
            if ip in net:
                raise ValueError(
                    f"{field} hostname '{host}' resolves to a private/internal address "
                    f"({ip_str}) which is not allowed."
                )
