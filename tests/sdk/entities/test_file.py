"""Tests for File entity and file support on Test/TestResult."""

import base64
import os
from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.entities.file import File
from rhesis.sdk.entities.test import Test
from rhesis.sdk.entities.test_result import TestResult

os.environ["RHESIS_BASE_URL"] = "http://test:8000"

SAMPLE_FILE_RESPONSE = {
    "id": "file-001",
    "filename": "photo.jpg",
    "content_type": "image/jpeg",
    "size_bytes": 1024,
    "description": None,
    "entity_id": "test-123",
    "entity_type": "Test",
    "position": 0,
}

SAMPLE_FILE_RESPONSE_2 = {
    "id": "file-002",
    "filename": "doc.pdf",
    "content_type": "application/pdf",
    "size_bytes": 2048,
    "description": None,
    "entity_id": "test-123",
    "entity_type": "Test",
    "position": 1,
}


def test_file_entity_fields():
    """Verify all File fields are correctly set."""
    f = File(
        id="file-001",
        filename="photo.jpg",
        content_type="image/jpeg",
        size_bytes=1024,
        description="A photo",
        entity_id="test-123",
        entity_type="Test",
        position=0,
    )
    assert f.id == "file-001"
    assert f.filename == "photo.jpg"
    assert f.content_type == "image/jpeg"
    assert f.size_bytes == 1024
    assert f.description == "A photo"
    assert f.entity_id == "test-123"
    assert f.entity_type == "Test"
    assert f.position == 0


def test_file_entity_defaults():
    """Verify File defaults are sensible."""
    f = File()
    assert f.filename == ""
    assert f.content_type == ""
    assert f.size_bytes == 0
    assert f.description is None
    assert f.entity_id is None
    assert f.entity_type is None
    assert f.position == 0
    assert f.id is None


@patch("requests.post")
def test_file_add_from_paths(mock_post, tmp_path):
    """File.add() with file paths opens files and sends multipart."""
    # Create a temporary file
    test_file = tmp_path / "photo.jpg"
    test_file.write_bytes(b"fake-image-data")

    mock_response = MagicMock()
    mock_response.json.return_value = [SAMPLE_FILE_RESPONSE]
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    files = File.add(
        sources=[str(test_file)],
        entity_id="test-123",
        entity_type="Test",
    )

    assert len(files) == 1
    assert files[0].id == "file-001"
    assert files[0].filename == "photo.jpg"

    # Verify multipart upload was called
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["url"] == "http://test:8000/files"
    assert kwargs["params"] == {
        "entity_id": "test-123",
        "entity_type": "Test",
    }
    # Verify files parameter structure
    uploaded_files = kwargs["files"]
    assert len(uploaded_files) == 1
    assert uploaded_files[0][0] == "files"
    assert uploaded_files[0][1][0] == "photo.jpg"
    assert uploaded_files[0][1][2] == "image/jpeg"


@patch("requests.post")
def test_file_add_from_base64_dicts(mock_post):
    """File.add() with base64 dicts decodes and sends multipart."""
    b64_data = base64.b64encode(b"fake-png-data").decode()

    mock_response = MagicMock()
    mock_response.json.return_value = [SAMPLE_FILE_RESPONSE]
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    files = File.add(
        sources=[
            {
                "filename": "img.png",
                "content_type": "image/png",
                "data": b64_data,
            }
        ],
        entity_id="test-123",
        entity_type="Test",
    )

    assert len(files) == 1
    assert files[0].id == "file-001"

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    uploaded_files = kwargs["files"]
    assert len(uploaded_files) == 1
    assert uploaded_files[0][0] == "files"
    assert uploaded_files[0][1][0] == "img.png"
    assert uploaded_files[0][1][2] == "image/png"
    # Verify BytesIO content is the decoded bytes
    uploaded_files[0][1][1].seek(0)
    assert uploaded_files[0][1][1].read() == b"fake-png-data"


@patch("requests.post")
def test_file_add_mixed_sources(mock_post, tmp_path):
    """File.add() handles mix of paths and base64 dicts."""
    test_file = tmp_path / "doc.pdf"
    test_file.write_bytes(b"fake-pdf-data")

    b64_data = base64.b64encode(b"fake-png-data").decode()

    mock_response = MagicMock()
    mock_response.json.return_value = [
        SAMPLE_FILE_RESPONSE,
        SAMPLE_FILE_RESPONSE_2,
    ]
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    files = File.add(
        sources=[
            str(test_file),
            {
                "filename": "img.png",
                "content_type": "image/png",
                "data": b64_data,
            },
        ],
        entity_id="test-123",
        entity_type="Test",
    )

    assert len(files) == 2
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    uploaded_files = kwargs["files"]
    assert len(uploaded_files) == 2


@patch("requests.request")
def test_file_download_writes_to_disk(mock_request, tmp_path):
    """File.download() saves content to the specified directory."""
    mock_response = MagicMock()
    mock_response.content = b"binary-file-content"
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    f = File(id="file-001", filename="photo.jpg")
    result_path = f.download(directory=str(tmp_path))

    assert result_path == tmp_path / "photo.jpg"
    assert result_path.read_bytes() == b"binary-file-content"

    mock_request.assert_called_once_with(
        method="GET",
        url="http://test:8000/files/file-001/content",
        headers={"Authorization": "Bearer rh-test-token"},
    )


def test_file_download_requires_id():
    """File.download() raises ValueError without an ID."""
    f = File(filename="photo.jpg")
    with pytest.raises(ValueError, match="File ID is required"):
        f.download()


@patch("requests.request")
def test_file_delete(mock_request):
    """File.delete() sends DELETE request."""
    mock_response = MagicMock()
    mock_response.json.return_value = {}
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    f = File(id="file-001", filename="photo.jpg")
    result = f.delete()

    assert result is True
    mock_request.assert_called_once_with(
        method="DELETE",
        url="http://test:8000/files/file-001",
        headers={
            "Authorization": "Bearer rh-test-token",
            "Content-Type": "application/json",
        },
        json=None,
        params=None,
    )


def test_file_push_raises():
    """File.push() raises NotImplementedError."""
    f = File(filename="photo.jpg")
    with pytest.raises(NotImplementedError, match="File.add"):
        f.push()


@patch("requests.post")
def test_test_add_files(mock_post):
    """Test.add_files() delegates to File.add()."""
    mock_response = MagicMock()
    mock_response.json.return_value = [SAMPLE_FILE_RESPONSE]
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    b64_data = base64.b64encode(b"data").decode()
    test = Test(
        id="test-123",
        category="safety",
        behavior="jailbreak",
    )
    files = test.add_files(
        [
            {
                "filename": "img.png",
                "content_type": "image/png",
                "data": b64_data,
            }
        ]
    )

    assert len(files) == 1
    assert files[0].id == "file-001"
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["params"]["entity_id"] == "test-123"
    assert kwargs["params"]["entity_type"] == "Test"


@patch("requests.request")
def test_test_get_files(mock_request):
    """Test.get_files() returns list of File instances."""
    mock_response = MagicMock()
    mock_response.json.return_value = [
        SAMPLE_FILE_RESPONSE,
        SAMPLE_FILE_RESPONSE_2,
    ]
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    test = Test(
        id="test-123",
        category="safety",
        behavior="jailbreak",
    )
    files = test.get_files()

    assert len(files) == 2
    assert files[0].filename == "photo.jpg"
    assert files[1].filename == "doc.pdf"
    mock_request.assert_called_once_with(
        method="GET",
        url="http://test:8000/tests/test-123/files",
        headers={
            "Authorization": "Bearer rh-test-token",
            "Content-Type": "application/json",
        },
        json=None,
        params=None,
    )


@patch("requests.post")
@patch("requests.request")
def test_test_push_with_files(mock_request, mock_post, tmp_path):
    """Test(files=[...]).push() creates test then uploads files."""
    # Mock the create request (POST to /tests)
    create_response = MagicMock()
    create_response.json.return_value = {
        "id": "test-new",
        "category": "safety",
        "behavior": "jailbreak",
    }
    create_response.raise_for_status = MagicMock()
    mock_request.return_value = create_response

    # Mock the file upload (POST to /files)
    upload_response = MagicMock()
    upload_response.json.return_value = [SAMPLE_FILE_RESPONSE]
    upload_response.raise_for_status = MagicMock()
    mock_post.return_value = upload_response

    test_file = tmp_path / "photo.jpg"
    test_file.write_bytes(b"fake-image")

    test = Test(
        category="safety",
        behavior="jailbreak",
        files=[str(test_file)],
    )
    test.push()

    # Verify test was created first
    mock_request.assert_called_once()
    req_kwargs = mock_request.call_args
    assert req_kwargs.kwargs["method"] == "POST"
    assert req_kwargs.kwargs["url"] == "http://test:8000/tests"
    # Verify files were NOT included in the JSON body
    assert "files" not in req_kwargs.kwargs["json"]

    # Verify file upload happened
    mock_post.assert_called_once()
    _, upload_kwargs = mock_post.call_args
    assert upload_kwargs["params"]["entity_id"] == "test-new"
    assert upload_kwargs["params"]["entity_type"] == "Test"

    # Verify files field was cleared after push
    assert test.files is None


@patch("requests.request")
def test_test_result_get_files(mock_request):
    """TestResult.get_files() returns list of File instances."""
    response_data = [
        {
            **SAMPLE_FILE_RESPONSE,
            "entity_type": "TestResult",
            "entity_id": "result-123",
        }
    ]
    mock_response = MagicMock()
    mock_response.json.return_value = response_data
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = TestResult(id="result-123")
    files = result.get_files()

    assert len(files) == 1
    assert files[0].filename == "photo.jpg"
    mock_request.assert_called_once_with(
        method="GET",
        url="http://test:8000/test_results/result-123/files",
        headers={
            "Authorization": "Bearer rh-test-token",
            "Content-Type": "application/json",
        },
        json=None,
        params=None,
    )


def test_test_add_files_requires_id():
    """Test.add_files() raises ValueError without an ID."""
    test = Test(category="safety", behavior="jailbreak")
    with pytest.raises(ValueError, match="Test must have an ID"):
        test.add_files(["photo.jpg"])


def test_test_get_files_requires_id():
    """Test.get_files() raises ValueError without an ID."""
    test = Test(category="safety", behavior="jailbreak")
    with pytest.raises(ValueError, match="Test must have an ID"):
        test.get_files()


def test_test_result_get_files_requires_id():
    """TestResult.get_files() raises ValueError without an ID."""
    result = TestResult()
    with pytest.raises(ValueError, match="TestResult must have an ID"):
        result.get_files()
