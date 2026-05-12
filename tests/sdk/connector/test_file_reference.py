"""Tests for :class:`rhesis.sdk.connector.types.FileReference`.

Covers both ``read_bytes`` (sync, ``urllib``-based) and ``aread_bytes``
(async, ``aiohttp``-based) — including the no-signed-url error path
that callers rely on to detect misuse.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.sdk.connector.types import FileReference


def _make_ref(signed_url: str | None = "https://example.test/file") -> FileReference:
    return FileReference(
        id="abc-123",
        filename="photo.jpeg",
        content_type="image/jpeg",
        size_bytes=42,
        content_hash="deadbeef" * 8,
        storage_path="attachments/abc-123",
        signed_url=signed_url,
        extracted_text="hi",
    )


class TestReadBytesSync:
    def test_fetches_bytes_via_urllib(self):
        ref = _make_ref()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"hello bytes"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            result = ref.read_bytes()

        mock_open.assert_called_once_with("https://example.test/file")
        assert result == b"hello bytes"

    def test_raises_when_signed_url_missing(self):
        ref = _make_ref(signed_url=None)
        with pytest.raises(RuntimeError, match="No signed_url available"):
            ref.read_bytes()


class TestAReadBytesAsync:
    @pytest.mark.asyncio
    async def test_fetches_bytes_via_aiohttp_when_session_none(self):
        ref = _make_ref()

        # Mock the response (async context manager returning .read())
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.read = AsyncMock(return_value=b"async bytes")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        # Mock the ClientSession (async context manager whose .get() returns mock_resp)
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session) as mock_cls:
            result = await ref.aread_bytes()

        mock_cls.assert_called_once_with()
        mock_session.get.assert_called_once_with("https://example.test/file")
        assert result == b"async bytes"

    @pytest.mark.asyncio
    async def test_reuses_provided_session_without_closing_it(self):
        ref = _make_ref()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.read = AsyncMock(return_value=b"reused")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        provided_session = MagicMock()
        provided_session.get = MagicMock(return_value=mock_resp)
        # Crucially: NOT used as an async context manager.
        provided_session.__aenter__ = AsyncMock(side_effect=AssertionError(
            "aread_bytes must not enter/exit a caller-provided session"
        ))
        provided_session.__aexit__ = AsyncMock(side_effect=AssertionError(
            "aread_bytes must not enter/exit a caller-provided session"
        ))

        # ClientSession class must not be instantiated when a session is passed
        with patch("aiohttp.ClientSession") as mock_cls:
            result = await ref.aread_bytes(session=provided_session)

        mock_cls.assert_not_called()
        provided_session.get.assert_called_once_with("https://example.test/file")
        assert result == b"reused"

    @pytest.mark.asyncio
    async def test_raises_when_signed_url_missing(self):
        ref = _make_ref(signed_url=None)
        with pytest.raises(RuntimeError, match="No signed_url available"):
            await ref.aread_bytes()
