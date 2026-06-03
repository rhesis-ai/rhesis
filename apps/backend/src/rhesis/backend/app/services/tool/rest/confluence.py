"""Confluence REST API client."""

from typing import Any, Dict

import httpx


class ConfluenceRestClient:
    def __init__(self, base_url: str, username: str, api_token: str):
        self._base_url = base_url.rstrip("/")
        self._auth = (username, api_token)

    async def health_check(self) -> Dict[str, Any]:
        url = self._base_url + "/wiki/rest/api/user/current"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, auth=self._auth)
        if resp.status_code == 200:
            display = resp.json().get("displayName", "")
            return {"is_authenticated": "Yes", "message": f"Connected as {display}"}
        return {"is_authenticated": "No", "message": f"Authentication failed: {resp.status_code}"}
