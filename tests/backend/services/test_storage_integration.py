"""
Integration tests for storage service and document handler.

This module contains integration tests that test the complete workflow
of file storage operations with real file systems and actual service interactions,
following the established patterns from other test modules.
"""

import asyncio
import os
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.services.storage_service import StorageService

from .base import BaseStorageIntegrationTests, StorageIntegrationTestMixin

# Import test fixtures and base classes
from .fixtures.storage_fixtures import (
    MockUploadFile,
    StorageServiceDataFactory,
    document_handler_with_local_storage,  # noqa: F401
    environment_configurations,  # noqa: F401
    local_storage_service,  # noqa: F401
    various_file_types,  # noqa: F401
)


class StorageIntegrationTestMixin(StorageIntegrationTestMixin):
    """Enhanced storage integration test mixin using factory system."""

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

    def get_test_organization_id(self) -> str:
        """Return test organization ID."""
        return "org-integration-test"

    def get_test_source_id(self) -> str:
        """Return test source ID."""
        return "source-integration-test"

    def get_test_filename(self) -> str:
        """Return test filename."""
        return "integration_test.txt"

    def get_test_content(self) -> bytes:
        """Return test file content."""
        return b"Integration test content for complete lifecycle"


@pytest.mark.integration
@pytest.mark.service
class TestStorageServiceIntegration(StorageIntegrationTestMixin, BaseStorageIntegrationTests):
    """Integration tests for StorageService with real file operations."""

    @pytest.mark.asyncio
    async def test_complete_file_lifecycle_local_storage(self, local_storage_service):
        """Test complete file lifecycle with local storage."""
        storage_service = local_storage_service

        # Test data
        org_id = "org-integration-test"
        source_id = "source-integration-test"
        filename = "integration_test.txt"
        content = b"Integration test content for complete lifecycle"

        # Test file path generation
        file_path = storage_service.get_file_path(org_id, source_id, filename)
        assert file_path is not None
        assert org_id in file_path
        assert source_id in file_path
        assert filename in file_path

        # Test file save
        result_path = await storage_service.save_file(content, file_path)
        assert result_path == file_path

        # Test file exists
        assert storage_service.file_exists(file_path) is True

        # Test file size
        file_size = storage_service.get_file_size(file_path)
        assert file_size == len(content)

        # Test file retrieval
        retrieved_content = await storage_service.get_file(file_path)
        assert retrieved_content == content

        # Test file deletion
        delete_result = await storage_service.delete_file(file_path)
        assert delete_result is True

        # Test file no longer exists
        assert storage_service.file_exists(file_path) is False

    @pytest.mark.asyncio
    async def test_multiple_files_same_organization(self, local_storage_service):
        """Test handling multiple files for the same organization."""
        storage_service = local_storage_service

        org_id = "org-multi-file-test"
        files_data = [
            ("source1", "file1.txt", b"Content 1"),
            ("source2", "file2.pdf", b"Content 2"),
            ("source3", "file3.json", b'{"key": "value"}'),
        ]

        file_paths = []

        # Save multiple files
        for source_id, filename, content in files_data:
            file_path = storage_service.get_file_path(org_id, source_id, filename)
            await storage_service.save_file(content, file_path)
            file_paths.append((file_path, content))

        # Verify all files exist
        for file_path, _ in file_paths:
            assert storage_service.file_exists(file_path) is True

        # Retrieve and verify all files
        for file_path, expected_content in file_paths:
            retrieved_content = await storage_service.get_file(file_path)
            assert retrieved_content == expected_content

        # Clean up all files
        for file_path, _ in file_paths:
            delete_result = await storage_service.delete_file(file_path)
            assert delete_result is True
            assert storage_service.file_exists(file_path) is False

    @pytest.mark.asyncio
    async def test_file_path_isolation_between_organizations(self, local_storage_service):
        """Test that file paths are properly isolated between organizations."""
        storage_service = local_storage_service

        # Same source_id and filename for different organizations
        source_id = "shared-source"
        filename = "shared_file.txt"
        content1 = b"Organization 1 content"
        content2 = b"Organization 2 content"

        org1_path = storage_service.get_file_path("org1", source_id, filename)
        org2_path = storage_service.get_file_path("org2", source_id, filename)

        # Paths should be different
        assert org1_path != org2_path

        # Save files to both paths
        await storage_service.save_file(content1, org1_path)
        await storage_service.save_file(content2, org2_path)

        # Verify both files exist and have correct content
        assert storage_service.file_exists(org1_path) is True
        assert storage_service.file_exists(org2_path) is True

        retrieved1 = await storage_service.get_file(org1_path)
        retrieved2 = await storage_service.get_file(org2_path)

        assert retrieved1 == content1
        assert retrieved2 == content2

        # Clean up
        await storage_service.delete_file(org1_path)
        await storage_service.delete_file(org2_path)

    @pytest.mark.asyncio
    async def test_large_file_handling(self, local_storage_service):
        """Test handling of large files."""
        storage_service = local_storage_service

        # Create a large file (1MB)
        large_content = b"x" * (1024 * 1024)
        org_id = "org-large-file"
        source_id = "source-large"
        filename = "large_file.txt"

        file_path = storage_service.get_file_path(org_id, source_id, filename)

        # Save large file
        result_path = await storage_service.save_file(large_content, file_path)
        assert result_path == file_path

        # Verify file size
        file_size = storage_service.get_file_size(file_path)
        assert file_size == len(large_content)

        # Retrieve and verify content
        retrieved_content = await storage_service.get_file(file_path)
        assert retrieved_content == large_content

        # Clean up
        await storage_service.delete_file(file_path)

    @pytest.mark.asyncio
    async def test_concurrent_file_operations(self, local_storage_service):
        """Test concurrent file operations."""
        storage_service = local_storage_service

        async def save_and_retrieve_file(file_id: int):
            """Save and retrieve a file."""
            org_id = f"org-concurrent-{file_id}"
            source_id = f"source-{file_id}"
            filename = f"file_{file_id}.txt"
            content = f"Content for file {file_id}".encode()

            file_path = storage_service.get_file_path(org_id, source_id, filename)
            await storage_service.save_file(content, file_path)

            retrieved_content = await storage_service.get_file(file_path)
            assert retrieved_content == content

            await storage_service.delete_file(file_path)
            return file_id

        # Run multiple concurrent operations
        tasks = [save_and_retrieve_file(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert set(results) == {0, 1, 2, 3, 4}


@pytest.mark.integration
@pytest.mark.service
class TestDocumentHandlerIntegration(StorageIntegrationTestMixin, BaseStorageIntegrationTests):
    """Integration tests for DocumentHandler with real storage operations."""

    @pytest.mark.asyncio
    async def test_complete_document_workflow(self, document_handler_with_local_storage):
        """Test complete document save/retrieve/delete workflow."""
        handler = document_handler_with_local_storage

        # Create test document
        content = b"Integration test document content"
        filename = "integration_document.txt"

        mock_file = MockUploadFile(content, filename)

        # Test save document
        metadata = await handler.save_document(
            document=mock_file,
            organization_id="org-integration",
            source_id="source-integration",
        )
        file_path = metadata["file_path"]

        # Verify save results
        assert file_path is not None
        assert metadata["file_size"] == len(content)
        assert metadata["original_filename"] == filename
        assert metadata["file_type"] == "text/plain"
        assert len(metadata["file_hash"]) == 64  # SHA-256 hex length

        # Test retrieve document
        retrieved_content = await handler.get_document_content(file_path)
        assert retrieved_content == content

        # Test delete document
        delete_result = await handler.delete_document(file_path)
        assert delete_result is True

    @pytest.mark.asyncio
    async def test_document_with_various_file_types(
        self, document_handler_with_local_storage, various_file_types
    ):
        """Test document handling with various file types."""
        handler = document_handler_with_local_storage

        for filename, content, expected_mime in various_file_types:
            mock_file = MockUploadFile(content, filename)

            # Test save
            metadata = await handler.save_document(
                document=mock_file,
                organization_id="org-file-types",
                source_id=f"source-{filename}",
            )
            file_path = metadata["file_path"]

            # Verify metadata
            assert metadata["file_type"] == expected_mime
            assert metadata["original_filename"] == filename
            assert metadata["file_size"] == len(content)

            # Test retrieve
            retrieved_content = await handler.get_document_content(file_path)
            assert retrieved_content == content

            # Clean up
            await handler.delete_document(file_path)

    @pytest.mark.asyncio
    async def test_document_size_validation(self, document_handler_with_local_storage):
        """Test document size validation with real storage."""
        handler = document_handler_with_local_storage

        # Test with size limit
        handler.max_size = 1000  # 1KB limit

        # Test valid size
        small_content = b"x" * 500  # 500 bytes
        small_file = MockUploadFile(small_content, "small.txt")

        metadata = await handler.save_document(
            document=small_file,
            organization_id="org-size-test",
            source_id="source-small",
        )
        file_path = metadata["file_path"]
        assert metadata["file_size"] == 500

        # Clean up
        await handler.delete_document(file_path)

        # Test oversized file
        large_content = b"x" * 1500  # 1.5KB
        large_file = MockUploadFile(large_content, "large.txt")

        with pytest.raises(ValueError, match="Source size exceeds limit"):
            await handler.save_document(
                document=large_file,
                organization_id="org-size-test",
                source_id="source-large",
            )

    @pytest.mark.asyncio
    async def test_document_error_handling(self, document_handler_with_local_storage):
        """Test document error handling scenarios."""
        handler = document_handler_with_local_storage

        # Test empty file
        empty_file = MockUploadFile(b"", "empty.txt")

        with pytest.raises(ValueError, match="Source is empty"):
            await handler.save_document(
                document=empty_file,
                organization_id="org-error-test",
                source_id="source-empty",
            )

        # Test file without filename
        class MockUploadFileNoName:
            def __init__(self, content: bytes):
                self.content = content
                self.filename = None

            async def read(self):
                return self.content

        no_name_file = MockUploadFileNoName(b"content")

        with pytest.raises(ValueError, match="Source has no name"):
            await handler.save_document(
                document=no_name_file,
                organization_id="org-error-test",
                source_id="source-no-name",
            )

    @pytest.mark.asyncio
    async def test_concurrent_document_operations(self, document_handler_with_local_storage):
        """Test concurrent document operations."""
        handler = document_handler_with_local_storage

        async def process_document(doc_id: int):
            """Process a single document."""
            content = f"Document {doc_id} content".encode()
            filename = f"doc_{doc_id}.txt"

            mock_file = MockUploadFile(content, filename)

            # Save document
            metadata = await handler.save_document(
                document=mock_file,
                organization_id=f"org-concurrent-{doc_id}",
                source_id=f"source-{doc_id}",
            )
            file_path = metadata["file_path"]

            # Retrieve document
            retrieved_content = await handler.get_document_content(file_path)
            assert retrieved_content == content

            # Delete document
            delete_result = await handler.delete_document(file_path)
            assert delete_result is True

            return doc_id

        # Run multiple concurrent document operations
        tasks = [process_document(i) for i in range(3)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert set(results) == {0, 1, 2}


@pytest.mark.integration
@pytest.mark.service
class TestStorageServiceEnvironmentConfigurations(
    StorageIntegrationTestMixin, BaseStorageIntegrationTests
):
    """Test StorageService with different environment configurations."""

    @patch("rhesis.backend.app.services.storage_service.fsspec.filesystem")
    def test_environment_specific_bucket_names(self, mock_fsspec, environment_configurations):
        """Test that different environments generate correct bucket names."""
        mock_fs = MagicMock()
        mock_fsspec.return_value = mock_fs

        configs = environment_configurations

        # Test each environment configuration
        for env_name, env_vars in configs.items():
            if env_name == "local":
                continue  # Skip local as it doesn't use buckets

            with patch.dict(os.environ, env_vars, clear=True):
                storage_service = StorageService()

                if env_name == "development":
                    assert storage_service.storage_uri == "gs://sources-rhesis-dev"
                elif env_name == "staging":
                    assert storage_service.storage_uri == "gs://sources-rhesis-stg"
                elif env_name == "production":
                    assert storage_service.storage_uri == "gs://sources-rhesis-prd"
                elif env_name in ["partial_gcs", "no_gcs"]:
                    # These should fallback to local storage
                    assert storage_service.use_cloud_storage is False

    def test_local_environment_configuration(self, environment_configurations):
        """Test local environment configuration."""
        config = environment_configurations["local"]

        with patch.dict(os.environ, config, clear=True):
            storage_service = StorageService()

            assert storage_service.storage_uri is None
            assert storage_service.use_cloud_storage is False
            assert storage_service.storage_path == "/tmp/local-test"

    def test_gcs_fallback_to_local(self, environment_configurations):
        """Test GCS fallback to local storage when credentials are missing."""
        config = environment_configurations["partial_gcs"]

        with patch.dict(os.environ, config, clear=True):
            storage_service = StorageService()

            # Should have bucket name but not use GCS due to missing credentials
            assert storage_service.storage_uri == "gs://sources-rhesis-dev"
            assert storage_service.use_cloud_storage is False
