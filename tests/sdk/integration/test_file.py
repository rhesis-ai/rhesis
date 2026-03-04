"""Integration tests for File entity and file support on Test/TestResult."""

import base64

import pytest

from rhesis.sdk.entities.file import File
from rhesis.sdk.entities.prompt import Prompt
from rhesis.sdk.entities.test import Test

# Minimal valid PNG (1x1 pixel, transparent)
MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

# Minimal valid PDF
MINIMAL_PDF = (
    b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]"
    b"/Parent 2 0 R>>endobj\n"
    b"xref\n0 4\n"
    b"0000000000 65535 f \n0000000009 00000 n \n"
    b"0000000058 00000 n \n0000000115 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n190\n%%EOF"
)


@pytest.fixture
def test_with_id(db_cleanup):
    """Create and push a Test, returning it with a valid ID."""
    test = Test(
        category="Safety",
        behavior="Refusal",
        prompt=Prompt(content="Test prompt for file tests"),
    )
    test.push()
    assert test.id is not None
    return test


# ============================================================================
# File.add() — upload from file paths
# ============================================================================


def test_file_add_from_path(test_with_id, tmp_path):
    """Upload a file from a local path and verify metadata."""
    img_path = tmp_path / "test_image.png"
    img_path.write_bytes(MINIMAL_PNG)

    files = test_with_id.add_files([str(img_path)])

    assert len(files) == 1
    f = files[0]
    assert f.id is not None
    assert f.filename == "test_image.png"
    assert f.content_type == "image/png"
    assert f.size_bytes > 0
    assert f.entity_id is not None
    assert f.entity_type == "Test"


def test_file_add_multiple_from_paths(test_with_id, tmp_path):
    """Upload multiple files from paths in a single call."""
    img_path = tmp_path / "image.png"
    img_path.write_bytes(MINIMAL_PNG)
    pdf_path = tmp_path / "document.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)

    files = test_with_id.add_files([str(img_path), str(pdf_path)])

    assert len(files) == 2
    filenames = {f.filename for f in files}
    assert "image.png" in filenames
    assert "document.pdf" in filenames


# ============================================================================
# File.add() — upload from base64 dicts
# ============================================================================


def test_file_add_from_base64(test_with_id):
    """Upload a file from a base64-encoded dict."""
    b64_data = base64.b64encode(MINIMAL_PNG).decode()

    files = test_with_id.add_files(
        [
            {
                "filename": "b64_image.png",
                "content_type": "image/png",
                "data": b64_data,
            }
        ]
    )

    assert len(files) == 1
    f = files[0]
    assert f.id is not None
    assert f.filename == "b64_image.png"
    assert f.content_type == "image/png"
    assert f.size_bytes == len(MINIMAL_PNG)


# ============================================================================
# File.add() — mixed sources
# ============================================================================


def test_file_add_mixed_sources(test_with_id, tmp_path):
    """Upload from both a path and a base64 dict in a single call."""
    pdf_path = tmp_path / "mixed.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    b64_data = base64.b64encode(MINIMAL_PNG).decode()

    files = test_with_id.add_files(
        [
            str(pdf_path),
            {
                "filename": "mixed_image.png",
                "content_type": "image/png",
                "data": b64_data,
            },
        ]
    )

    assert len(files) == 2
    filenames = {f.filename for f in files}
    assert "mixed.pdf" in filenames
    assert "mixed_image.png" in filenames


# ============================================================================
# Test.get_files()
# ============================================================================


def test_get_files_returns_uploaded(test_with_id, tmp_path):
    """get_files() returns previously uploaded files."""
    img_path = tmp_path / "retrieve_me.png"
    img_path.write_bytes(MINIMAL_PNG)

    test_with_id.add_files([str(img_path)])
    files = test_with_id.get_files()

    assert len(files) >= 1
    assert any(f.filename == "retrieve_me.png" for f in files)


def test_get_files_empty_when_none_uploaded(test_with_id):
    """get_files() returns empty list when no files attached."""
    files = test_with_id.get_files()
    assert files == []


# ============================================================================
# File.download()
# ============================================================================


def test_file_download(test_with_id, tmp_path):
    """Download a file and verify content matches."""
    img_path = tmp_path / "download_me.png"
    img_path.write_bytes(MINIMAL_PNG)

    files = test_with_id.add_files([str(img_path)])
    f = files[0]

    download_dir = tmp_path / "downloads"
    saved_path = f.download(directory=str(download_dir))

    assert saved_path.exists()
    assert saved_path.name == "download_me.png"
    assert saved_path.read_bytes() == MINIMAL_PNG


# ============================================================================
# File.delete()
# ============================================================================


def test_file_delete(test_with_id, tmp_path):
    """Delete a file and verify it no longer appears in get_files()."""
    img_path = tmp_path / "delete_me.png"
    img_path.write_bytes(MINIMAL_PNG)

    files = test_with_id.add_files([str(img_path)])
    file_id = files[0].id

    result = test_with_id.delete_file(file_id)
    assert result is True

    remaining = test_with_id.get_files()
    assert not any(f.id == file_id for f in remaining)


# ============================================================================
# Test.push() with files=[] inline
# ============================================================================


def test_push_with_inline_files(db_cleanup, tmp_path):
    """Test(files=[...]).push() creates test then uploads files."""
    img_path = tmp_path / "inline.png"
    img_path.write_bytes(MINIMAL_PNG)

    test = Test(
        category="Safety",
        behavior="Refusal",
        prompt=Prompt(content="Inline file test"),
        files=[str(img_path)],
    )
    test.push()

    assert test.id is not None
    assert test.files is None  # Cleared after push

    files = test.get_files()
    assert len(files) == 1
    assert files[0].filename == "inline.png"


def test_push_with_inline_base64_files(db_cleanup):
    """Test(files=[base64_dict]).push() creates test then uploads."""
    b64_data = base64.b64encode(MINIMAL_PNG).decode()

    test = Test(
        category="Safety",
        behavior="Refusal",
        prompt=Prompt(content="Inline base64 file test"),
        files=[
            {
                "filename": "inline_b64.png",
                "content_type": "image/png",
                "data": b64_data,
            }
        ],
    )
    test.push()

    assert test.id is not None
    files = test.get_files()
    assert len(files) == 1
    assert files[0].filename == "inline_b64.png"


# ============================================================================
# File.push() raises NotImplementedError
# ============================================================================


def test_file_push_raises():
    """File.push() should always raise NotImplementedError."""
    f = File(filename="nope.png")
    with pytest.raises(NotImplementedError, match="File.add"):
        f.push()


# ============================================================================
# Error handling
# ============================================================================


def test_add_files_without_test_id():
    """add_files() raises ValueError when test has no ID."""
    test = Test(category="Safety", behavior="Refusal")
    with pytest.raises(ValueError, match="Test must have an ID"):
        test.add_files(["anything.png"])


def test_get_files_without_test_id():
    """get_files() raises ValueError when test has no ID."""
    test = Test(category="Safety", behavior="Refusal")
    with pytest.raises(ValueError, match="Test must have an ID"):
        test.get_files()


def test_download_without_file_id():
    """download() raises ValueError when file has no ID."""
    f = File(filename="no_id.png")
    with pytest.raises(ValueError, match="File ID is required"):
        f.download()
