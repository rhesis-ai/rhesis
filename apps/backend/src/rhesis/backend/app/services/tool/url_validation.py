"""Outbound URL validation for user-supplied instance URLs.

Lives apart from ``rest/config.py`` so the REST clients that need it do not
have to import from the module that builds them. That cycle is why
``config.py`` used to import its client classes at the bottom of the file.

The address check is the shared one in ``app/utils/ssrf_http_client.py``:
private networks follow ``OUTBOUND_ALLOW_PRIVATE_NETWORKS`` (on-prem Jira or
GitLab is a real setup), link-local and cloud metadata are always refused.
"""

import ipaddress
from urllib.parse import urlparse

from rhesis.backend.app.utils.ssrf_http_client import (
    SSRFError,
    private_targets_allowed,
    resolve_checked,
)


def validate_base_url(url: str, field: str = "URL", *, require_https: bool = True) -> None:
    """Raise ValueError if *url* is not a safe endpoint.

    Checks:
    - scheme must be https (http too when ``require_https`` is False)
    - host must not be an IP literal (only when ``require_https``)
    - hostname must not resolve to a blocked address

    ``require_https=False`` is for fields that never had the HTTPS and
    hostname rules (``GITLAB_API_URL``), so adding the address check does not
    also reject URLs that used to be accepted.
    """
    if not url:
        raise ValueError(f"{field} must not be empty.")
    parsed = urlparse(url)
    allowed_schemes = ("https",) if require_https else ("https", "http")
    if parsed.scheme not in allowed_schemes:
        expected = "HTTPS" if require_https else "http or https"
        raise ValueError(f"{field} must use {expected} (got '{parsed.scheme}').")
    host = parsed.hostname or ""
    if not host:
        raise ValueError(f"{field} has no hostname.")
    if require_https and _is_ip_literal(host):
        raise ValueError(f"{field} must be a hostname, not an IP address ({host}).")
    try:
        resolve_checked(host, None, allow_private=private_targets_allowed())
    except SSRFError as exc:
        raise ValueError(f"{field} is not allowed: {exc}.") from exc


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True
