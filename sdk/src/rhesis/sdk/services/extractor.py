"""Document extraction service using Markitdown."""

import os
from abc import ABC, abstractmethod
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

import requests
from markitdown import MarkItDown
from pydantic import BaseModel

if TYPE_CHECKING:
    from rhesis.sdk.models.base import BaseLLM
    from rhesis.sdk.models.factory import LanguageModelConfig


class SourceType(Enum):
    DOCUMENT = "document"
    IMAGE = "image"
    WEBSITE = "website"
    NOTION = "notion"
    TEXT = "text"


class SourceSpecification(BaseModel):
    type: SourceType
    name: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[dict] = None


class ExtractedSource(SourceSpecification):
    content: str


class Extractor(ABC):
    @abstractmethod
    def extract(self, source: SourceSpecification) -> ExtractedSource:
        pass


class ExtractionService:
    """Service for extracting text from sources."""

    @staticmethod
    def extract(
        sources: list[SourceSpecification],
        model: Optional[Union["BaseLLM", "LanguageModelConfig"]] = None,
    ) -> list[ExtractedSource]:
        """Extract content from a list of sources.

        Args:
            sources: Sources to process.
            model: Optional SDK language model (``BaseLLM`` instance or
                ``LanguageModelConfig``) used for vision-based image description.
                When omitted, image sources fall back to EXIF-only extraction.
        """
        from rhesis.sdk.models.base import BaseLLM
        from rhesis.sdk.models.factory import LanguageModelConfig, get_language_model

        resolved_model: Optional[BaseLLM] = None
        if model is not None:
            if isinstance(model, LanguageModelConfig):
                resolved_model = get_language_model(config=model)
            else:
                resolved_model = model

        extracted_sources = []
        for source in sources:
            if source.type == SourceType.TEXT:
                extracted_sources.append(IdentityExtractor().extract(source))
            elif source.type == SourceType.DOCUMENT:
                extracted_sources.append(DocumentExtractor().extract(source))
            elif source.type == SourceType.IMAGE:
                extracted_sources.append(ImageExtractor(model=resolved_model).extract(source))
            elif source.type == SourceType.WEBSITE:
                extracted_sources.append(WebsiteExtractor().extract(source))
            elif source.type == SourceType.NOTION:
                extracted_sources.append(NotionExtractor().extract(source))
            else:
                raise ValueError(f"Unsupported source type: {source.type}")
        return extracted_sources


class NotionExtractor(Extractor):
    def extract(self, source: SourceSpecification) -> ExtractedSource:
        raise NotImplementedError("Notion extraction is not implemented")


class IdentityExtractor(Extractor):
    def extract(self, source: SourceSpecification) -> ExtractedSource:
        return ExtractedSource(
            **source.model_dump(exclude={"metadata"}), content=source.metadata["content"]
        )


class WebsiteExtractor(Extractor):
    """Extract text from websites using Markitdown."""

    def __init__(self) -> None:
        """Initialize the WebsiteExtractor."""
        self.converter = MarkItDown()

    def extract(self, source: SourceSpecification) -> ExtractedSource:
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


class _MarkItDownModelAdapter:
    """Adapts an SDK ``BaseLLM`` to the OpenAI ``chat.completions`` interface
    expected by MarkItDown for vision-based image description.

    MarkItDown calls::

        llm_client.chat.completions.create(model=..., messages=[...])

    where ``messages`` contain base64-encoded image payloads.  Because all SDK
    language model providers are LiteLLM-backed, this adapter routes those calls
    directly through ``litellm.completion`` using the model's own credentials,
    so *any* registered provider (OpenAI, Gemini, Anthropic, Vertex AI, …) works
    transparently.
    """

    def __init__(self, llm: "BaseLLM") -> None:
        self._llm = llm
        self.chat = _MarkItDownModelAdapter._Chat(llm)

    class _Chat:
        def __init__(self, llm: "BaseLLM") -> None:
            self.completions = _MarkItDownModelAdapter._Completions(llm)

    class _Completions:
        def __init__(self, llm: "BaseLLM") -> None:
            self._llm = llm

        def create(self, model: str, messages: list, **kwargs):
            import litellm

            return litellm.completion(
                model=self._llm.model_name,
                messages=messages,
                api_key=getattr(self._llm, "api_key", None),
                api_base=getattr(self._llm, "api_base", None),
                api_version=getattr(self._llm, "api_version", None),
                **kwargs,
            )


class ImageExtractor(Extractor):
    """Extract text/description from image files using Markitdown.

    Pass a ``model`` (any SDK ``BaseLLM`` instance or ``LanguageModelConfig``)
    to enable vision-based description via the model's provider.  Without one,
    only EXIF metadata is extracted.

    Supported ``SourceSpecification.metadata`` keys:
        - ``path`` (str): local file path to an image.
        - ``url``  (str): HTTP(S) URL of an image to download and process.

    At least one of ``path`` or ``url`` must be present.

    Example::

        # EXIF-only (no model)
        extractor = ImageExtractor()

        # Vision description via any SDK provider
        from rhesis.sdk.models.factory import get_language_model
        llm = get_language_model("openai/gpt-4o")
        extractor = ImageExtractor(model=llm)
    """

    supported_extensions: set[str] = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".bmp",
        ".tiff",
        ".tif",
    }

    _CONTENT_TYPE_MAP: dict[str, str] = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/tiff": ".tiff",
    }

    def __init__(
        self,
        model: Optional[Union["BaseLLM", "LanguageModelConfig"]] = None,
    ) -> None:
        from rhesis.sdk.models.base import BaseLLM
        from rhesis.sdk.models.factory import LanguageModelConfig, get_language_model

        resolved: Optional[BaseLLM] = None
        if model is not None:
            if isinstance(model, LanguageModelConfig):
                resolved = get_language_model(config=model)
            else:
                resolved = model

        if resolved is not None:
            adapter = _MarkItDownModelAdapter(resolved)
            self.converter = MarkItDown(
                llm_client=adapter,
                llm_model=resolved.model_name,
            )
        else:
            self.converter = MarkItDown()

    def extract(self, source: SourceSpecification) -> ExtractedSource:
        if source.type != SourceType.IMAGE:
            raise ValueError(f"Unsupported source type: {source.type}")

        metadata = source.metadata or {}

        if "path" in metadata:
            content = self._extract_from_file(metadata["path"])
        elif "url" in metadata:
            content = self._extract_from_url(metadata["url"])
        else:
            raise ValueError("Image source metadata must contain 'path' or 'url'")

        return ExtractedSource(**source.model_dump(), content=content)

    def extract_from_bytes(self, file_content: bytes, filename: str) -> str:
        """Extract content from raw image bytes.

        Args:
            file_content: Binary content of the image.
            filename: Original filename used to infer the image format.

        Returns:
            Extracted text / description.
        """
        file_extension = Path(filename).suffix.lower()
        self._validate_extension(file_extension)

        from markitdown._stream_info import StreamInfo

        stream_info = StreamInfo(filename=filename, extension=file_extension)
        try:
            result = self.converter.convert(BytesIO(file_content), stream_info=stream_info)
            return self._text_from_result(result)
        except Exception as e:
            raise ValueError(f"Failed to extract content from image bytes: {str(e)}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_from_file(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Image file not found: {file_path}")

        file_extension = Path(file_path).suffix.lower()
        self._validate_extension(file_extension)

        try:
            result = self.converter.convert(file_path)
            return self._text_from_result(result)
        except Exception as e:
            raise ValueError(f"Failed to extract content from image {file_path}: {str(e)}")

    def _extract_from_url(self, url: str) -> str:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch image from {url}: {str(e)}")

        content_type = response.headers.get("content-type", "")
        ext = self._ext_from_content_type(content_type) or Path(url.split("?")[0]).suffix.lower()
        if ext not in self.supported_extensions:
            ext = ".jpg"

        from markitdown._stream_info import StreamInfo

        stream_info = StreamInfo(filename=f"image{ext}", extension=ext)
        try:
            result = self.converter.convert(BytesIO(response.content), stream_info=stream_info)
            return self._text_from_result(result)
        except Exception as e:
            raise ValueError(f"Failed to extract content from image URL {url}: {str(e)}")

    def _validate_extension(self, file_extension: str) -> None:
        if file_extension not in self.supported_extensions:
            raise ValueError(
                f"Unsupported image type: {file_extension}. "
                f"Supported types: {', '.join(sorted(self.supported_extensions))}"
            )

    def _ext_from_content_type(self, content_type: str) -> Optional[str]:
        for mime, ext in self._CONTENT_TYPE_MAP.items():
            if mime in content_type:
                return ext
        return None

    def _text_from_result(self, result) -> str:
        if hasattr(result, "text_content") and result.text_content:
            return result.text_content.strip()
        if hasattr(result, "markdown") and result.markdown:
            return result.markdown.strip()
        return str(result).strip()


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

    def extract(self, source: SourceSpecification) -> ExtractedSource:
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
