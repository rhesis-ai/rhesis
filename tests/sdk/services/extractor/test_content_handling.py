"""Tests for DocumentExtractor content handling functionality."""

from unittest.mock import patch

import pytest

from rhesis.sdk.services.extractor import DocumentExtractor
from rhesis.sdk.types import Document


class TestDocumentExtractorContentHandling:
    """Test cases for DocumentExtractor content handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = DocumentExtractor()

    def test_extract_with_content(self):
        """Test extraction when content is provided directly."""
        documents = [
            Document(name="test_doc", description="Test document", content="This is test content")
        ]

        result = self.extractor.extract(documents)
        assert result == {"test_doc": "This is test content"}

    def test_extract_mixed_content_and_path(self):
        """Test extraction with mixed content and path documents."""
        documents = [
            Document(
                name="content_doc", description="Document with content", content="Direct content"
            ),
            Document(name="file_doc", description="Document from file", path="/path/to/test.png"),
        ]

        with patch.object(self.extractor, "_extract_from_file") as mock_extract:
            mock_extract.return_value = "Extracted text from PNG"
            result = self.extractor.extract(documents)

        expected = {"content_doc": "Direct content", "file_doc": "Extracted text from PNG"}
        assert result == expected

    def test_extract_missing_name(self):
        """Test extraction with missing document name."""
        with pytest.raises(TypeError, match="missing 1 required positional argument: 'name'"):
            Document(description="Test document", content="Test content")

    def test_extract_empty_document(self):
        """Test extraction with empty document (no content or path)."""
        with pytest.raises(ValueError, match="Either 'path' or 'content' must be provided"):
            Document(name="empty_doc", description="Empty document")

    def test_extract_with_none_values(self):
        """Test extraction with None values in document fields."""
        with pytest.raises(ValueError, match="Either 'path' or 'content' must be provided"):
            Document(name="test_doc", description="Test document", content=None, path=None)

    def test_extract_with_missing_fields(self):
        """Test extraction with missing optional fields."""
        with pytest.raises(ValueError, match="Either 'path' or 'content' must be provided"):
            Document(
                name="test_doc",
                description="Test document",
                # Missing content and path fields
            )

    def test_extract_multiple_documents_with_content(self):
        """Test extraction with multiple documents containing content."""
        documents = [
            Document(
                name="doc1", description="First document", content="Content from first document"
            ),
            Document(
                name="doc2", description="Second document", content="Content from second document"
            ),
            Document(
                name="doc3", description="Third document", content="Content from third document"
            ),
        ]

        result = self.extractor.extract(documents)
        expected = {
            "doc1": "Content from first document",
            "doc2": "Content from second document",
            "doc3": "Content from third document",
        }
        assert result == expected

    def test_extract_with_empty_content(self):
        """Test extraction with empty content string."""
        with pytest.raises(ValueError, match="Either 'path' or 'content' must be provided"):
            Document(
                name="empty_content_doc", description="Document with empty content", content=""
            )

    def test_extract_with_whitespace_content(self):
        """Test extraction with whitespace-only content."""
        documents = [
            Document(
                name="whitespace_doc",
                description="Document with whitespace content",
                content="   \n\t   ",
            )
        ]

        result = self.extractor.extract(documents)
        assert result == {"whitespace_doc": "   \n\t   "}

    def test_extract_with_special_characters(self):
        """Test extraction with special characters in content."""
        special_content = "Content with special chars: äöüß, éèê, ñ, ç, 中文, 🚀, 💻"
        documents = [
            Document(
                name="special_chars_doc",
                description="Document with special characters",
                content=special_content,
            )
        ]

        result = self.extractor.extract(documents)
        assert result == {"special_chars_doc": special_content}

    def test_extract_with_large_content(self):
        """Test extraction with large content."""
        large_content = "Large content " * 1000  # Create a large string
        documents = [
            Document(
                name="large_doc", description="Document with large content", content=large_content
            )
        ]

        result = self.extractor.extract(documents)
        assert result == {"large_doc": large_content}
        assert len(result["large_doc"]) == len(large_content)

    def test_extract_with_mixed_content_types(self):
        """Test extraction with mixed content types (content vs path)."""
        documents = [
            Document(
                name="content_only", description="Content only document", content="Direct content"
            ),
            Document(name="path_only", description="Path only document", path="/path/to/file.pdf"),
            Document(
                name="both_provided",
                description="Document with both content and path",
                content="Direct content takes precedence",
                path="/path/to/file.pdf",
            ),
        ]

        with patch.object(self.extractor, "_extract_from_file") as mock_extract:
            mock_extract.return_value = "Extracted from file"
            result = self.extractor.extract(documents)

        expected = {
            "content_only": "Direct content",
            "path_only": "Extracted from file",
            "both_provided": "Direct content takes precedence",  # Content takes precedence
        }
        assert result == expected
