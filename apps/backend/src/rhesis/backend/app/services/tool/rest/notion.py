"""Notion REST API source for deterministic page content extraction."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .schemas import FetchedSource

logger = logging.getLogger(__name__)

_NOTION_API = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


class NotionRestClient:
    """Fetches Notion page content directly via the REST API.

    Uses the Notion API to retrieve page blocks and convert them to
    plain markdown. Handles pagination and nested blocks automatically.
    """

    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
        }

    async def health_check(
        self, tool_metadata: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Verify credentials by calling GET /v1/users/me."""
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://api.notion.com/v1/users/me", headers=self._headers)
        if resp.status_code == 200:
            data = resp.json()
            bot_owner = data.get("bot", {}).get("owner", {}).get("user", {})
            name = data.get("name") or bot_owner.get("name", "")
            return {"is_authenticated": "Yes", "message": f"Connected as {name}"}
        return {"is_authenticated": "No", "message": f"Authentication failed: {resp.status_code}"}

    async def fetch(self, page_id_or_url: str) -> str:
        """Fetch a single Notion page as markdown text.

        Args:
            page_id_or_url: Notion page ID (raw or UUID) or full Notion URL.

        Returns:
            Page content as markdown string.
        """
        docs = await self.fetch_all(page_id_or_url, include_children=False)
        return docs[0].content if docs else ""

    async def fetch_all(
        self,
        page_id_or_url: str,
        include_children: bool = False,
    ) -> List[FetchedSource]:
        """Fetch a Notion page and optionally its subpages.

        Args:
            page_id_or_url: Notion page ID (raw or UUID) or full Notion URL.
            include_children: When True, each child page is fetched
                separately and returned as an additional FetchedSource.

        Returns:
            List of FetchedSource — the first entry is always the
            requested page; subsequent entries are subpages (if any).
        """
        page_id = self._extract_page_id(page_id_or_url)
        async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
            return await self._fetch_page(client, page_id, include_children)

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        page_id: str,
        include_children: bool,
    ) -> List[FetchedSource]:
        """Fetch one page and recurse into subpages if requested."""
        title = await self._fetch_page_title(client, page_id)
        content_blocks, child_pages = await self._fetch_page_blocks(client, page_id)
        content = self._blocks_to_markdown(content_blocks)
        url = f"https://www.notion.so/{page_id.replace('-', '')}"

        docs = [FetchedSource(id=page_id, title=title, content=content, url=url)]

        if include_children:
            for child in child_pages:
                try:
                    sub_docs = await self._fetch_page(client, child["id"], include_children=True)
                    docs.extend(sub_docs)
                except Exception as e:
                    logger.warning("Skipping subpage '%s': %s", child["title"], e)

        return docs

    async def _fetch_page_title(self, client: httpx.AsyncClient, page_id: str) -> str:
        """Fetch the title of a Notion page from its properties."""
        try:
            response = await client.get(f"{_NOTION_API}/pages/{page_id}")
            if response.status_code != 200:
                return "Untitled"
            data = response.json()
            props = data.get("properties", {})
            # Title property can be named "title" or "Name" depending on page type
            title_prop = props.get("title") or props.get("Name") or {}
            title_items = title_prop.get("title", [])
            return "".join(item.get("plain_text", "") for item in title_items) or "Untitled"
        except Exception:
            return "Untitled"

    async def _fetch_page_blocks(
        self,
        client: httpx.AsyncClient,
        block_id: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """Fetch all content blocks and collect child-page references.

        Returns:
            Tuple of (content_blocks, child_page_infos).
            content_blocks: blocks that form the page body (recursively populated).
            child_page_infos: list of {"id": ..., "title": ...} for subpages.
        """
        content_blocks: List[Dict[str, Any]] = []
        child_pages: List[Dict[str, str]] = []
        cursor: Optional[str] = None

        while True:
            data = await self._request_blocks(client, block_id, cursor)

            for block in data.get("results", []):
                if block.get("type") == "child_page":
                    # Subpages are separate documents — don't embed their content
                    child_pages.append(
                        {
                            "id": block["id"],
                            "title": block.get("child_page", {}).get("title", "Untitled"),
                        }
                    )
                else:
                    content_blocks.append(block)
                    if block.get("has_children"):
                        sub_blocks, _ = await self._fetch_page_blocks(client, block["id"])
                        block["_children"] = sub_blocks

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

        return content_blocks, child_pages

    async def _request_blocks(
        self,
        client: httpx.AsyncClient,
        block_id: str,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Single API call to fetch one page of blocks with error handling."""
        params: Dict[str, Any] = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor

        response = await client.get(f"{_NOTION_API}/blocks/{block_id}/children", params=params)

        if response.status_code == 404:
            raise ValueError(
                f"Notion page '{block_id}' not found or not accessible. "
                "Make sure you have shared the page with your Notion integration: "
                "open the page in Notion → ··· menu → Connections → Add connections."
            )
        if response.status_code == 401:
            raise ValueError("Invalid Notion token. Please check your NOTION_TOKEN credentials.")
        if response.status_code == 403:
            raise ValueError(
                f"Access denied to Notion page '{block_id}'. "
                "Share the page with your integration before importing."
            )

        response.raise_for_status()
        return response.json()

    @staticmethod
    def _extract_page_id(input: str) -> str:
        """Normalize a Notion page ID or URL to UUID format with dashes.

        Accepts:
        - Full Notion URL: https://www.notion.so/Page-Title-30515268a407818fa99bce93e0a7f172
        - Raw 32-char ID:  30515268a407818fa99bce93e0a7f172
        - UUID format:     30515268-a407-818f-a99b-ce93e0a7f172

        Raises:
            ValueError: If the input is a non-Notion URL or does not contain a valid page ID.
        """
        if input.startswith("http"):
            from urllib.parse import urlparse

            host = urlparse(input).hostname or ""
            if not (host == "notion.so" or host.endswith(".notion.so")):
                raise ValueError(
                    f"Expected a Notion URL (notion.so) but got: {input!r}. "
                    "Make sure you selected the correct tool for this URL."
                )
            path = input.split("?")[0].rstrip("/")
            last_segment = path.split("/")[-1]
            raw = re.sub(r"[^a-f0-9]", "", last_segment.lower())[-32:]
        else:
            raw = input.replace("-", "").lower()

        if len(raw) == 32:
            return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"

        raise ValueError(
            f"Could not extract a Notion page ID from: {input!r}. "
            "Please provide a valid Notion page URL or ID."
        )

    def _rich_text_to_str(self, rich_text: List[Dict[str, Any]]) -> str:
        return "".join(part.get("plain_text", "") for part in rich_text)

    def _blocks_to_markdown(self, blocks: List[Dict[str, Any]], depth: int = 0) -> str:
        lines = []
        indent = "  " * depth

        for block in blocks:
            block_type = block.get("type", "")
            content = block.get(block_type, {})
            rich_text = content.get("rich_text", [])
            text = self._rich_text_to_str(rich_text)

            if block_type == "heading_1":
                lines.append(f"# {text}")
            elif block_type == "heading_2":
                lines.append(f"## {text}")
            elif block_type == "heading_3":
                lines.append(f"### {text}")
            elif block_type == "paragraph":
                lines.append(text)
            elif block_type == "bulleted_list_item":
                lines.append(f"{indent}- {text}")
            elif block_type == "numbered_list_item":
                lines.append(f"{indent}1. {text}")
            elif block_type == "quote":
                lines.append(f"> {text}")
            elif block_type == "code":
                language = content.get("language", "")
                lines.append(f"```{language}\n{text}\n```")
            elif block_type == "divider":
                lines.append("---")
            elif block_type in ("callout", "toggle"):
                lines.append(text)
            else:
                if text:
                    lines.append(text)

            children = block.get("_children", [])
            if children:
                lines.append(self._blocks_to_markdown(children, depth + 1))

        return "\n\n".join(line for line in lines if line)
