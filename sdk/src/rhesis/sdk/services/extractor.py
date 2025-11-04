"""Document extraction service using Markitdown."""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List

from markitdown import MarkItDown

from rhesis.sdk.types import Document


class Extractor(ABC):
    @abstractmethod
    def extract(self, *args: Any, **kwargs: Any) -> Dict[str, str]:
        pass


class DocumentExtractor(Extractor):
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
            ".md",
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

    def extract(self, documents: List[Document]) -> Dict[str, str]:
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
            name = document.name

            content = document.content
            path = document.path

            # If content is provided, use it directly
            if content:
                extracted_texts[name] = content
                continue

            # If no content but path is provided, extract from file
            if path:
                extracted_text = self._extract_from_file(path)
                extracted_texts[name] = extracted_text
                continue

        return extracted_texts

    def extract_from_bytes(self, file_content: bytes, filename: str) -> str:
        """
        Extract text from binary file content using Markitdown.

        Args:
            file_content: Binary content of the file
            filename: Original filename with extension

        Returns:
            str: Extracted text from the file

        Raises:
            ValueError: If the file type is not supported or extraction fails
        """
        # Get file extension and check if supported
        file_extension = Path(filename).suffix.lower()
        self._validate_file_extension(file_extension)

        # Extract directly from bytes using BytesIO
        from io import BytesIO

        # Create a BytesIO object from the binary content
        file_like_object = BytesIO(file_content)

        # Always use UTF-8 encoding to prevent ASCII decoding errors
        from markitdown._stream_info import StreamInfo

        stream_info = StreamInfo(
            filename=filename,
            extension=file_extension,
            charset="utf-8",  # Default to UTF-8 for all text files
        )

        result = self.converter.convert(file_like_object, stream_info=stream_info)
        return self._extract_text_from_result(result)

    def _extract_text_from_result(self, result) -> str:
        """
        Extract text content from MarkItDown result object.

        Args:
            result: MarkItDown conversion result

        Returns:
            str: Extracted text content
        """
        if hasattr(result, "text_content") and result.text_content:
            extracted_text = result.text_content
        elif hasattr(result, "markdown") and result.markdown:
            extracted_text = result.markdown
        else:
            extracted_text = str(result)

        return extracted_text.strip() if extracted_text else ""

    def _validate_file_extension(self, file_extension: str) -> None:
        """
        Validate that the file extension is supported.

        Args:
            file_extension: File extension to validate

        Raises:
            ValueError: If the file extension is not supported
        """
        if file_extension not in self.supported_extensions:
            raise ValueError(
                f"Unsupported file type: {file_extension}. "
                f"Supported types: {', '.join(self.supported_extensions)}"
            )

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
        self._validate_file_extension(file_extension)

        # Always use UTF-8 encoding to prevent ASCII decoding errors
        from markitdown._stream_info import StreamInfo

        stream_info = StreamInfo(
            local_path=file_path,
            filename=Path(file_path).name,
            extension=file_extension,
            charset="utf-8",  # Default to UTF-8 for all text files
        )

        try:
            result = self.converter.convert(file_path, stream_info=stream_info)
            return self._extract_text_from_result(result)
        except Exception as e:
            raise ValueError(f"Failed to extract text from {file_path}: {str(e)}")

    def get_supported_extensions(self) -> set[str]:
        """
        Get the list of supported file extensions.

        Returns:
            set[str]: Set of supported file extensions (including the dot)
        """
        return self.supported_extensions.copy()
