"""Tests for the GitHub REST source — GitHubRestClient and URL parsing."""

import base64
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from rhesis.backend.app.services.tool.rest.github import (
    GitHubRestClient,
    _parse_github_url,
)


@pytest.mark.unit
@pytest.mark.services
class TestParseGithubUrl:
    """Test _parse_github_url for the supported URL shapes."""

    def test_repo_root_defaults_to_main(self):
        api_url, branch = _parse_github_url("https://github.com/owner/repo")
        assert api_url == "https://api.github.com/repos/owner/repo/contents/"
        assert branch == "main"

    def test_blob_url_extracts_branch_and_path(self):
        api_url, branch = _parse_github_url(
            "https://github.com/owner/repo/blob/dev/src/app.py"
        )
        assert api_url == "https://api.github.com/repos/owner/repo/contents/src/app.py"
        assert branch == "dev"

    def test_tree_url_extracts_branch_and_dir(self):
        api_url, branch = _parse_github_url(
            "https://github.com/owner/repo/tree/feature/docs"
        )
        assert api_url == "https://api.github.com/repos/owner/repo/contents/docs"
        assert branch == "feature"

    def test_non_http_raises(self):
        with pytest.raises(ValueError, match="Expected a full GitHub URL"):
            _parse_github_url("owner/repo")

    def test_non_github_host_raises(self):
        with pytest.raises(ValueError, match="Expected a GitHub URL"):
            _parse_github_url("https://gitlab.com/owner/repo")

    def test_missing_repo_raises(self):
        with pytest.raises(ValueError, match="Cannot parse owner/repo"):
            _parse_github_url("https://github.com/owner")


@pytest.mark.unit
@pytest.mark.services
class TestDecode:
    """Test _decode base64 handling."""

    def test_base64_content(self):
        encoded = base64.b64encode(b"hello world").decode()
        data = {"content": encoded, "encoding": "base64"}
        assert GitHubRestClient._decode(data) == "hello world"

    def test_plain_content(self):
        data = {"content": "plain", "encoding": "utf-8"}
        assert GitHubRestClient._decode(data) == "plain"

    def test_missing_content(self):
        assert GitHubRestClient._decode({}) == ""


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestGithubHealthCheck:
    async def test_authenticated(self):
        client = GitHubRestClient(token="t")
        resp = Mock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.return_value = {"login": "octocat"}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await client.health_check()
        assert result["is_authenticated"] == "Yes"
        assert "octocat" in result["message"]

    async def test_unauthenticated(self):
        client = GitHubRestClient(token="bad")
        resp = Mock(spec=httpx.Response)
        resp.status_code = 401
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            result = await client.health_check()
        assert result["is_authenticated"] == "No"
        assert "401" in result["message"]


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestGithubFetch:
    """Test fetch / fetch_all for files, directories, and errors."""

    def _file_payload(self, name, text):
        return {
            "type": "file",
            "name": name,
            "sha": f"sha-{name}",
            "html_url": f"https://github.com/o/r/blob/main/{name}",
            "content": base64.b64encode(text.encode()).decode(),
            "encoding": "base64",
        }

    async def test_fetch_single_file(self):
        client = GitHubRestClient(token="t")
        resp = Mock(spec=httpx.Response)
        resp.status_code = 200
        resp.is_success = True
        resp.raise_for_status = Mock()
        resp.json.return_value = self._file_payload("app.py", "print('hi')")
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            text = await client.fetch("https://github.com/o/r/blob/main/app.py")
        assert "print('hi')" in text

    async def test_fetch_directory_lists_files(self):
        client = GitHubRestClient(token="t")
        listing = [
            {"type": "file", "url": "https://api.github.com/file/a"},
            {"type": "dir", "url": "https://api.github.com/dir/sub"},
        ]

        async def fake_get(self_client, url, *args, **kwargs):
            resp = Mock(spec=httpx.Response)
            resp.status_code = 200
            resp.raise_for_status = Mock()
            if url.endswith("/contents/"):
                resp.json.return_value = listing
            else:  # individual file fetch
                resp.json.return_value = self._file_payload("a.py", "a content")
            return resp

        with patch("httpx.AsyncClient.get", new=fake_get):
            # include_children=False → dir entry is skipped, only the file fetched
            sources = await client.fetch_all(
                "https://github.com/o/r", include_children=False
            )
        assert len(sources) == 1
        assert sources[0].title == "a.py"
        assert sources[0].content == "a content"

    async def test_404_raises(self):
        client = GitHubRestClient(token="t")
        resp = Mock(spec=httpx.Response)
        resp.status_code = 404
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            with pytest.raises(ValueError, match="not found"):
                await client.fetch_all("https://github.com/o/r/blob/main/missing.py")

    async def test_401_raises_invalid_token(self):
        client = GitHubRestClient(token="bad")
        resp = Mock(spec=httpx.Response)
        resp.status_code = 401
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
            with pytest.raises(ValueError, match="Invalid GitHub token"):
                await client.fetch_all("https://github.com/o/r")
