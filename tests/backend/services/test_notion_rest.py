"""Tests for the Notion REST source — NotionRestClient."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from rhesis.backend.app.services.tool.rest.notion import NotionRestClient


@pytest.mark.unit
@pytest.mark.services
class TestExtractPageId:
    """Test _extract_page_id URL/ID normalization and validation."""

    def test_raw_32_char_id(self):
        raw = "30515268a407818fa99bce93e0a7f172"
        assert (
            NotionRestClient._extract_page_id(raw)
            == "30515268-a407-818f-a99b-ce93e0a7f172"
        )

    def test_already_dashed_uuid(self):
        uuid_str = "30515268-a407-818f-a99b-ce93e0a7f172"
        assert NotionRestClient._extract_page_id(uuid_str) == uuid_str

    def test_full_notion_url(self):
        url = "https://www.notion.so/Page-Title-30515268a407818fa99bce93e0a7f172"
        assert (
            NotionRestClient._extract_page_id(url)
            == "30515268-a407-818f-a99b-ce93e0a7f172"
        )

    def test_url_with_query_string(self):
        url = "https://www.notion.so/My-Page-30515268a407818fa99bce93e0a7f172?pvs=4"
        assert (
            NotionRestClient._extract_page_id(url)
            == "30515268-a407-818f-a99b-ce93e0a7f172"
        )

    def test_non_notion_url_raises(self):
        with pytest.raises(ValueError, match="Expected a Notion URL"):
            NotionRestClient._extract_page_id("https://github.com/owner/repo")

    def test_invalid_id_raises(self):
        with pytest.raises(ValueError, match="Could not extract a Notion page ID"):
            NotionRestClient._extract_page_id("not-a-valid-id")


@pytest.mark.unit
@pytest.mark.services
class TestBlocksToMarkdown:
    """Test _blocks_to_markdown rendering."""

    def _block(self, block_type, text, **extra):
        return {"type": block_type, block_type: {"rich_text": _rt(text), **extra}}

    def test_headings_and_paragraph(self):
        client = NotionRestClient(token="t")
        blocks = [
            self._block("heading_1", "Title"),
            self._block("heading_2", "Sub"),
            self._block("paragraph", "Body text"),
        ]
        md = client._blocks_to_markdown(blocks)
        assert "# Title" in md
        assert "## Sub" in md
        assert "Body text" in md

    def test_list_items_and_quote(self):
        client = NotionRestClient(token="t")
        blocks = [
            self._block("bulleted_list_item", "item a"),
            self._block("numbered_list_item", "item b"),
            self._block("quote", "wise words"),
        ]
        md = client._blocks_to_markdown(blocks)
        assert "- item a" in md
        assert "1. item b" in md
        assert "> wise words" in md

    def test_code_block_with_language(self):
        client = NotionRestClient(token="t")
        block = {"type": "code", "code": {"rich_text": _rt("print(1)"), "language": "python"}}
        md = client._blocks_to_markdown([block])
        assert "```python" in md
        assert "print(1)" in md

    def test_divider(self):
        client = NotionRestClient(token="t")
        md = client._blocks_to_markdown([{"type": "divider", "divider": {}}])
        assert md == "---"

    def test_nested_children_are_indented(self):
        client = NotionRestClient(token="t")
        parent = self._block("bulleted_list_item", "parent")
        parent["_children"] = [self._block("bulleted_list_item", "child")]
        md = client._blocks_to_markdown([parent])
        assert "- parent" in md
        assert "  - child" in md

    def test_empty_blocks_skipped(self):
        client = NotionRestClient(token="t")
        md = client._blocks_to_markdown([self._block("paragraph", "")])
        assert md == ""


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestNotionHealthCheck:
    """Test health_check credential verification."""

    async def test_authenticated(self):
        client = NotionRestClient(token="t")
        resp = Mock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.return_value = {"name": "My Bot"}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await client.health_check()
        assert result["is_authenticated"] == "Yes"
        assert "My Bot" in result["message"]

    async def test_unauthenticated(self):
        client = NotionRestClient(token="bad")
        resp = Mock(spec=httpx.Response)
        resp.status_code = 401
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await client.health_check()
        assert result["is_authenticated"] == "No"
        assert "401" in result["message"]


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestNotionRequestBlocks:
    """Test _request_blocks HTTP status mapping."""

    async def _run(self, status_code):
        client = NotionRestClient(token="t")
        resp = Mock(spec=httpx.Response)
        resp.status_code = status_code
        async with httpx.AsyncClient() as http:
            with patch.object(http, "get", new_callable=AsyncMock, return_value=resp):
                return await client._request_blocks(http, "block-id")

    async def test_404_raises_not_found(self):
        with pytest.raises(ValueError, match="not found or not accessible"):
            await self._run(404)

    async def test_401_raises_invalid_token(self):
        with pytest.raises(ValueError, match="Invalid Notion token"):
            await self._run(401)

    async def test_403_raises_access_denied(self):
        with pytest.raises(ValueError, match="Access denied"):
            await self._run(403)


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestNotionFetch:
    """Test fetch / fetch_all end-to-end with a mocked HTTP client."""

    async def test_fetch_returns_markdown(self):
        page_id = "30515268-a407-818f-a99b-ce93e0a7f172"

        async def fake_get(self_client, url, *args, **kwargs):
            resp = Mock(spec=httpx.Response)
            resp.status_code = 200
            if "/pages/" in url:
                resp.json.return_value = {
                    "properties": {"title": {"title": _rt("My Page")}}
                }
            else:  # /blocks/{id}/children
                resp.json.return_value = {
                    "results": [
                        {"type": "heading_1", "heading_1": {"rich_text": _rt("Hello")}},
                        {"type": "paragraph", "paragraph": {"rich_text": _rt("World")}},
                    ],
                    "has_more": False,
                }
            return resp

        client = NotionRestClient(token="t")
        with patch("httpx.AsyncClient.get", new=fake_get):
            text = await client.fetch(page_id)

        assert "# Hello" in text
        assert "World" in text

    async def test_fetch_all_collects_subpages(self):
        async def fake_get(self_client, url, *args, **kwargs):
            resp = Mock(spec=httpx.Response)
            resp.status_code = 200
            if "/pages/" in url:
                resp.json.return_value = {
                    "properties": {"title": {"title": _rt("Parent")}}
                }
            elif "/blocks/parentid/children" in url or "parent" in url.lower():
                resp.json.return_value = {
                    "results": [
                        {
                            "type": "child_page",
                            "id": "childid",
                            "child_page": {"title": "Child"},
                        }
                    ],
                    "has_more": False,
                }
            else:  # child blocks
                resp.json.return_value = {
                    "results": [
                        {"type": "paragraph", "paragraph": {"rich_text": _rt("sub")}}
                    ],
                    "has_more": False,
                }
            return resp

        client = NotionRestClient(token="t")
        # _extract_page_id normalizes; use a value whose dashed form contains "parentid" loosely
        with patch.object(client, "_extract_page_id", return_value="parentid"):
            with patch("httpx.AsyncClient.get", new=fake_get):
                docs = await client.fetch_all("parentid", include_children=True)

        assert len(docs) == 2
        assert docs[0].title == "Parent"
        assert docs[1].id == "childid"


def _rt(text):
    """Build a Notion rich_text array containing one plain-text run."""
    return [{"plain_text": text}] if text else []
