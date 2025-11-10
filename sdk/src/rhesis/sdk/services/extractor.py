"""Document extraction service using Markitdown."""

import os
from abc import ABC, abstractmethod
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from markitdown import MarkItDown
from pydantic import BaseModel


class SourceType(Enum):
    DOCUMENT = "document"
    WEBSITE = "website"
    NOTION = "notion"
    TEXT = "text"


class SourceBase(BaseModel):
    type: SourceType
    name: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[dict] = None


class ExtractedSource(SourceBase):
    content: str


class Extractor(ABC):
    @abstractmethod
    def extract(self, source: SourceBase) -> ExtractedSource:
        pass


class ExtractionService:
    def __call__(self, sources: list[SourceBase]) -> list[ExtractedSource]:
        extracted_sources = []
        for source in sources:
            if source.type == SourceType.TEXT:
                extracted_sources.append(TextExtractor().extract(source))
            elif source.type == SourceType.DOCUMENT:
                extracted_sources.append(DocumentExtractor().extract(source))
            elif source.type == SourceType.WEBSITE:
                extracted_sources.append(WebsiteExtractor().extract(source))
            elif source.type == SourceType.NOTION:
                extracted_sources.append(NotionExtractor().extract(source))
            else:
                raise ValueError(f"Unsupported source type: {source.type}")
        return extracted_sources


class NotionExtractor(Extractor):
    def extract(self, source: SourceBase) -> ExtractedSource:
        raise NotImplementedError("Notion extraction is not implemented")


class TextExtractor(Extractor):
    def extract(self, source: SourceBase) -> ExtractedSource:
        return ExtractedSource(
            **source.model_dump(exclude={"medatadata"}), content=source.metadata["content"]
        )


class WebsiteExtractor(Extractor):
    """Extract text from websites using Markitdown."""

    def __init__(self) -> None:
        """Initialize the WebsiteExtractor."""
        self.converter = MarkItDown()

    def extract(self, source: SourceBase) -> ExtractedSource:
        """
        Extract text from a website source.

        Args:
            source: SourceBase object containing the website source

        Returns:
            ExtractedSource object containing the extracted text

        Raises:
            ValueError: If the source type is not supported or URL is missing
        """
        if source.type != SourceType.WEBSITE:
            raise ValueError(f"Unsupported source type: {source.type}")

        if "url" not in source.metadata:
            raise ValueError("URL not found in source metadata")

        url = source.metadata["url"]
        extracted_text = self._extract_from_url(url)

        return ExtractedSource(**source.model_dump(), content=extracted_text)

    def _extract_from_url(self, url: str) -> str:
        """
        Extract text from a URL using Markitdown.

        Args:
            url: URL of the webpage to extract text from

        Returns:
            str: Extracted text from the webpage

        Raises:
            ValueError: If fetching or extraction fails
        """
        try:
            # Fetch the webpage content with browser-like headers
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/91.0.4472.124 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            response = requests.get(url, timeout=30, headers=headers)
            response.raise_for_status()

            # Use MarkItDown to convert HTML to text
            html_content = BytesIO(response.content)

            from markitdown._stream_info import StreamInfo

            stream_info = StreamInfo(
                filename="webpage.html",
                extension=".html",
                charset="utf-8",
            )

            result = self.converter.convert(html_content, stream_info=stream_info)
            extracted_text = self._extract_text_from_result(result)

            return extracted_text
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch webpage from {url}: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to extract text from {url}: {str(e)}")

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


class DocumentExtractor(Extractor):
    """Extract plain text from supported document files using Markitdown."""

    supported_extensions: set[str] = {
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

    def __init__(self) -> None:
        """Initialize the DocumentExtractor."""
        # Note: Markitdown supports also other formats but may need additional dependencies
        self.converter = MarkItDown()

    def extract(self, source: SourceBase) -> ExtractedSource:
        """
        Extract text from a document source.

        Args:
            source: SourceBase object containing the document source

        Returns:
            ExtractedSource object containing the extracted text

        Raises:
            ValueError: If the source type is not supported
        """
        if source.type != SourceType.DOCUMENT:
            raise ValueError(f"Unsupported source type: {source.type}")

        extracted_text = self._extract_from_file(source.metadata["path"])

        return ExtractedSource(**source.model_dump(), content=extracted_text)

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


if __name__ == "__main__":
    extractor = DocumentExtractor()
    source = SourceBase(
        name="test",
        description="test",
        type=SourceType.DOCUMENT,
        metadata={"path": "/Users/arek/Desktop/rhesis/CHANGELOG.md"},
    )
    extracted_source = extractor.extract(source)
    print(extracted_source)


if __name__ == "__main__":
    extractor = WebsiteExtractor()
    source = SourceBase(
        name="test",
        description="test",
        type=SourceType.WEBSITE,
        metadata={"url": "https://sebastianraschka.com/blog/2025/llm-evaluation-4-approaches.html"},
    )
    extracted_source = extractor.extract(source)
    print(extracted_source)
