"""Tests for the Confluence REST source — ConfluenceRestClient."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from rhesis.backend.app.services.tool.rest.confluence import ConfluenceRestClient


@pytest.mark.unit
@pytest.mark.services
class TestConfluenceInit:
    def test_base_url_trailing_slash_stripped(self):
        client = ConfluenceRestClient(
            base_url="https://test.atlassian.net/",
            username="u@test.com",
            api_token="tok",
        )
        assert client._base_url == "https://test.atlassian.net"
        assert client._auth == ("u@test.com", "tok")


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestConfluenceHealthCheck:
    def _client(self):
        return ConfluenceRestClient(
            base_url="https://test.atlassian.net",
            username="u@test.com",
            api_token="tok",
        )

    async def test_authenticated(self):
        resp = Mock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.return_value = {"displayName": "Jane Doe"}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await self._client().health_check()
        assert result["is_authenticated"] == "Yes"
        assert "Jane Doe" in result["message"]

    async def test_unauthenticated(self):
        resp = Mock(spec=httpx.Response)
        resp.status_code = 403
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await self._client().health_check()
        assert result["is_authenticated"] == "No"
        assert "403" in result["message"]

    async def test_hits_current_user_endpoint(self):
        resp = Mock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.return_value = {"displayName": "X"}
        mock_get = AsyncMock(return_value=resp)
        with patch("httpx.AsyncClient.get", new=mock_get):
            await self._client().health_check()
        called_url = mock_get.call_args[0][0]
        assert called_url == "https://test.atlassian.net/wiki/rest/api/user/current"
