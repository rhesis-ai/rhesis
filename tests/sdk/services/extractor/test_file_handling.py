"""Tests for DocumentExtractor file handling functionality."""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.services.extractor import DocumentExtractor
from rhesis.sdk.types import Document


class TestDocumentExtractorFileHandling:
    """Test cases for DocumentExtractor file handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = DocumentExtractor()

    def test_init(self):
        """Test DocumentExtractor initialization."""
        expected_extensions = {
            ".docx",
            ".pptx",
            ".xlsx",
            ".pdf",
            ".txt",
            ".md",
            ".csv",
            ".json",
            ".xml",
            ".html",
            ".htm",
            ".zip",
            ".epub",
        }
        assert self.extractor.supported_extensions == expected_extensions

    def test_extract_with_file_path(self):
        """Test extraction from file path."""
        documents = [
            Document(name="test_doc", description="Test document", path="/path/to/test.pdf")
        ]

        with patch.object(self.extractor, "_extract_from_file") as mock_extract:
            mock_extract.return_value = "Extracted text from PDF"
            result = self.extractor.extract(documents)

        assert result == {"test_doc": "Extracted text from PDF"}
        mock_extract.assert_called_once_with("/path/to/test.pdf")

    def test_extract_file_not_found(self):
        """Test extraction when file is not found."""
        documents = [
            Document(name="missing_doc", description="Missing file", path="/nonexistent/file.pdf")
        ]

        with pytest.raises(FileNotFoundError, match="File not found: /nonexistent/file.pdf"):
            self.extractor.extract(documents)

    def test_extract_unsupported_file_type(self):
        """Test extraction with unsupported file type."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as temp_file:
            temp_file.write(b"fake executable content")
            temp_file_path = temp_file.name

        try:
            documents = [
                Document(
                    name="unsupported_doc", description="Unsupported file type", path=temp_file_path
                )
            ]

            with pytest.raises(ValueError, match="Unsupported file type: .exe"):
                self.extractor.extract(documents)
        finally:
            os.unlink(temp_file_path)

    def test_extract_from_file_success(self):
        """Test successful file extraction."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(b"PDF content")
            temp_file_path = temp_file.name

        try:
            # Patch the converter instance, not the class
            with patch.object(self.extractor, "converter") as mock_converter:
                mock_result = Mock()
                mock_result.text_content = "Extracted PDF text"
                mock_result.markdown = "# Extracted PDF text"
                mock_converter.convert.return_value = mock_result

                result = self.extractor._extract_from_file(temp_file_path)

            assert result == "Extracted PDF text"
        finally:
            os.unlink(temp_file_path)

    def test_extract_from_file_not_found(self):
        """Test file extraction when file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="File not found: /nonexistent/file.pdf"):
            self.extractor._extract_from_file("/nonexistent/file.pdf")

    def test_extract_from_file_unsupported_type(self):
        """Test file extraction with unsupported file type."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as temp_file:
            temp_file_path = temp_file.name

        try:
            with pytest.raises(ValueError, match="Unsupported file type: .exe"):
                self.extractor._extract_from_file(temp_file_path)
        finally:
            os.unlink(temp_file_path)

    def test_extract_from_file_markitdown_error(self):
        """Test file extraction when Markitdown raises an error."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file_path = temp_file.name

        try:
            # Patch the converter instance, not the class
            with patch.object(self.extractor, "converter") as mock_converter:
                mock_converter.convert.side_effect = Exception("Markitdown error")

                with pytest.raises(ValueError, match="Failed to extract text from"):
                    self.extractor._extract_from_file(temp_file_path)
        finally:
            os.unlink(temp_file_path)

    def test_extract_from_file_empty_result(self):
        """Test file extraction when Markitdown returns empty result."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file_path = temp_file.name

        try:
            # Patch the converter instance, not the class
            with patch.object(self.extractor, "converter") as mock_converter:
                mock_result = Mock()
                mock_result.text_content = ""
                mock_result.markdown = ""
                # Set the string representation to return empty string
                mock_result.__str__ = Mock(return_value="")
                mock_converter.convert.return_value = mock_result

                result = self.extractor._extract_from_file(temp_file_path)

            assert result == ""
        finally:
            os.unlink(temp_file_path)

    def test_extract_txt_file(self):
        """Test extraction from a .txt file."""
        test_content = (
            "This is a test text file.\nWith multiple lines.\nAnd some content to extract."
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name

        try:
            documents = [
                Document(name="test_txt", description="Test text document", path=temp_file_path)
            ]

            result = self.extractor.extract(documents)
            assert result == {"test_txt": test_content}
        finally:
            os.unlink(temp_file_path)

    def test_extract_from_txt_file_direct(self):
        """Test direct extraction from .txt file using _extract_from_file method."""
        test_content = "Direct text file extraction test.\nMultiple lines of content."

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name

        try:
            result = self.extractor._extract_from_file(temp_file_path)
            assert result == test_content
        finally:
            os.unlink(temp_file_path)

    def test_get_supported_extensions(self):
        """Test getting supported extensions."""
        extensions = self.extractor.get_supported_extensions()
        expected = {
            ".docx",
            ".pptx",
            ".xlsx",
            ".pdf",
            ".txt",
            ".md",
            ".csv",
            ".json",
            ".xml",
            ".html",
            ".htm",
            ".zip",
            ".epub",
        }
        assert extensions == expected
        # Ensure it returns a copy, not the original
        assert extensions is not self.extractor.supported_extensions

    def test_supported_file_types(self):
        """Test that all supported file types are properly handled."""
        supported_types = [
            ".docx",
            ".pptx",
            ".xlsx",
            ".pdf",
            ".txt",
            ".md",
            ".csv",
            ".json",
            ".xml",
            ".html",
            ".htm",
            ".zip",
            ".epub",
        ]

        for file_type in supported_types:
            with tempfile.NamedTemporaryFile(suffix=file_type, delete=False) as temp_file:
                temp_file_path = temp_file.name

                # For .txt files, write some content since they're read directly
                if file_type == ".txt":
                    temp_file.write(b"Test content for text file")
                else:
                    # For other files, write some dummy content
                    temp_file.write(b"dummy content")

            try:
                if file_type == ".txt":
                    # .txt files are handled directly, no Markitdown needed
                    result = self.extractor._extract_from_file(temp_file_path)
                    assert result == "Test content for text file"
                else:
                    # Other files use Markitdown - patch the converter instance
                    with patch.object(self.extractor, "converter") as mock_converter:
                        mock_result = Mock()
                        mock_result.text_content = f"Extracted text from {file_type}"
                        mock_result.markdown = f"# Extracted text from {file_type}"
                        mock_converter.convert.return_value = mock_result

                        result = self.extractor._extract_from_file(temp_file_path)
                        assert result == f"Extracted text from {file_type}"
            finally:
                os.unlink(temp_file_path)

    def test_extract_with_manual_pdf_path(self):
        """Manual test method for testing with your own PDF file."""
        # This test is skipped by default but can be enabled for manual testing
        pytest.skip("Manual test - enable by removing this line and providing a PDF path")

        # Set your PDF path here directly
        pdf_path = "/path/to/your/pdf"  # Replace with your actual PDF path

        if not pdf_path or not os.path.exists(pdf_path):
            pytest.skip(f"PDF file not found: {pdf_path}")

        documents = [
            {
                "name": "manual_test_pdf",
                "description": "Manual test PDF",
                "path": pdf_path,
                "content": "",
            }
        ]

        result = self.extractor.extract(documents)
        assert "manual_test_pdf" in result
        extracted_text = result["manual_test_pdf"]
        print(f"Extracted text length: {len(extracted_text)}")
        print(f"First 200 characters: {extracted_text[:200]}...")
        assert len(extracted_text) > 0
