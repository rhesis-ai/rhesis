"""
Tests for StorageService class.

This module tests the low-level file storage operations with Google Cloud Storage
and backend storage, following the established patterns from other test modules
with factory-based data generation and base class inheritance.
"""

import os
from typing import Any, Dict
from unittest.mock import MagicMock, mock_open, patch

import pytest

from rhesis.backend.app.services.storage_service import StorageService

from .base import BaseStorageServiceTests, StorageServiceTestMixin

# Import test fixtures and base classes
from .fixtures.storage_fixtures import (
    StorageServiceDataFactory,
    local_storage_service,  # noqa: F401
)


class StorageServiceTestMixin(StorageServiceTestMixin):
    """Enhanced storage service test mixin using factory system."""

    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample storage service data using factory."""
        return StorageServiceDataFactory.sample_data()

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal storage service data using factory."""
        return StorageServiceDataFactory.minimal_data()

    def get_edge_case_data(self, case_type: str) -> Dict[str, Any]:
        """Return edge case storage service data using factory."""
        return StorageServiceDataFactory.edge_case_data(case_type)


@pytest.mark.unit
@pytest.mark.service
class TestStorageServiceInitialization(StorageServiceTestMixin, BaseStorageServiceTests):
    """Test StorageService initialization and configuration."""

    def test_init_without_gcs_configuration(self):
        """Test initialization without GCS configuration (local storage)."""
        with patch.dict(
            os.environ,
            {"BACKEND_ENV": "local", "LOCAL_STORAGE_PATH": "/tmp/test-storage"},
            clear=True,
        ):
            storage_service = StorageService()

            assert storage_service.storage_uri is None
            assert storage_service.service_account_key is None
            assert storage_service.storage_path == "/tmp/test-storage"
            assert storage_service.use_cloud_storage is False

    def test_init_partial_gcs_configuration(self):
        """Test initialization with partial GCS configuration (should fallback to local)."""
        with patch.dict(
            os.environ,
            {
                "BACKEND_ENV": "development",
                "STORAGE_SERVICE_URI": "gs://sources-rhesis-dev",
                "LOCAL_STORAGE_PATH": "/tmp/test-storage",
            },
            clear=True,
        ):
            storage_service = StorageService()

            assert storage_service.storage_uri == "gs://sources-rhesis-dev"
            assert storage_service.service_account_key is None
            assert storage_service.use_cloud_storage is False

    @patch("rhesis.backend.app.services.storage_service.fsspec.filesystem")
    def test_file_system_initialization_gcs(self, mock_fsspec):
        """Test file system initialization for GCS."""
        mock_fs = MagicMock()
        mock_fsspec.return_value = mock_fs

        with patch.dict(
            os.environ,
            {
                "BACKEND_ENV": "production",
                "STORAGE_SERVICE_URI": "gs://sources-rhesis-prd",
                "STORAGE_SERVICE_ACCOUNT_KEY": "eyJ0eXBlIjoidGVzdCIsInByb2plY3RfaWQiOiJ0ZXN0LXByb2plY3QifQ==",
            },
            clear=True,
        ):
            # Mock the service account creation to avoid actual GCS calls
            with patch("rhesis.backend.app.services.storage_service.service_account"):
                storage_service = StorageService()

            # The service should successfully initialize with cloud storage when credentials are provided
            assert storage_service.storage_uri == "gs://sources-rhesis-prd"
            assert (
                storage_service.use_cloud_storage is True
            )  # Successfully initialized with mocked credentials

    @patch("rhesis.backend.app.services.storage_service.fsspec.filesystem")
    def test_file_system_initialization_local(self, mock_fsspec):
        """Test file system initialization for local storage."""
        mock_fs = MagicMock()
        mock_fsspec.return_value = mock_fs

        with patch.dict(os.environ, {"BACKEND_ENV": "local"}, clear=True):
            storage_service = StorageService()

            mock_fsspec.assert_called_once_with("file")
            assert storage_service.fs == mock_fs


@pytest.mark.unit
@pytest.mark.service
class TestStorageServiceFilePaths(StorageServiceTestMixin, BaseStorageServiceTests):
    """Test file path generation methods."""

    @patch("rhesis.backend.app.services.storage_service.Path")
    def test_get_file_path_local(self, mock_path):
        """Test file path generation for local storage."""
        mock_storage_dir = MagicMock()
        mock_path.return_value.__truediv__.return_value = mock_storage_dir
        mock_storage_dir.mkdir.return_value = None
        mock_storage_dir.__truediv__.return_value = "/tmp/rhesis-files/org-123/source-456_test.pdf"

        with patch.dict(
            os.environ,
            {"BACKEND_ENV": "local", "LOCAL_STORAGE_PATH": "/tmp/rhesis-files"},
            clear=True,
        ):
            storage_service = StorageService()

            file_path = storage_service.get_file_path(
                organization_id="org-123", source_id="source-456", filename="test.pdf"
            )

            expected_path = "/tmp/rhesis-files/org-123/source-456_test.pdf"
            assert file_path == expected_path

            # Verify directory creation
            mock_storage_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)


@pytest.mark.unit
@pytest.mark.service
class TestStorageServiceFileOperations(StorageServiceTestMixin, BaseStorageServiceTests):
    """Test file operations with mocked file system."""

    @pytest.mark.asyncio
    async def test_save_file_success(self):
        """Test successful file save operation."""
        mock_fs = MagicMock()
        mock_file = MagicMock()
        mock_fs.open.return_value.__enter__.return_value = mock_file

        storage_service = StorageService()
        storage_service.fs = mock_fs

        content = b"test file content"
        file_path = "test/path/file.txt"

        result = await storage_service.save_file(content, file_path)

        assert result == file_path
        mock_fs.open.assert_called_once_with(file_path, "wb")
        mock_file.write.assert_called_once_with(content)

    @pytest.mark.asyncio
    async def test_get_file_success(self):
        """Test successful file retrieval operation."""
        storage_service = StorageService()
        file_path = "test/path/file.txt"
        test_content = b"test file content"

        # Mock the cloud storage check to fail, then mock local file operations
        with patch.object(
            storage_service.fs, "open", side_effect=Exception("Cloud storage not available")
        ):
            with patch("builtins.open", mock_open(read_data=test_content)):
                with patch("os.path.exists", return_value=True):
                    result = await storage_service.get_file(file_path)

        assert result == test_content

    @pytest.mark.asyncio
    async def test_delete_file_success(self):
        """Test successful file deletion."""
        mock_fs = MagicMock()
        storage_service = StorageService()
        storage_service.fs = mock_fs

        file_path = "test/path/file.txt"

        result = await storage_service.delete_file(file_path)

        assert result is True
        mock_fs.rm.assert_called_once_with(file_path)

    @pytest.mark.asyncio
    async def test_delete_file_failure(self):
        """Test file deletion failure handling."""
        mock_fs = MagicMock()
        mock_fs.rm.side_effect = Exception("Delete failed")
        storage_service = StorageService()
        storage_service.fs = mock_fs

        file_path = "test/path/file.txt"

        result = await storage_service.delete_file(file_path)

        assert result is False

    def test_file_exists_true(self):
        """Test file existence check when file exists."""
        storage_service = StorageService()
        file_path = "test/path/file.txt"

        # Mock local file existence check since we're using local storage
        with patch("os.path.exists", return_value=True):
            result = storage_service.file_exists(file_path)

        assert result is True

    def test_file_exists_false(self):
        """Test file existence check when file doesn't exist."""
        storage_service = StorageService()
        file_path = "test/path/file.txt"

        # Mock local file existence check since we're using local storage
        with patch("os.path.exists", return_value=False):
            result = storage_service.file_exists(file_path)

        assert result is False

    def test_file_exists_exception(self):
        """Test file existence check exception handling."""
        mock_fs = MagicMock()
        mock_fs.exists.side_effect = Exception("Check failed")
        storage_service = StorageService()
        storage_service.fs = mock_fs

        file_path = "test/path/file.txt"

        result = storage_service.file_exists(file_path)

        assert result is False

    def test_get_file_size_success(self):
        """Test successful file size retrieval."""
        storage_service = StorageService()
        file_path = "test/path/file.txt"

        # Mock local file operations since we're using local storage
        with patch("os.path.exists", return_value=True):
            with patch("os.path.getsize", return_value=1024):
                result = storage_service.get_file_size(file_path)

        assert result == 1024

    def test_get_file_size_failure(self):
        """Test file size retrieval failure handling."""
        mock_fs = MagicMock()
        mock_fs.size.side_effect = Exception("Size check failed")
        storage_service = StorageService()
        storage_service.fs = mock_fs

        file_path = "test/path/file.txt"

        result = storage_service.get_file_size(file_path)

        assert result is None


@pytest.mark.unit
@pytest.mark.service
class TestStorageServiceEdgeCases(StorageServiceTestMixin, BaseStorageServiceTests):
    """Test edge cases and error scenarios for StorageService."""

    def test_file_path_with_special_characters(self):
        """Test file path generation with special characters."""
        with patch.dict(
            os.environ,
            {"BACKEND_ENV": "local", "LOCAL_STORAGE_PATH": "/tmp/test"},
            clear=True,
        ):
            storage_service = StorageService()

            # Test with special characters in IDs and filename
            file_path = storage_service.get_file_path(
                organization_id="org-with-special-chars!@#",
                source_id="source-with-spaces and symbols",
                filename="file with spaces & symbols.txt",
            )

            assert file_path is not None
            assert "org-with-special-chars!@#" in file_path
            assert "source-with-spaces and symbols" in file_path
            assert "file with spaces & symbols.txt" in file_path

    def test_file_path_with_unicode_characters(self):
        """Test file path generation with unicode characters."""
        with patch.dict(
            os.environ,
            {"BACKEND_ENV": "local", "LOCAL_STORAGE_PATH": "/tmp/test"},
            clear=True,
        ):
            storage_service = StorageService()

            # Test with unicode characters
            file_path = storage_service.get_file_path(
                organization_id="org-测试",
                source_id="source-тест",
                filename="файл-测试.txt",
            )

            assert file_path is not None
            assert "org-测试" in file_path
            assert "source-тест" in file_path
            assert "файл-测试.txt" in file_path

    def test_file_path_with_very_long_names(self):
        """Test file path generation with very long names."""
        with patch.dict(
            os.environ,
            {"BACKEND_ENV": "local", "LOCAL_STORAGE_PATH": "/tmp/test"},
            clear=True,
        ):
            storage_service = StorageService()

            # Create very long names (but not exceeding filesystem limits)
            long_org_id = "org-" + "x" * 100  # Reduced from 300
            long_source_id = "source-" + "y" * 100  # Reduced from 300
            long_filename = "file-" + "z" * 100 + ".txt"  # Reduced from 300

            file_path = storage_service.get_file_path(
                organization_id=long_org_id,
                source_id=long_source_id,
                filename=long_filename,
            )

            assert file_path is not None
            assert len(file_path) > 300  # Should be reasonably long

    @pytest.mark.asyncio
    async def test_concurrent_access_same_file(self, local_storage_service):
        """Test concurrent access to the same file."""
        storage_service = local_storage_service

        org_id = "org-concurrent-same"
        source_id = "source-same"
        filename = "same_file.txt"
        content = b"concurrent access test content"

        file_path = storage_service.get_file_path(org_id, source_id, filename)

        # Save file
        await storage_service.save_file(content, file_path)

        # Multiple concurrent reads
        import asyncio

        async def read_file():
            return await storage_service.get_file(file_path)

        tasks = [read_file() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All reads should return the same content
        for result in results:
            assert result == content

        # Clean up
        await storage_service.delete_file(file_path)

    def test_file_operations_with_nonexistent_path(self):
        """Test file operations with non-existent file paths."""
        mock_fs = MagicMock()
        mock_fs.exists.return_value = False
        mock_fs.size.side_effect = FileNotFoundError("File not found")
        mock_fs.open.side_effect = FileNotFoundError("File not found")

        storage_service = StorageService()
        storage_service.fs = mock_fs

        file_path = "nonexistent/path/file.txt"

        # Test file exists
        assert storage_service.file_exists(file_path) is False

        # Test file size
        assert storage_service.get_file_size(file_path) is None

    def test_file_operations_with_permission_errors(self):
        """Test file operations with permission errors."""
        mock_fs = MagicMock()
        mock_fs.exists.side_effect = PermissionError("Permission denied")
        mock_fs.size.side_effect = PermissionError("Permission denied")
        mock_fs.open.side_effect = PermissionError("Permission denied")

        storage_service = StorageService()
        storage_service.fs = mock_fs

        file_path = "restricted/path/file.txt"

        # Test file exists with permission error
        assert storage_service.file_exists(file_path) is False

        # Test file size with permission error
        assert storage_service.get_file_size(file_path) is None
