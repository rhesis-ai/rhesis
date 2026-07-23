"""Thin wrapper around the SDK ``APIClient`` for pulling data from a Rhesis platform.

Wrapping the SDK client (rather than calling it directly from resource handlers)
keeps pagination and token introspection in one place and gives tests a single,
easy seam to mock (patch ``PlatformClient.list`` / ``introspect_token``).
"""

from __future__ import annotations

import logging
from typing import List, Optional

import requests

from rhesis.sdk.clients.api import APIClient, Endpoints, Methods

logger = logging.getLogger(__name__)

_TIMEOUT = 30
_PAGE_SIZE = 100


class PlatformClient:
    """Read-only client for a remote Rhesis platform, authenticated by an ``rh-`` key."""

    def __init__(self, api_key: str, base_url: str):
        self._api = APIClient(api_key=api_key, base_url=base_url)

    @property
    def base_url(self) -> str:
        return self._api.base_url

    def get_json(self, path: str) -> dict:
        """GET an arbitrary path (not in the SDK ``Endpoints`` enum) and return JSON."""
        response = requests.get(
            f"{self._api.base_url}/{path.lstrip('/')}",
            headers=self._api.headers,
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def introspect_token(self) -> dict:
        """Validate the key and return ``{organization_id, user_email, project_id}``.

        Raises ``requests`` errors on failure (mapped by the caller).
        """
        return self.get_json("tokens/current")

    def list(self, endpoint: Endpoints, params: Optional[dict] = None) -> List[dict]:
        """Fetch every page of a platform list endpoint (list routes default limit=10)."""
        out: List[dict] = []
        skip = 0
        while True:
            page_params = {"skip": skip, "limit": _PAGE_SIZE, **(params or {})}
            batch = self._api.send_request(endpoint, Methods.GET, params=page_params)
            if isinstance(batch, dict):
                batch = batch.get("data", [])
            if not isinstance(batch, list):
                batch = []
            out.extend(batch)
            if len(batch) < _PAGE_SIZE:
                return out
            skip += _PAGE_SIZE

    def set_project(self, project_id: str) -> None:
        """Scope subsequent requests to a specific project (via ``X-Project-Id``)."""
        self._api.headers["X-Project-Id"] = str(project_id)

    def clear_project(self) -> None:
        self._api.headers.pop("X-Project-Id", None)
