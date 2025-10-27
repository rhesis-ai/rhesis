"""
Tests for DocumentHandler class.

This module tests the persistent document storage with cloud/local backend,
following the established patterns from other test modules with factory-based
data generation and base class inheritance.
"""

import hashlib
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile
from rhesis.backend.app.services.handlers.document import DocumentHandler

from .base import BaseDocumentHandlerTests, DocumentHandlerTestMixin

# Import test fixtures and base classes
from .fixtures.storage_fixtures import DocumentHandlerDataFactory, MockUploadFile


class DocumentHandlerTestMixin(DocumentHandlerTestMixin):
    """Enhanced document handler test mixin using factory system."""

    # Factory-based data methods
    def get_sample_data(self) -> Dict[str, Any]:
        """Return sample document handler data using factory."""
        return DocumentHandlerDataFactory.sample_data()

    def get_minimal_data(self) -> Dict[str, Any]:
        """Return minimal document handler data using factory."""
        return DocumentHandlerDataFactory.minimal_data()

    def get_edge_case_data(self, case_type: str) -> Dict[str, Any]:
        """Return edge case document handler data using factory."""
        return DocumentHandlerDataFactory.edge_case_data(case_type)


@pytest.mark.unit
@pytest.mark.service
class TestDocumentHandlerInitialization(
    DocumentHandlerTestMixin, BaseDocumentHandlerTests
):
    """Test DocumentHandler initialization and configuration."""

    def test_init_with_default_storage_service(self):
        """Test initialization with default StorageService."""
        with patch(
            "rhesis.backend.app.services.handlers.document.StorageService"
        ) as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage_class.return_value = mock_storage

            handler = DocumentHandler()

            assert handler.storage_service == mock_storage
            assert handler.max_size == 5 * 1024 * 1024  # 5MB default
            mock_storage_class.assert_called_once()

    def test_init_with_custom_storage_service(self):
        """Test initialization with custom StorageService."""
        mock_storage = MagicMock()
        custom_max_size = 10 * 1024 * 1024  # 10MB

        handler = DocumentHandler(
            storage_service=mock_storage, max_size=custom_max_size
        )

        assert handler.storage_service == mock_storage
        assert handler.max_size == custom_max_size

    def test_init_with_custom_max_size_only(self):
        """Test initialization with custom max size but default storage service."""
        with patch(
            "rhesis.backend.app.services.handlers.document.StorageService"
        ) as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage_class.return_value = mock_storage

            custom_max_size = 2 * 1024 * 1024  # 2MB
            handler = DocumentHandler(max_size=custom_max_size)

            assert handler.storage_service == mock_storage
            assert handler.max_size == custom_max_size
            mock_storage_class.assert_called_once()


@pytest.mark.unit
@pytest.mark.service
class TestDocumentHandlerValidation(DocumentHandlerTestMixin, BaseDocumentHandlerTests):
    """Test document validation methods."""

    @pytest.mark.asyncio
    async def test_save_document_no_filename(self):
        """Test save_document with UploadFile that has no filename."""
        handler = DocumentHandler()

        # Create mock UploadFile without filename
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = None

        with pytest.raises(ValueError, match="Source has no name"):
            await handler.save_document(
                document=mock_file, organization_id="org-123", source_id="source-456"
            )

    @pytest.mark.asyncio
    async def test_save_document_empty_content(self):
        """Test save_document with empty file content."""
        handler = DocumentHandler()

        # Create mock UploadFile with empty content
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.read = AsyncMock(return_value=b"")

        with pytest.raises(ValueError, match="Source is empty"):
            await handler.save_document(
                document=mock_file, organization_id="org-123", source_id="source-456"
            )

    @pytest.mark.asyncio
    async def test_save_document_exceeds_size_limit(self):
        """Test save_document with file exceeding size limit."""
        handler = DocumentHandler(max_size=100)  # 100 bytes limit

        # Create mock UploadFile with content exceeding limit
        large_content = b"x" * 150  # 150 bytes
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "large.txt"
        mock_file.read = AsyncMock(return_value=large_content)

        with pytest.raises(
            ValueError, match="Source size exceeds limit of 100 bytes"
        ):
            await handler.save_document(
                document=mock_file, organization_id="org-123", source_id="source-456"
            )

    @pytest.mark.asyncio
    async def test_save_document_valid_size(self):
        """Test save_document with valid file size."""
        handler = DocumentHandler(max_size=1000)  # 1KB limit

        # Create mock UploadFile with valid content
        content = b"valid content"
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.read = AsyncMock(return_value=content)

        # Mock storage service
        mock_storage = MagicMock()
        mock_storage.get_file_path.return_value = "test/path/file.txt"
        mock_storage.save_file = AsyncMock(return_value="test/path/file.txt")
        handler.storage_service = mock_storage

        # Mock metadata extraction
        with patch.object(handler, "_extract_metadata") as mock_extract:
            mock_extract.return_value = {
                "file_size": len(content),
                "file_path": "test/path/file.txt",
            }

            metadata = await handler.save_document(
                document=mock_file, organization_id="org-123", source_id="source-456"
            )

            assert metadata["file_path"] == "test/path/file.txt"
            assert metadata["file_size"] == len(content)

            # Verify storage service calls
            mock_storage.get_file_path.assert_called_once_with(
                "org-123", "source-456", "test.txt"
            )
            mock_storage.save_file.assert_called_once_with(
                content, "test/path/file.txt"
            )
            mock_extract.assert_called_once_with(
                content, "test.txt", "test/path/file.txt", None, "org-123", None
            )


@pytest.mark.unit
@pytest.mark.service
class TestDocumentHandlerFileOperations(
    DocumentHandlerTestMixin, BaseDocumentHandlerTests
):
    """Test document file operations."""

    @pytest.mark.asyncio
    async def test_get_document_content_success(self):
        """Test successful document content retrieval."""
        handler = DocumentHandler()

        mock_storage = MagicMock()
        mock_storage.get_file = AsyncMock(return_value=b"file content")
        handler.storage_service = mock_storage

        file_path = "test/path/file.txt"
        result = await handler.get_document_content(file_path)

        assert result == b"file content"
        mock_storage.get_file.assert_called_once_with(file_path)

    @pytest.mark.asyncio
    async def test_delete_document_success(self):
        """Test successful document deletion."""
        handler = DocumentHandler()

        mock_storage = MagicMock()
        mock_storage.delete_file = AsyncMock(return_value=True)
        handler.storage_service = mock_storage

        file_path = "test/path/file.txt"
        result = await handler.delete_document(file_path)

        assert result is True
        mock_storage.delete_file.assert_called_once_with(file_path)

    @pytest.mark.asyncio
    async def test_delete_document_failure(self):
        """Test document deletion failure."""
        handler = DocumentHandler()

        mock_storage = MagicMock()
        mock_storage.delete_file = AsyncMock(return_value=False)
        handler.storage_service = mock_storage

        file_path = "test/path/file.txt"
        result = await handler.delete_document(file_path)

        assert result is False
        mock_storage.delete_file.assert_called_once_with(file_path)


@pytest.mark.unit
@pytest.mark.service
class TestDocumentHandlerMetadataExtraction(
    DocumentHandlerTestMixin, BaseDocumentHandlerTests
):
    """Test metadata extraction methods."""

    def test_extract_metadata_basic(self):
        """Test basic metadata extraction."""
        handler = DocumentHandler()

        content = b"test file content"
        filename = "test.txt"

        with (
            patch.object(handler, "_calculate_file_hash") as mock_hash,
            patch.object(handler, "_get_mime_type") as mock_mime,
        ):
            mock_hash.return_value = "abc123hash"
            mock_mime.return_value = "text/plain"

            metadata = handler._extract_metadata(
                content, filename, "test/path/file.txt"
            )

            expected_metadata = {
                "file_size": len(content),
                "file_hash": "abc123hash",
                "original_filename": filename,
                "file_type": "text/plain",
                "file_path": "test/path/file.txt",
            }

            # Check all fields
            assert metadata["file_size"] == expected_metadata["file_size"]
            assert metadata["file_hash"] == expected_metadata["file_hash"]
            assert (
                metadata["original_filename"] == expected_metadata["original_filename"]
            )
            assert metadata["file_type"] == expected_metadata["file_type"]
            assert metadata["file_path"] == expected_metadata["file_path"]

            mock_hash.assert_called_once_with(content)
            mock_mime.assert_called_once_with(filename)

    def test_calculate_file_hash(self):
        """Test file hash calculation."""
        handler = DocumentHandler()

        content = b"test content for hashing"
        expected_hash = hashlib.sha256(content).hexdigest()

        result = handler._calculate_file_hash(content)

        assert result == expected_hash
        assert len(result) == 64  # SHA-256 hex digest length

    def test_get_mime_type_known_extensions(self):
        """Test MIME type detection for known file extensions."""
        handler = DocumentHandler()

        test_cases = [
            ("document.pdf", "application/pdf"),
            (
                "report.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            ("readme.txt", "text/plain"),
            ("guide.md", "text/markdown"),
            ("page.html", "text/html"),
            ("data.csv", "text/csv"),
            ("config.json", "application/json"),
            ("schema.xml", "application/xml"),
            ("archive.zip", "application/zip"),
            ("image.png", "image/png"),
            ("photo.jpg", "image/jpeg"),
            ("photo.jpeg", "image/jpeg"),
            ("animation.gif", "image/gif"),
            ("icon.svg", "image/svg+xml"),
        ]

        for filename, expected_mime in test_cases:
            result = handler._get_mime_type(filename)
            assert result == expected_mime, f"Failed for {filename}"

    def test_get_mime_type_unknown_extension(self):
        """Test MIME type detection for unknown file extensions."""
        handler = DocumentHandler()

        result = handler._get_mime_type("unknown.xyz")
        assert result == "application/octet-stream"

    def test_get_mime_type_no_extension(self):
        """Test MIME type detection for files without extensions."""
        handler = DocumentHandler()

        result = handler._get_mime_type("README")
        assert result == "application/octet-stream"

    def test_get_mime_type_case_insensitive(self):
        """Test MIME type detection is case insensitive."""
        handler = DocumentHandler()

        assert handler._get_mime_type("test.PDF") == "application/pdf"
        assert handler._get_mime_type("TEST.PDF") == "application/pdf"
        assert handler._get_mime_type("test.Pdf") == "application/pdf"


@pytest.mark.integration
@pytest.mark.service
class TestDocumentHandlerIntegration(
    DocumentHandlerTestMixin, BaseDocumentHandlerTests
):
    """Integration tests for DocumentHandler with real file operations."""

    @pytest.mark.asyncio
    async def test_complete_document_workflow(self):
        """Test complete document save/retrieve/delete workflow."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a real StorageService with local storage
            with patch.dict(
                os.environ,
                {"BACKEND_ENV": "local", "LOCAL_STORAGE_PATH": temp_dir},
                clear=True,
            ):
                from rhesis.backend.app.services.storage_service import StorageService

                storage_service = StorageService()
                handler = DocumentHandler(storage_service=storage_service)

                # Create a real UploadFile-like object
                content = b"integration test content for document handler"
                filename = "integration_test.txt"

                # Simulate UploadFile behavior
                mock_file = MockUploadFile(content, filename)

                # Test save document
                metadata = await handler.save_document(
                    document=mock_file,
                    organization_id="org-123",
                    source_id="source-456",
                )
                file_path = metadata["file_path"]

                # Verify save results
                assert file_path is not None
                assert metadata["file_size"] == len(content)
                assert metadata["original_filename"] == filename
                assert metadata["file_type"] == "text/plain"
                assert len(metadata["file_hash"]) == 64

                # Test retrieve document
                retrieved_content = await handler.get_document_content(file_path)
                assert retrieved_content == content

                # Test delete document
                delete_result = await handler.delete_document(file_path)
                assert delete_result is True

                # Verify file no longer exists
                assert not storage_service.file_exists(file_path)

    @pytest.mark.asyncio
    async def test_document_with_various_file_types(self):
        """Test document handling with various file types."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {"BACKEND_ENV": "local", "LOCAL_STORAGE_PATH": temp_dir},
                clear=True,
            ):
                from rhesis.backend.app.services.storage_service import StorageService

                storage_service = StorageService()
                handler = DocumentHandler(storage_service=storage_service)

                test_files = [
                    ("document.pdf", b"PDF content", "application/pdf"),
                    ("data.json", b'{"key": "value"}', "application/json"),
                    ("image.png", b"PNG content", "image/png"),
                    (
                        "script.py",
                        b"print('hello')",
                        "application/octet-stream",
                    ),  # Python not in MIME types
                ]

                for filename, content, expected_mime in test_files:

                    class MockUploadFile:
                        def __init__(self, content: bytes, filename: str):
                            self.content = content
                            self.filename = filename

                        async def read(self):
                            return self.content

                    mock_file = MockUploadFile(content, filename)

                    # Test save
                    metadata = await handler.save_document(
                        document=mock_file,
                        organization_id="org-123",
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


@pytest.mark.unit
@pytest.mark.service
class TestDocumentHandlerEdgeCases(DocumentHandlerTestMixin, BaseDocumentHandlerTests):
    """Test edge cases and error scenarios for DocumentHandler."""

    @pytest.mark.asyncio
    async def test_document_with_very_long_filename(self):
        """Test document handling with very long filename."""
        handler = DocumentHandler()

        # Create filename longer than typical filesystem limits
        long_filename = "x" * 500 + ".txt"
        content = b"test content"

        mock_file = MockUploadFile(content, long_filename)

        # Mock storage service
        mock_storage = MagicMock()
        mock_storage.get_file_path.return_value = "test/path/file.txt"
        mock_storage.save_file = AsyncMock()
        handler.storage_service = mock_storage

        # Should handle long filename gracefully
        metadata = await handler.save_document(
            document=mock_file, organization_id="org-123", source_id="source-456"
        )
        file_path = metadata["file_path"]

        assert metadata["original_filename"] == long_filename
        assert metadata["file_size"] == len(content)

    @pytest.mark.asyncio
    async def test_document_with_empty_filename(self):
        """Test document handling with empty filename."""
        handler = DocumentHandler()

        # Create file with empty filename
        content = b"test content"
        mock_file = MockUploadFile(content, "")

        with pytest.raises(ValueError, match="Source has no name"):
            await handler.save_document(
                document=mock_file, organization_id="org-123", source_id="source-456"
            )

    @pytest.mark.asyncio
    async def test_document_with_whitespace_only_filename(self):
        """Test document handling with whitespace-only filename."""
        handler = DocumentHandler()

        # Create file with whitespace-only filename
        content = b"test content"
        mock_file = MockUploadFile(content, "   ")

        with pytest.raises(ValueError, match="Source has no name"):
            await handler.save_document(
                document=mock_file, organization_id="org-123", source_id="source-456"
            )

    def test_metadata_extraction_with_binary_content(self):
        """Test metadata extraction with binary content."""
        handler = DocumentHandler()

        # Create binary content (not text)
        binary_content = bytes(range(256))  # All possible byte values
        filename = "binary_file.bin"

        metadata = handler._extract_metadata(
            binary_content, filename, "test/path/binary_file.bin"
        )

        assert metadata["file_size"] == 256
        assert metadata["file_type"] == "application/octet-stream"
        assert len(metadata["file_hash"]) == 64
        assert metadata["original_filename"] == filename

    def test_metadata_extraction_with_unicode_content(self):
        """Test metadata extraction with unicode content."""
        handler = DocumentHandler()

        # Create unicode content
        unicode_content = "测试内容 with unicode: émojis 🚀".encode("utf-8")
        filename = "unicode_file.txt"

        metadata = handler._extract_metadata(
            unicode_content, filename, "test/path/unicode_file.txt"
        )

        assert metadata["file_size"] == len(unicode_content)
        assert metadata["file_type"] == "text/plain"
        assert len(metadata["file_hash"]) == 64
        assert metadata["original_filename"] == filename

    @pytest.mark.asyncio
    async def test_document_size_at_exact_limit(self):
        """Test document handling at exact size limit."""
        handler = DocumentHandler(max_size=100)  # 100 bytes limit

        # Create content exactly at the limit
        content = b"x" * 100  # Exactly 100 bytes
        mock_file = MockUploadFile(content, "exact_size.txt")

        # Mock storage service
        mock_storage = MagicMock()
        mock_storage.get_file_path.return_value = "test/path/file.txt"
        mock_storage.save_file = AsyncMock()
        handler.storage_service = mock_storage

        # Should accept file at exact limit
        metadata = await handler.save_document(
            document=mock_file, organization_id="org-123", source_id="source-456"
        )
        file_path = metadata["file_path"]

        assert metadata["file_size"] == 100

    @pytest.mark.asyncio
    async def test_document_size_one_byte_over_limit(self):
        """Test document handling one byte over size limit."""
        handler = DocumentHandler(max_size=100)  # 100 bytes limit

        # Create content one byte over the limit
        content = b"x" * 101  # 101 bytes
        mock_file = MockUploadFile(content, "over_size.txt")

        with pytest.raises(ValueError, match="Source size exceeds limit"):
            await handler.save_document(
                document=mock_file, organization_id="org-123", source_id="source-456"
            )

    def test_mime_type_detection_with_multiple_extensions(self):
        """Test MIME type detection with multiple extensions."""
        handler = DocumentHandler()

        # Test files with multiple extensions
        test_cases = [
            ("file.tar.gz", "application/octet-stream"),  # Not in our mapping
            ("backup.sql.gz", "application/octet-stream"),  # Not in our mapping
            ("archive.zip.bak", "application/octet-stream"),  # Not in our mapping
        ]

        for filename, expected_mime in test_cases:
            result = handler._get_mime_type(filename)
            assert result == expected_mime, f"Failed for {filename}"

    def test_mime_type_detection_with_hidden_files(self):
        """Test MIME type detection with hidden files."""
        handler = DocumentHandler()

        # Test hidden files (starting with dot)
        test_cases = [
            (".hidden.txt", "text/plain"),
            (".config.json", "application/json"),
            (".env", "application/octet-stream"),  # No extension
        ]

        for filename, expected_mime in test_cases:
            result = handler._get_mime_type(filename)
            assert result == expected_mime, f"Failed for {filename}"
