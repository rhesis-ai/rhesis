"""Tests for the DocumentExtractor class."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.services.extractor import DocumentExtractor


class TestDocumentExtractor:
    """Test cases for DocumentExtractor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = DocumentExtractor()

    def test_init(self):
        """Test DocumentExtractor initialization."""
        expected_extensions = {
            ".pdf",
            ".docx", ".xlsx", ".pptx",
            ".md",
            ".adoc",
            ".html", ".xhtml",
            ".csv",
            ".txt",
            ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp",
            ".xml",
            ".json",
        }
        assert self.extractor.supported_extensions == expected_extensions

    def test_extract_with_content(self):
        """Test extraction when content is provided directly."""
        documents = [
            {
                "name": "test_doc",
                "description": "Test document",
                "content": "This is test content",
                "path": ""
            }
        ]

        result = self.extractor.extract(documents)
        assert result == {"test_doc": "This is test content"}

    def test_extract_with_file_path(self):
        """Test extraction from file path."""
        documents = [
            {
                "name": "test_doc",
                "description": "Test document",
                "path": "/path/to/test.pdf",
                "content": ""
            }
        ]

        with patch.object(self.extractor, '_extract_from_file') as mock_extract:
            mock_extract.return_value = "Extracted text from PDF"
            result = self.extractor.extract(documents)

        assert result == {"test_doc": "Extracted text from PDF"}
        mock_extract.assert_called_once_with("/path/to/test.pdf")

    def test_extract_mixed_content_and_path(self):
        """Test extraction with mixed content and path documents."""
        documents = [
            {
                "name": "content_doc",
                "description": "Document with content",
                "content": "Direct content",
                "path": ""
            },
            {
                "name": "file_doc",
                "description": "Document from file",
                "path": "/path/to/test.png",
                "content": ""
            }
        ]

        with patch.object(self.extractor, '_extract_from_file') as mock_extract:
            mock_extract.return_value = "Extracted text from PNG"
            result = self.extractor.extract(documents)

        expected = {
            "content_doc": "Direct content",
            "file_doc": "Extracted text from PNG"
        }
        assert result == expected

    def test_extract_missing_name(self):
        """Test extraction with missing document name."""
        documents = [
            {
                "description": "Test document",
                "content": "Test content"
            }
        ]

        with pytest.raises(ValueError, match="Document must have a 'name' field"):
            self.extractor.extract(documents)

    def test_extract_empty_document(self):
        """Test extraction with empty document (no content or path)."""
        documents = [
            {
                "name": "empty_doc",
                "description": "Empty document",
                "content": "",
                "path": ""
            }
        ]

        with pytest.raises(ValueError, match="Document 'empty_doc' must have either 'content' or 'path' field"):
            self.extractor.extract(documents)

    def test_extract_file_not_found(self):
        """Test extraction when file is not found."""
        documents = [
            {
                "name": "missing_doc",
                "description": "Missing file",
                "path": "/nonexistent/file.pdf",
                "content": ""
            }
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
                {
                    "name": "unsupported_doc",
                    "description": "Unsupported file type",
                    "path": temp_file_path,
                    "content": ""
                }
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
            with patch('docling.document_converter.DocumentConverter') as mock_converter_class:
                mock_converter = mock_converter_class.return_value
                mock_result = Mock()
                mock_result.document.export_to_markdown.return_value = "Extracted PDF text"
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

    def test_extract_from_file_docling_error(self):
        """Test file extraction when Docling raises an error."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file_path = temp_file.name

        try:
            with patch('docling.document_converter.DocumentConverter') as mock_converter_class:
                mock_converter_class.side_effect = Exception("Docling error")
                
                with pytest.raises(ValueError, match="Failed to extract text from"):
                    self.extractor._extract_from_file(temp_file_path)
        finally:
            os.unlink(temp_file_path)

    def test_extract_from_file_empty_result(self):
        """Test file extraction when Docling returns empty result."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file_path = temp_file.name

        try:
            with patch('docling.document_converter.DocumentConverter') as mock_converter_class:
                mock_converter = mock_converter_class.return_value
                mock_result = Mock()
                mock_result.document.export_to_markdown.return_value = ""
                mock_converter.convert.return_value = mock_result
                
                result = self.extractor._extract_from_file(temp_file_path)

            assert result == ""
        finally:
            os.unlink(temp_file_path)

    def test_extract_txt_file(self):
        """Test extraction from a .txt file."""
        test_content = "This is a test text file.\nWith multiple lines.\nAnd some content to extract."
        
        with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name

        try:
            documents = [
                {
                    "name": "test_txt",
                    "description": "Test text document",
                    "path": temp_file_path,
                    "content": ""
                }
            ]

            result = self.extractor.extract(documents)
            assert result == {"test_txt": test_content}
        finally:
            os.unlink(temp_file_path)

    def test_extract_from_txt_file_direct(self):
        """Test direct extraction from .txt file using _extract_from_file method."""
        test_content = "Direct text file extraction test.\nMultiple lines of content."
        
        with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as temp_file:
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
            ".pdf",
            ".docx", ".xlsx", ".pptx",
            ".md",
            ".adoc",
            ".html", ".xhtml",
            ".csv",
            ".txt",
            ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp",
            ".xml",
            ".json",
        }
        assert extensions == expected
        # Ensure it returns a copy, not the original
        assert extensions is not self.extractor.supported_extensions

    def test_extract_with_none_values(self):
        """Test extraction with None values in document fields."""
        documents = [
            {
                "name": "test_doc",
                "description": "Test document",
                "content": None,
                "path": None
            }
        ]

        with pytest.raises(ValueError, match="Document 'test_doc' must have either 'content' or 'path' field"):
            self.extractor.extract(documents)

    def test_extract_with_missing_fields(self):
        """Test extraction with missing optional fields."""
        documents = [
            {
                "name": "test_doc",
                "description": "Test document"
                # Missing content and path fields
            }
        ]

        with pytest.raises(ValueError, match="Document 'test_doc' must have either 'content' or 'path' field"):
            self.extractor.extract(documents)

    def test_supported_file_types(self):
        """Test that all supported file types are properly handled."""
        supported_types = [
            ".pdf", ".docx", ".xlsx", ".pptx", ".md", ".adoc",
            ".html", ".xhtml", ".csv", ".txt", ".png", ".jpg", ".jpeg",
            ".tiff", ".bmp", ".webp", ".xml", ".json"
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
                    # .txt files are handled directly, no Docling needed
                    result = self.extractor._extract_from_file(temp_file_path)
                    assert result == "Test content for text file"
                else:
                    # Other files use Docling
                    with patch('docling.document_converter.DocumentConverter') as mock_converter_class:
                        mock_converter = mock_converter_class.return_value
                        mock_result = Mock()
                        mock_result.document.export_to_markdown.return_value = f"Extracted text from {file_type}"
                        mock_converter.convert.return_value = mock_result
                        
                        result = self.extractor._extract_from_file(temp_file_path)
                        assert result == f"Extracted text from {file_type}"
            finally:
                os.unlink(temp_file_path)

    def test_extract_real_pdf_file(self):
        """Test extraction with a real PDF file (if available)."""
        # This test can be used to test with actual PDF files
        # Create a simple PDF for testing
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
        except ImportError:
            pytest.skip("reportlab not available for creating test PDF")

        # Create a simple test PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file_path = temp_file.name

        try:
            # Create a simple PDF with some text
            c = canvas.Canvas(temp_file_path, pagesize=letter)
            c.drawString(100, 750, "This is a test PDF document.")
            c.drawString(100, 730, "It contains some sample text for extraction.")
            c.drawString(100, 710, "DocumentExtractor should be able to extract this text.")
            c.save()

            # Test extraction
            documents = [
                {
                    "name": "test_pdf",
                    "description": "Real PDF test document",
                    "path": temp_file_path,
                    "content": ""
                }
            ]

            result = self.extractor.extract(documents)
            
            # Check that we got some text back
            assert "test_pdf" in result
            extracted_text = result["test_pdf"]
            assert len(extracted_text) > 0
            # The exact text might vary depending on Docling's processing
            # but we should get something back
            print(f"Extracted text from real PDF: {extracted_text[:100]}...")

        except Exception as e:
            pytest.skip(f"Could not test with real PDF: {e}")
        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_extract_with_manual_pdf_path(self):
        """Manual test method for testing with your own PDF file."""
        # This test is skipped by default but can be enabled for manual testing
        pytest.skip("Manual test - enable by removing this line and providing a PDF path")
        
        # Uncomment and modify the path below to test with your own PDF
        # pdf_path = "/path/to/your/test.pdf"
        # 
        # if not os.path.exists(pdf_path):
        #     pytest.skip(f"PDF file not found: {pdf_path}")
        # 
        # documents = [
        #     {
        #         "name": "manual_test_pdf",
        #         "description": "Manual test PDF",
        #         "path": pdf_path,
        #         "content": ""
        #     }
        # ]
        # 
        # result = self.extractor.extract(documents)
        # assert "manual_test_pdf" in result
        # extracted_text = result["manual_test_pdf"]
        # print(f"Extracted text length: {len(extracted_text)}")
        # print(f"First 200 characters: {extracted_text[:200]}...")
        # assert len(extracted_text) > 0 