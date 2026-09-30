"""HTTP access to the docs site's LLM views."""

from __future__ import annotations

import httpx

from docs_assistant.corpus.parser import url_to_path


class DocsFetchError(RuntimeError):
    """The docs site could not be reached or returned an error."""


class DocsFetcher:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        # Tests pass an httpx.MockTransport; production uses the default network transport.
        self._transport = transport

    async def fetch_index(self) -> str:
        return await self._get("/llms.txt")

    async def fetch_full(self) -> str:
        return await self._get("/llms-full.txt")

    async def fetch_page(self, url_or_path: str, *, timeout: float | None = None) -> str:
        # /api/md/ works in production today; /<path>.md depended on the Dockerfile fix.
        return await self._get(f"/api/md/{url_to_path(url_or_path)}", timeout=timeout, retries=0)

    async def _get(self, path: str, *, timeout: float | None = None, retries: int | None = None):
        attempts = 1 + (self.retries if retries is None else retries)
        last_error: Exception | None = None
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout or self.timeout,
            transport=self._transport,
            follow_redirects=True,
        ) as client:
            for _ in range(attempts):
                try:
                    response = await client.get(path)
                except httpx.HTTPError as exc:
                    last_error = exc
                    continue
                if response.status_code == 200:
                    return response.text
                last_error = DocsFetchError(f"GET {path} returned {response.status_code}")
                if response.status_code < 500:
                    break
        raise DocsFetchError(f"Could not fetch {self.base_url}{path}: {last_error}")
