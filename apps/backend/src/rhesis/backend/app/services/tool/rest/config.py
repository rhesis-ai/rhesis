"""Resolve a DB tool to its REST client implementation via a provider registry."""

import ipaddress
import json
import socket
import uuid
from typing import Callable, Dict
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException

from .base import RestClient

# Private IP ranges that must never be reached by user-supplied URLs
_BLOCKED_NETS = [
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
        addr = ipaddress.ip_address(host)
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


from .confluence import ConfluenceRestClient
from .github import GitHubRestClient
from .jira import JiraRestClient
from .notion import NotionRestClient

# Maps provider type_value → factory(credentials) → RestClient
_PROVIDER_REGISTRY: Dict[str, Callable[[Dict[str, str]], RestClient]] = {
    "notion": lambda c: NotionRestClient(token=c.get("NOTION_TOKEN", "")),
    "github": lambda c: GitHubRestClient(token=c.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")),
    "jira": lambda c: JiraRestClient(
        base_url=c.get("JIRA_URL", ""),
        username=c.get("JIRA_USERNAME", ""),
        api_token=c.get("JIRA_API_TOKEN", ""),
    ),
    "confluence": lambda c: ConfluenceRestClient(
        base_url=c.get("CONFLUENCE_URL", ""),
        username=c.get("CONFLUENCE_USERNAME", ""),
        api_token=c.get("CONFLUENCE_API_TOKEN", ""),
    ),
}


def build_client(provider: str, credentials: Dict[str, str]) -> RestClient:
    """Instantiate the RestClient for *provider* using *credentials*.

    Raises:
        ToolConfigurationError: If no client is registered for *provider*.
    """
    factory = _PROVIDER_REGISTRY.get(provider)
    if factory is None:
        raise ToolConfigurationError(f"No REST client registered for provider '{provider}'")
    return factory(credentials)


def get_rest_source(
    db: Session, tool_id: str, organization_id: str, user_id: str = None
) -> RestClient:
    """Resolve a DB tool to its REST client.

    Raises:
        ToolConfigurationError: If tool not found, deleted, or provider unsupported.
    """
    try:
        tool = crud.get_tool(db, uuid.UUID(tool_id), organization_id, user_id)
    except ItemDeletedException:
        raise ToolConfigurationError(
            f"Tool '{tool_id}' has been deleted. Please re-import the source."
        )

    if not tool:
        raise ToolConfigurationError(
            f"Tool '{tool_id}' not found. Please add it in /integrations/tools"
        )

    try:
        credentials = json.loads(tool.credentials)
    except (json.JSONDecodeError, TypeError) as e:
        raise ToolConfigurationError(f"Invalid credentials for tool '{tool_id}': {e}")

    return build_client(tool.tool_provider_type.type_value, credentials)
