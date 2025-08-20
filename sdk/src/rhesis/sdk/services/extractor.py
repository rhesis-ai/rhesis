"""Document extraction service using Markitdown."""

import os
from pathlib import Path
from typing import Dict, List
from markitdown import MarkItDown


class DocumentExtractor:
    """Extract plain text from supported document files using Markitdown."""

    def __init__(self) -> None:
        """Initialize the DocumentExtractor."""
        # Note: Markitdown supports also other formats but may need additional dependencies
        self.supported_extensions = {
            # Office formats
            ".docx",
            ".pptx", 
            ".xlsx",
            
            # Documents
            ".pdf",
            ".txt",
            ".csv",
            ".json",
            ".xml",
            ".html",
            ".htm",
            
            # Archives (iterate over contents)
            ".zip",
            # E-books
            ".epub",
        }
        
        self.converter = MarkItDown()

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
            raise ValueError(f"Document '{name}' must have either 'content' or 'path' field")

        return extracted_texts

    def _extract_from_file(self, file_path: str) -> str:
        """
        Extract text from a file using Markitdown.

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
            result = self.converter.convert_local(file_path)

            # Extract text from result - markitdown returns text_content and markdown
            if hasattr(result, 'text_content') and result.text_content:
                extracted_text = result.text_content
            elif hasattr(result, 'markdown') and result.markdown:
                extracted_text = result.markdown
            else:
                # Fallback to string representation
                extracted_text = str(result)

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
