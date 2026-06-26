"""Tests for the file_bytes_and_type/file_extracted_text helpers in _file_compat.py."""

import asyncio
import base64

import pytest

from rhesis.penelope._file_compat import (
    afile_bytes_and_type,
    file_bytes_and_type,
    file_extracted_text,
)


class _FakeFileReference:
    def __init__(self, content_type, content, extracted_text=None):
        self.content_type = content_type
        self._content = content
        self.extracted_text = extracted_text

    def read_bytes(self):
        return self._content

    async def aread_bytes(self):
        return self._content


def test_file_bytes_and_type_dict():
    file = {"content_type": "image/png", "data": base64.b64encode(b"abc").decode()}
    data, content_type = file_bytes_and_type(file)
    assert data == b"abc"
    assert content_type == "image/png"


def test_file_bytes_and_type_dict_missing_content_type_defaults():
    file = {"data": base64.b64encode(b"abc").decode()}
    _, content_type = file_bytes_and_type(file)
    assert content_type == "application/octet-stream"


def test_file_bytes_and_type_file_reference():
    file = _FakeFileReference("application/pdf", b"pdf-bytes")
    data, content_type = file_bytes_and_type(file)
    assert data == b"pdf-bytes"
    assert content_type == "application/pdf"


def test_afile_bytes_and_type_dict():
    file = {"content_type": "image/png", "data": base64.b64encode(b"abc").decode()}
    data, content_type = asyncio.run(afile_bytes_and_type(file))
    assert data == b"abc"
    assert content_type == "image/png"


def test_afile_bytes_and_type_file_reference_uses_aread_bytes():
    file = _FakeFileReference("application/pdf", b"pdf-bytes")
    data, content_type = asyncio.run(afile_bytes_and_type(file))
    assert data == b"pdf-bytes"
    assert content_type == "application/pdf"


def test_file_extracted_text_dict_returns_none():
    assert file_extracted_text({"data": "abc"}) is None


def test_file_extracted_text_file_reference_present():
    file = _FakeFileReference("application/pdf", b"unused", extracted_text="Hello from PDF")
    assert file_extracted_text(file) == "Hello from PDF"


def test_file_extracted_text_file_reference_absent():
    file = _FakeFileReference("application/pdf", b"unused")
    assert file_extracted_text(file) is None


@pytest.mark.parametrize("missing_key", [{"content_type": "image/png"}])
def test_file_bytes_and_type_dict_without_data_raises(missing_key):
    with pytest.raises(KeyError):
        file_bytes_and_type(missing_key)
