"""
Base classes for storage service tests.

This module provides base classes that follow the established patterns
from other test modules, ensuring consistency across the test suite.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock

from rhesis.backend.app.services.handlers.document import DocumentHandler
from rhesis.backend.app.services.storage_service import StorageService


class BaseStorageServiceTests(ABC):
    """Base class for storage service tests following established patterns."""

    @abstractmethod
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample data for testing."""
        pass

    @abstractmethod
    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal required data for testing."""
        pass

    @abstractmethod
    def get_edge_case_data(self, case_type: str) -> Dict[str, Any]:
        """Return edge case data for boundary testing."""
        pass


class BaseDocumentHandlerTests(ABC):
    """Base class for document handler tests following established patterns."""

    @abstractmethod
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample document data for testing."""
        pass

    @abstractmethod
    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal document data for testing."""
        pass

    @abstractmethod
    def get_edge_case_data(self, case_type: str) -> Dict[str, Any]:
        """Return edge case document data for boundary testing."""
        pass


class BaseStorageIntegrationTests(ABC):
    """Base class for storage integration tests."""

    @abstractmethod
    def get_test_organization_id(self) -> str:
        """Return test organization ID."""
        pass

    @abstractmethod
    def get_test_source_id(self) -> str:
        """Return test source ID."""
        pass

    @abstractmethod
    def get_test_filename(self) -> str:
        """Return test filename."""
        pass

    @abstractmethod
    def get_test_content(self) -> bytes:
        """Return test file content."""
        pass


# Mixin classes for common test functionality
class StorageServiceTestMixin:
    """Mixin providing common storage service test functionality."""

    def create_mock_storage_service(self, **overrides) -> MagicMock:
        """Create a mock storage service with default configuration."""
        mock_service = MagicMock(spec=StorageService)
        mock_service.bucket_name = "test-bucket"
        mock_service.project_id = "test-project"
        mock_service.credentials_path = "/path/to/credentials.json"
        mock_service.storage_path = "/tmp/test-storage"
        mock_service.use_gcs = True
        mock_service.fs = MagicMock()

        # Mock async methods
        mock_service.save_file = AsyncMock(return_value="test/path/file.txt")
        mock_service.get_file = AsyncMock(return_value=b"test file content")
        mock_service.delete_file = AsyncMock(return_value=True)

        # Mock sync methods
        mock_service.file_exists.return_value = True
        mock_service.get_file_size.return_value = 1024
        mock_service.get_file_path.return_value = "test/path/file.txt"

        # Apply overrides
        for key, value in overrides.items():
            setattr(mock_service, key, value)

        return mock_service


class DocumentHandlerTestMixin:
    """Mixin providing common document handler test functionality."""

    def create_mock_document_handler(
        self, storage_service: Optional[StorageService] = None, **overrides
    ) -> DocumentHandler:
        """Create a document handler with optional storage service."""
        if storage_service is None:
            storage_service = self.create_mock_storage_service()

        handler = DocumentHandler(storage_service=storage_service)

        # Apply overrides
        for key, value in overrides.items():
            setattr(handler, key, value)

        return handler

    def create_mock_storage_service(self, **overrides) -> MagicMock:
        """Create a mock storage service (delegates to StorageServiceTestMixin)."""
        mixin = StorageServiceTestMixin()
        return mixin.create_mock_storage_service(**overrides)


class StorageIntegrationTestMixin:
    """Mixin providing common integration test functionality."""

    def create_test_file_data(
        self, size_bytes: int = 1024, filename: str = "test.txt"
    ) -> Dict[str, Any]:
        """Create test file data for integration tests."""
        return {
            "content": b"x" * size_bytes,
            "filename": filename,
            "organization_id": "org-integration-test",
            "source_id": "source-integration-test",
        }

    def create_large_file_data(self, size_mb: int = 1) -> Dict[str, Any]:
        """Create large file data for performance testing."""
        return self.create_test_file_data(
            size_bytes=size_mb * 1024 * 1024, filename=f"large_file_{size_mb}mb.txt"
        )

    def create_multiple_file_data(self, count: int = 3) -> list[Dict[str, Any]]:
        """Create multiple file data for batch testing."""
        return [
            self.create_test_file_data(filename=f"file_{i}.txt", size_bytes=1024 * (i + 1))
            for i in range(count)
        ]
