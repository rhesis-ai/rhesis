"""GitHub REST API source for deterministic file content extraction."""

import base64
import logging
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

import httpx

from .schemas import FetchedSource

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"


def _parse_github_url(url: str) -> Tuple[str, str]:
    """Parse a full GitHub URL into (api_url, branch).

    Accepts:
      - https://github.com/owner/repo
      - https://github.com/owner/repo/blob/branch/path/to/file
      - https://github.com/owner/repo/tree/branch/path/to/dir
    """
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError(f"Expected a full GitHub URL, got: {url!r}")

    parsed = urlparse(url)
    host = parsed.hostname or ""
    if not (host == "github.com" or host.endswith(".github.com")):
        raise ValueError(
            f"Expected a GitHub URL (github.com) but got: {url!r}. "
            "Make sure you selected the correct tool for this URL."
        )
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Cannot parse owner/repo from URL: {url}")

    owner, repo = parts[0], parts[1]

    if len(parts) >= 4 and parts[2] in ("blob", "tree"):
        branch = parts[3]
        path = "/".join(parts[4:])
    else:
        branch = "main"
        path = "/".join(parts[2:])

    api_url = f"{_GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    return api_url, branch


class GitHubRestClient:
    """Fetches GitHub file content directly via the REST API."""

    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def health_check(self) -> Dict[str, Any]:
        """Verify credentials by calling GET /user."""
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://api.github.com/user", headers=self._headers)
        if resp.status_code == 200:
            login = resp.json().get("login", "")
            return {"is_authenticated": "Yes", "message": f"Connected as {login}"}
        return {"is_authenticated": "No", "message": f"Authentication failed: {resp.status_code}"}

    async def fetch(self, url: str) -> str:
        """Fetch a single file or top-level directory listing from a GitHub URL."""
        sources = await self.fetch_all(url, include_children=False)
        if len(sources) == 1:
            return sources[0].content
        return "\n".join(f"- {s.title}" for s in sources)

    async def fetch_all(self, url: str, include_children: bool = False) -> List[FetchedSource]:
        """Fetch a file or directory from a GitHub URL.

        For files: returns a single FetchedSource.
        For directories: returns one FetchedSource per file.
            When include_children=True, recurses into subdirectories.
        """
        api_url, branch = _parse_github_url(url)
        async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
            return await self._fetch(client, api_url, branch, include_children)

    async def _fetch(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        branch: str,
        recursive: bool,
    ) -> List[FetchedSource]:
        response = await client.get(api_url, params={"ref": branch})

        if response.status_code == 404:
            raise ValueError(f"GitHub resource not found: {api_url}. Check the URL and branch.")
        if response.status_code == 401:
            raise ValueError(
                "Invalid GitHub token. Please check your GITHUB_PERSONAL_ACCESS_TOKEN credentials."
            )

        response.raise_for_status()
        data = response.json()

        if isinstance(data, list):
            sources: List[FetchedSource] = []
            for entry in data:
                if entry["type"] == "file":
                    sources.append(await self._fetch_file(client, entry["url"], branch))
                elif entry["type"] == "dir" and recursive:
                    sources.extend(await self._fetch(client, entry["url"], branch, recursive))
            return sources

        return [self._to_source(data)]

    async def _fetch_file(
        self, client: httpx.AsyncClient, api_url: str, branch: str = ""
    ) -> FetchedSource:
        params = {"ref": branch} if branch else {}
        response = await client.get(api_url, params=params)
        response.raise_for_status()
        return self._to_source(response.json())

    def _to_source(self, data: Dict[str, Any]) -> FetchedSource:
        return FetchedSource(
            id=data.get("sha", data.get("path", "")),
            title=data.get("name", ""),
            content=self._decode(data),
            url=data.get("html_url"),
        )

    @staticmethod
    def _decode(data: Dict[str, Any]) -> str:
        content = data.get("content", "")
        if data.get("encoding") == "base64":
            return base64.b64decode(content).decode("utf-8", errors="replace")
        return content
