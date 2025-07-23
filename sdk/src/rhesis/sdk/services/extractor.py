"""Document extraction service using Docling."""

import os
from pathlib import Path
from typing import Dict, List, Optional

# Docling imports are done locally to avoid circular imports


class DocumentExtractor:
    """Extract plain text from supported document files using Docling."""

    def __init__(self) -> None:
        """Initialize the DocumentExtractor."""
        # Supported file extensions based on Docling's supported formats
        # See: https://docling-project.github.io/docling/usage/supported_formats/
        self.supported_extensions = {
            # Document formats
            ".pdf",
            ".docx", ".xlsx", ".pptx",  # MS Office formats
            ".md",  # Markdown
            ".adoc",  # AsciiDoc
            ".html", ".xhtml",  # HTML formats
            ".csv",  # CSV files
            ".txt",  # Plain text files
            # Image formats
            ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp",
            # Schema-specific formats
            ".xml",  # USPTO XML, JATS XML
            ".json",  # Docling JSON
        }

    def extract(self, documents: List[Dict]) -> Dict[str, str]:
        """
        Extract text from a list of documents.

        Args:
            documents: List of document dictionaries with the following fields:
                - name (str): Unique identifier or label for the document
                - description (str): Short description of the document's purpose or content
                - path (str): Local file path (optional, can be empty if content is provided)
                - content (str): Pre-provided document content (optional)

        Returns:
            Dict[str, str]: Dictionary mapping document names to extracted text

        Raises:
            ValueError: If neither content nor path is provided for a document
            FileNotFoundError: If the specified file path doesn't exist
            ValueError: If the file type is not supported
        """
        extracted_texts = {}

        for document in documents:
            name = document.get("name")
            if not name:
                raise ValueError("Document must have a 'name' field")

            content = document.get("content", "")
            path = document.get("path", "")

            # If content is provided, use it directly
            if content:
                extracted_texts[name] = content
                continue

            # If no content but path is provided, extract from file
            if path:
                extracted_text = self._extract_from_file(path)
                extracted_texts[name] = extracted_text
                continue

            # Neither content nor path provided
            raise ValueError(
                f"Document '{name}' must have either 'content' or 'path' field"
            )

        return extracted_texts

    def _extract_from_file(self, file_path: str) -> str:
        """
        Extract text from a file using Docling.

        Args:
            file_path: Path to the file to extract text from

        Returns:
            str: Extracted text from the file

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file type is not supported
        """
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get file extension and check if supported
        file_extension = Path(file_path).suffix.lower()
        if file_extension not in self.supported_extensions:
            raise ValueError(
                f"Unsupported file type: {file_extension}. "
                f"Supported types: {', '.join(self.supported_extensions)}"
            )

        try:
            # Special handling for plain text files - read directly
            if file_extension == ".txt":
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read().strip()
            
            # Use Docling to extract text from the file
            from docling.document_converter import DocumentConverter
            
            converter = DocumentConverter()
            result = converter.convert(file_path)
            
            # Export to markdown and extract the text
            extracted_text = result.document.export_to_markdown()
            return extracted_text.strip() if extracted_text else ""
        except Exception as e:
            raise ValueError(f"Failed to extract text from {file_path}: {str(e)}")

    def get_supported_extensions(self) -> set[str]:
        """
        Get the list of supported file extensions.

        Returns:
            set[str]: Set of supported file extensions (including the dot)
        """
        return self.supported_extensions.copy()