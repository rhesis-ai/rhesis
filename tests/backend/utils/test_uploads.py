"""
📦 Shared upload helpers

Every feature that accepts a file needs the same two guarantees: a bounded body
and a storage failure that says what to fix. These used to be reimplemented per
feature, so the tests live with the shared helper rather than with any one
caller.

Run with: python -m pytest tests/backend/utils/test_uploads.py -v
"""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from rhesis.backend.app.utils.uploads import read_upload_capped, store_bytes


def _upload(content: bytes) -> AsyncMock:
    """An UploadFile stand-in whose read(n) truncates like the real one."""
    upload = AsyncMock()
    upload.read.side_effect = lambda n: content[:n]
    return upload


class TestReadUploadCapped:
    async def test_returns_the_body_within_the_limit(self):
        """✅ The ordinary path hands back exactly what was sent."""
        assert await read_upload_capped(_upload(b"hello"), 1024, "Favicon") == b"hello"

    async def test_accepts_a_body_exactly_at_the_limit(self):
        """✅ The cap is inclusive — an exact fit is not an error."""
        assert await read_upload_capped(_upload(b"x" * 10), 10, "Favicon") == b"x" * 10

    async def test_rejects_an_oversized_body_with_413(self):
        """✅ One byte over is refused."""
        with pytest.raises(HTTPException) as excinfo:
            await read_upload_capped(_upload(b"x" * 11), 10, "Favicon")

        assert excinfo.value.status_code == 413
        assert "Favicon" in excinfo.value.detail

    async def test_reads_only_one_byte_past_the_limit(self):
        """✅ An oversized upload is rejected without buffering all of it.

        Reading the whole body first would let one request exhaust the worker,
        which is the thing the cap exists to prevent.
        """
        upload = _upload(b"x" * 10_000)

        with pytest.raises(HTTPException):
            await read_upload_capped(upload, 10, "Favicon")

        upload.read.assert_awaited_once_with(11)

    async def test_rejects_an_empty_body_with_400(self):
        """✅ An empty file is a bad request, not a size problem."""
        with pytest.raises(HTTPException) as excinfo:
            await read_upload_capped(_upload(b""), 10, "Font file")

        assert excinfo.value.status_code == 400
        assert "Font file" in excinfo.value.detail


class TestStoreBytes:
    def test_passes_through_the_stored_path_and_hash(self):
        """✅ The happy path returns what StorageService returned."""
        storage = Mock()
        storage.put_object_bytes.return_value = ("branding/x/favicon.png", "sha")

        assert store_bytes(storage, b"bytes", "branding/x/favicon.png", "image/png") == (
            "branding/x/favicon.png",
            "sha",
        )

    def test_turns_an_unwritable_path_into_a_503(self):
        """✅ Unwritable storage is a deployment problem, not a bad request.

        The local storage path is a container path under docker-compose and a
        host directory otherwise, so getting it wrong is easy — and the raw
        OSError surfaced as a 500 whose traceback ended in `mkdir`.
        """
        storage = Mock()
        storage.put_object_bytes.side_effect = OSError("Read-only file system: '/app'")

        with pytest.raises(HTTPException) as excinfo:
            store_bytes(storage, b"bytes", "branding/x/favicon.png", "image/png")

        assert excinfo.value.status_code == 503
        assert "STORAGE_SERVICE_URI" in excinfo.value.detail

    def test_survives_a_cloud_backend_raising_its_own_exception_type(self):
        """✅ fsspec's cloud backends raise native types, not OSError."""

        class GcsError(Exception):
            pass

        storage = Mock()
        storage.put_object_bytes.side_effect = GcsError("403 forbidden")

        with pytest.raises(HTTPException) as excinfo:
            store_bytes(storage, b"bytes", "p", "image/png")

        assert excinfo.value.status_code == 503
