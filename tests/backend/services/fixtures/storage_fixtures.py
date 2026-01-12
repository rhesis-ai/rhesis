"""
Test fixtures for storage service and document handler tests.

This module provides factory classes and pytest fixtures for creating
test data and mock objects for storage-related tests.
"""

import tempfile
from typing import Any, Dict

import pytest

from rhesis.backend.app.services.handlers.document import DocumentHandler
from rhesis.backend.app.services.storage_service import StorageService


class DocumentHandlerDataFactory:
    """Factory for creating document handler test data."""

    @staticmethod
    def sample_data() -> Dict[str, Any]:
        """Return sample document handler data."""
        return {
            "organization_id": "org-sample-123",
            "source_id": "source-sample-456",
            "filename": "sample_document.pdf",
            "content": b"Sample document content for testing",
            "file_size": 32,
            "file_type": "application/pdf",
        }

    @staticmethod
    def minimal_data() -> Dict[str, Any]:
        """Return minimal document handler data."""
        return {
            "organization_id": "org-min",
            "source_id": "src-min",
            "filename": "min.txt",
            "content": b"min",
            "file_size": 3,
            "file_type": "text/plain",
        }

    @staticmethod
    def edge_case_data(case_type: str) -> Dict[str, Any]:
        """Return edge case data for testing."""
        base_data = DocumentHandlerDataFactory.sample_data()

        if case_type == "empty_file":
            base_data["content"] = b""
            base_data["file_size"] = 0
        elif case_type == "large_file":
            base_data["content"] = b"x" * 1000000  # 1MB
            base_data["file_size"] = 1000000
        elif case_type == "unicode_filename":
            base_data["filename"] = "файл_с_кириллицей.pdf"
        elif case_type == "special_chars":
            base_data["filename"] = "file with spaces & symbols!@#.pdf"
        elif case_type == "no_extension":
            base_data["filename"] = "filename_without_extension"

        return base_data


class StorageServiceDataFactory:
    """Factory for creating storage service test data."""

    @staticmethod
    def sample_data() -> Dict[str, Any]:
        """Return sample storage service data."""
        return {
            "organization_id": "org-sample-123",
            "source_id": "source-sample-456",
            "filename": "sample_document.pdf",
            "file_path": "org-sample-123/source-sample-456_sample_document.pdf",
        }

    @staticmethod
    def minimal_data() -> Dict[str, Any]:
        """Return minimal storage service data."""
        return {
            "organization_id": "org-min",
            "source_id": "src-min",
            "filename": "min.txt",
            "file_path": "org-min/src-min_min.txt",
        }

    @staticmethod
    def edge_case_data(case_type: str) -> Dict[str, Any]:
        """Return edge case storage service data."""
        base_data = StorageServiceDataFactory.sample_data()

        if case_type == "local_storage":
            base_data["file_path"] = "/tmp/local-storage/test-file.pdf"
        elif case_type == "production_config":
            base_data["file_path"] = "sources-rhesis-prd/org-123/source-456_test.pdf"
        elif case_type == "missing_credentials":
            base_data["organization_id"] = ""
            base_data["source_id"] = ""
        elif case_type == "long_paths":
            base_data["organization_id"] = "org-" + "x" * 100
            base_data["source_id"] = "source-" + "y" * 100
            base_data["filename"] = "file-" + "z" * 100 + ".txt"

        return base_data


class MockUploadFile:
    """Mock UploadFile for testing document handler operations."""

    def __init__(
        self,
        content: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
    ):
        self.content = content
        self.filename = filename
        self.content_type = content_type
        self.size = len(content)

    async def read(self) -> bytes:
        """Read file content."""
        return self.content

    def __len__(self) -> int:
        """Return file size."""
        return self.size


# Pytest fixtures


@pytest.fixture
def local_storage_service():
    """Create a StorageService configured for local storage."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("LOCAL_STORAGE_PATH", temp_dir)
            mp.setenv("BACKEND_ENV", "test")

            storage_service = StorageService()
            yield storage_service


@pytest.fixture
def document_handler_with_local_storage(local_storage_service):
    """Create a DocumentHandler with local storage service."""
    return DocumentHandler(storage_service=local_storage_service)


@pytest.fixture
def various_file_types():
    """Provide various file types for testing."""
    return [
        ("document.pdf", b"PDF content", "application/pdf"),
        ("image.jpg", b"JPEG content", "image/jpeg"),
        ("text.txt", b"Text content", "text/plain"),
        ("data.json", b'{"key": "value"}', "application/json"),
        (
            "spreadsheet.xlsx",
            b"Excel content",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    ]


@pytest.fixture
def environment_configurations():
    """Provide different environment configurations for testing."""
    return {
        "local": {
            "BACKEND_ENV": "local",
            "LOCAL_STORAGE_PATH": "/tmp/local-test",
        },
        "development": {
            "BACKEND_ENV": "development",
            "STORAGE_SERVICE_URI": "gs://sources-rhesis-dev",
            "STORAGE_SERVICE_ACCOUNT_KEY": "eyJ0eXBlIjoidGVzdCIsInByb2plY3RfaWQiOiJ0ZXN0LXByb2plY3QifQ==",  # base64 encoded test JSON
            "LOCAL_STORAGE_PATH": "/tmp/dev-storage",
        },
        "staging": {
            "BACKEND_ENV": "staging",
            "STORAGE_SERVICE_URI": "gs://sources-rhesis-stg",
            "STORAGE_SERVICE_ACCOUNT_KEY": "eyJ0eXBlIjoidGVzdCIsInByb2plY3RfaWQiOiJ0ZXN0LXByb2plY3QifQ==",  # base64 encoded test JSON
            "LOCAL_STORAGE_PATH": "/tmp/stg-storage",
        },
        "production": {
            "BACKEND_ENV": "production",
            "STORAGE_SERVICE_URI": "gs://sources-rhesis-prd",
            "STORAGE_SERVICE_ACCOUNT_KEY": "eyJ0eXBlIjoidGVzdCIsInByb2plY3RfaWQiOiJ0ZXN0LXByb2plY3QifQ==",  # base64 encoded test JSON
            "LOCAL_STORAGE_PATH": "/tmp/prd-storage",
        },
        "partial_gcs": {
            "BACKEND_ENV": "development",
            "STORAGE_SERVICE_URI": "gs://sources-rhesis-dev",
            # Missing STORAGE_SERVICE_ACCOUNT_KEY to test fallback
            "LOCAL_STORAGE_PATH": "/tmp/fallback-storage",
        },
        "no_gcs": {
            "BACKEND_ENV": "development",
            # Missing both STORAGE_PROJECT_ID and STORAGE_CREDENTIALS_PATH
            "LOCAL_STORAGE_PATH": "/tmp/no-gcs-storage",
        },
    }
