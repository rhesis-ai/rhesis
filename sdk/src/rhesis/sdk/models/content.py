"""Multimodal content types for LLM messages.

This module provides content type classes for building multimodal messages
that can include text, images, audio, video, and files. Each content type
knows how to convert itself to LiteLLM's expected format.

Example:
    Basic image analysis::

        >>> from rhesis.sdk.models import ImageContent, Message, get_model
        >>> model = get_model("gemini", "gemini-2.0-flash")
        >>> content = ImageContent.from_file("photo.jpg")
        >>> response = model.analyze_content(content, "Describe this image")

    Multi-image comparison::

        >>> messages = [Message(role="user", content=[
        ...     ImageContent.from_file("img1.jpg"),
        ...     ImageContent.from_file("img2.jpg"),
        ...     "Compare these images"
        ... ])]
        >>> response = model.generate_multimodal(messages)
"""

import base64
import logging
import mimetypes
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, Union

from rhesis.sdk.errors import (
    AUDIO_CONTENT_MISSING_DATA,
    FILE_CONTENT_MISSING_DATA,
    IMAGE_CONTENT_MISSING_DATA,
    VIDEO_FILE_NOT_FOUND,
    VIDEO_FILE_TOO_LARGE,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ContentPart",
    "TextContent",
    "ImageContent",
    "AudioContent",
    "VideoContent",
    "FileContent",
    "Message",
    "detect_mime_type",
    "MAX_VIDEO_SIZE_MB",
]

# Maximum video file size in MB for local file upload
MAX_VIDEO_SIZE_MB = 50

# Audio format mapping from MIME type to format name
# Some APIs expect specific format names (e.g., "mp3" not "mpeg")
AUDIO_FORMAT_MAP = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/flac": "flac",
    "audio/aac": "aac",
    "audio/m4a": "m4a",
    "audio/webm": "webm",
}


def detect_mime_type(path: Union[str, Path]) -> str:
    """Detect MIME type from file path.

    Args:
        path: File path

    Returns:
        MIME type string (e.g., 'image/jpeg')
    """
    path = Path(path)
    mime_type, _ = mimetypes.guess_type(str(path))

    if mime_type:
        return mime_type

    # Fallback based on extension
    extension = path.suffix.lower()
    extension_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".aac": "audio/aac",
        ".m4a": "audio/m4a",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".webm": "video/webm",
        ".pdf": "application/pdf",
    }

    return extension_map.get(extension, "application/octet-stream")


@dataclass
class ContentPart(ABC):
    """Abstract base class for content parts in multimodal messages."""

    @property
    @abstractmethod
    def type(self) -> str:
        """Return the type identifier for this content."""
        pass

    @abstractmethod
    def to_litellm_format(self) -> dict:
        """Convert to LiteLLM's expected message content format."""
        pass


@dataclass
class TextContent(ContentPart):
    """Text content part."""

    text: str

    @property
    def type(self) -> str:
        return "text"

    def to_litellm_format(self) -> dict:
        """Convert to LiteLLM format."""
        return {"type": "text", "text": self.text}


@dataclass
class ImageContent(ContentPart):
    """Image content part.

    Can be created from URL, file path, or raw bytes.
    Supports OpenAI's detail parameter for vision models.

    Note:
        The `detail` parameter is OpenAI-specific and controls image processing
        resolution. Other providers may ignore this parameter. Values:
        - "auto": Let the model decide (default)
        - "low": Lower resolution, faster processing
        - "high": Higher resolution, more detail
    """

    url: Optional[str] = None
    data: Optional[bytes] = None
    mime_type: str = "image/jpeg"
    detail: Literal["auto", "low", "high"] = "auto"

    def __post_init__(self):
        """Validate that either url or data is provided."""
        if self.url is None and self.data is None:
            raise ValueError(IMAGE_CONTENT_MISSING_DATA)

    @property
    def type(self) -> str:
        return "image"

    @classmethod
    def from_url(cls, url: str, detail: Literal["auto", "low", "high"] = "auto") -> "ImageContent":
        """Create ImageContent from a URL.

        Args:
            url: Image URL
            detail: Detail level for vision models (OpenAI-specific)

        Returns:
            ImageContent instance
        """
        return cls(url=url, detail=detail)

    @classmethod
    def from_file(
        cls, path: Union[str, Path], detail: Literal["auto", "low", "high"] = "auto"
    ) -> "ImageContent":
        """Create ImageContent from a local file.

        Args:
            path: Path to image file
            detail: Detail level for vision models

        Returns:
            ImageContent instance with base64-encoded data
        """
        path = Path(path)
        mime_type = detect_mime_type(path)

        with open(path, "rb") as f:
            data = f.read()

        return cls(data=data, mime_type=mime_type, detail=detail)

    @classmethod
    def from_bytes(
        cls, data: bytes, mime_type: str, detail: Literal["auto", "low", "high"] = "auto"
    ) -> "ImageContent":
        """Create ImageContent from raw bytes.

        Args:
            data: Raw image bytes
            mime_type: MIME type (e.g., 'image/jpeg')
            detail: Detail level for vision models

        Returns:
            ImageContent instance
        """
        return cls(data=data, mime_type=mime_type, detail=detail)

    @classmethod
    def from_base64(
        cls,
        data: str,
        mime_type: str = "image/jpeg",
        detail: Literal["auto", "low", "high"] = "auto",
    ) -> "ImageContent":
        """Create ImageContent from a base64-encoded string.

        Args:
            data: Base64-encoded image data (without data URL prefix)
            mime_type: MIME type (e.g., 'image/jpeg', 'image/png')
            detail: Detail level for vision models

        Returns:
            ImageContent instance

        Example:
            >>> # From raw base64 string
            >>> content = ImageContent.from_base64("iVBORw0KGgo...", mime_type="image/png")
            >>> # From data URL (prefix will be stripped)
            >>> content = ImageContent.from_base64(
            ...     "data:image/png;base64,iVBORw0KGgo...",
            ...     mime_type="image/png"
            ... )
        """
        # Strip data URL prefix if present (e.g., "data:image/png;base64,")
        if data.startswith("data:"):
            # Extract the base64 part after the comma
            if "," in data:
                data = data.split(",", 1)[1]

        decoded_data = base64.b64decode(data)
        return cls(data=decoded_data, mime_type=mime_type, detail=detail)

    def to_litellm_format(self) -> dict:
        """Convert to LiteLLM format.

        Returns:
            Dict in format: {"type": "image_url", "image_url": {...}}
        """
        if self.url:
            image_url = self.url
        elif self.data:
            # Encode as base64 data URL
            encoded = base64.standard_b64encode(self.data).decode("utf-8")
            image_url = f"data:{self.mime_type};base64,{encoded}"
        else:
            raise ValueError("ImageContent must have either url or data")

        return {"type": "image_url", "image_url": {"url": image_url, "detail": self.detail}}


@dataclass
class AudioContent(ContentPart):
    """Audio content part.

    Supports audio input for models like Gemini and Whisper.
    """

    url: Optional[str] = None
    data: Optional[bytes] = None
    mime_type: str = "audio/mpeg"

    def __post_init__(self):
        """Validate that either url or data is provided."""
        if self.url is None and self.data is None:
            raise ValueError(AUDIO_CONTENT_MISSING_DATA)

    @property
    def type(self) -> str:
        return "audio"

    @classmethod
    def from_url(cls, url: str, mime_type: Optional[str] = None) -> "AudioContent":
        """Create AudioContent from a URL.

        Args:
            url: Audio URL
            mime_type: Optional MIME type override

        Returns:
            AudioContent instance
        """
        return cls(url=url, mime_type=mime_type or "audio/mpeg")

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "AudioContent":
        """Create AudioContent from a local file.

        Args:
            path: Path to audio file

        Returns:
            AudioContent instance with base64-encoded data
        """
        path = Path(path)
        mime_type = detect_mime_type(path)

        with open(path, "rb") as f:
            data = f.read()

        return cls(data=data, mime_type=mime_type)

    @classmethod
    def from_bytes(cls, data: bytes, mime_type: str) -> "AudioContent":
        """Create AudioContent from raw bytes.

        Args:
            data: Raw audio bytes
            mime_type: MIME type (e.g., 'audio/mpeg')

        Returns:
            AudioContent instance
        """
        return cls(data=data, mime_type=mime_type)

    @classmethod
    def from_base64(cls, data: str, mime_type: str = "audio/mpeg") -> "AudioContent":
        """Create AudioContent from a base64-encoded string.

        Args:
            data: Base64-encoded audio data (without data URL prefix)
            mime_type: MIME type (e.g., 'audio/mpeg', 'audio/wav')

        Returns:
            AudioContent instance

        Example:
            >>> # From raw base64 string
            >>> content = AudioContent.from_base64("SGVsbG8gV29ybGQ=", mime_type="audio/wav")
            >>> # From data URL (prefix will be stripped)
            >>> content = AudioContent.from_base64(
            ...     "data:audio/wav;base64,SGVsbG8gV29ybGQ=",
            ...     mime_type="audio/wav"
            ... )
        """
        # Strip data URL prefix if present (e.g., "data:audio/wav;base64,")
        if data.startswith("data:"):
            if "," in data:
                data = data.split(",", 1)[1]

        decoded_data = base64.b64decode(data)
        return cls(data=decoded_data, mime_type=mime_type)

    def _get_audio_format(self) -> str:
        """Get the audio format name for the API.

        Returns:
            Format name (e.g., 'mp3', 'wav') suitable for API consumption
        """
        # Use the mapping if available, otherwise extract from MIME type
        return AUDIO_FORMAT_MAP.get(self.mime_type, self.mime_type.split("/")[-1])

    def to_litellm_format(self) -> dict:
        """Convert to LiteLLM format.

        Returns:
            Dict in format for audio input
        """
        if self.url:
            return {"type": "input_audio", "input_audio": {"url": self.url}}
        elif self.data:
            encoded = base64.standard_b64encode(self.data).decode("utf-8")
            return {
                "type": "input_audio",
                "input_audio": {
                    "data": encoded,
                    "format": self._get_audio_format(),
                },
            }
        else:
            # This should never happen due to __post_init__ validation
            raise ValueError("AudioContent must have either url or data")


@dataclass
class VideoContent(ContentPart):
    """Video content part.

    Supports video input for models like Gemini 1.5+.

    Note:
        For local files, use from_file() which includes size validation.
        Large videos (>50MB by default) should be uploaded to a URL instead.
    """

    url: str
    mime_type: str = "video/mp4"

    @property
    def type(self) -> str:
        return "video"

    @classmethod
    def from_url(cls, url: str, mime_type: str = "video/mp4") -> "VideoContent":
        """Create VideoContent from a URL.

        Args:
            url: Video URL
            mime_type: MIME type

        Returns:
            VideoContent instance
        """
        return cls(url=url, mime_type=mime_type)

    @classmethod
    def from_file(
        cls, path: Union[str, Path], max_size_mb: int = MAX_VIDEO_SIZE_MB
    ) -> "VideoContent":
        """Create VideoContent from a local file.

        Encodes the video as a base64 data URL. For large videos,
        consider uploading to cloud storage and using from_url() instead.

        Args:
            path: Path to video file.
            max_size_mb: Maximum allowed file size in MB (default: 50MB).
                Set to 0 to disable size check (not recommended).

        Returns:
            VideoContent instance with base64-encoded data URL.

        Raises:
            ValueError: If file exceeds max_size_mb.
            FileNotFoundError: If file doesn't exist.

        Example:
            >>> content = VideoContent.from_file("short_clip.mp4")
            >>> # For larger files, increase limit (use with caution)
            >>> content = VideoContent.from_file("large_video.mp4", max_size_mb=100)
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(VIDEO_FILE_NOT_FOUND.format(path=path))

        # Check file size
        size_bytes = path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)

        if max_size_mb > 0 and size_mb > max_size_mb:
            raise ValueError(VIDEO_FILE_TOO_LARGE.format(size_mb=size_mb, max_size_mb=max_size_mb))

        if size_mb > 20:
            logger.warning(
                "Video file is %.1fMB. Large videos may cause slow uploads "
                "and API timeouts. Consider using VideoContent.from_url() with cloud storage.",
                size_mb,
            )

        mime_type = detect_mime_type(path)

        with open(path, "rb") as f:
            data = f.read()

        encoded = base64.standard_b64encode(data).decode("utf-8")
        data_url = f"data:{mime_type};base64,{encoded}"

        return cls(url=data_url, mime_type=mime_type)

    def to_litellm_format(self) -> dict:
        """Convert to LiteLLM format.

        Returns:
            Dict for video input
        """
        return {"type": "video", "video": {"url": self.url}}


@dataclass
class FileContent(ContentPart):
    """File content part for documents and PDFs.

    Supports various document formats that can be processed by vision models.
    """

    url: Optional[str] = None
    data: Optional[bytes] = None
    mime_type: str = "application/pdf"

    def __post_init__(self):
        """Validate that either url or data is provided."""
        if self.url is None and self.data is None:
            raise ValueError(FILE_CONTENT_MISSING_DATA)

    @property
    def type(self) -> str:
        return "file"

    @classmethod
    def from_url(cls, url: str, mime_type: Optional[str] = None) -> "FileContent":
        """Create FileContent from a URL.

        Args:
            url: File URL
            mime_type: Optional MIME type override

        Returns:
            FileContent instance
        """
        # Try to detect MIME type from URL
        if mime_type is None:
            mime_type = detect_mime_type(url)
        return cls(url=url, mime_type=mime_type)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "FileContent":
        """Create FileContent from a local file.

        Args:
            path: Path to file

        Returns:
            FileContent instance with base64-encoded data
        """
        path = Path(path)
        mime_type = detect_mime_type(path)

        with open(path, "rb") as f:
            data = f.read()

        return cls(data=data, mime_type=mime_type)

    @classmethod
    def from_bytes(cls, data: bytes, mime_type: str) -> "FileContent":
        """Create FileContent from raw bytes.

        Args:
            data: Raw file bytes
            mime_type: MIME type (e.g., 'application/pdf')

        Returns:
            FileContent instance
        """
        return cls(data=data, mime_type=mime_type)

    @classmethod
    def from_base64(cls, data: str, mime_type: str = "application/pdf") -> "FileContent":
        """Create FileContent from a base64-encoded string.

        Args:
            data: Base64-encoded file data (without data URL prefix)
            mime_type: MIME type (e.g., 'application/pdf')

        Returns:
            FileContent instance

        Example:
            >>> # From raw base64 string
            >>> content = FileContent.from_base64("JVBERi0xLjQ=", mime_type="application/pdf")
            >>> # From data URL (prefix will be stripped)
            >>> content = FileContent.from_base64(
            ...     "data:application/pdf;base64,JVBERi0xLjQ=",
            ...     mime_type="application/pdf"
            ... )
        """
        # Strip data URL prefix if present (e.g., "data:application/pdf;base64,")
        if data.startswith("data:"):
            if "," in data:
                data = data.split(",", 1)[1]

        decoded_data = base64.b64decode(data)
        return cls(data=decoded_data, mime_type=mime_type)

    def to_litellm_format(self) -> dict:
        """Convert to LiteLLM format.

        Returns:
            Dict for file/document input
        """
        if self.url:
            return {"type": "file", "file": {"url": self.url}}
        elif self.data:
            # For inline file data, use image_url format with data URL
            encoded = base64.standard_b64encode(self.data).decode("utf-8")
            return {
                "type": "image_url",
                "image_url": {"url": f"data:{self.mime_type};base64,{encoded}"},
            }
        else:
            # This should never happen due to __post_init__ validation
            raise ValueError("FileContent must have either url or data")


@dataclass
class Message:
    """A message in a multimodal conversation.

    Can contain either simple string content or a list of mixed content parts
    (text, images, audio, video, files).

    Examples:
        >>> # Simple text message
        >>> msg = Message(role="user", content="Hello!")

        >>> # Mixed content with image and text
        >>> msg = Message(
        ...     role="user",
        ...     content=[
        ...         ImageContent.from_file("photo.jpg"),
        ...         "What's in this image?",  # Raw strings are allowed
        ...         TextContent("Please describe it."),
        ...     ]
        ... )
    """

    role: Literal["user", "assistant", "system"]
    content: Union[str, list[Union[str, ContentPart]]]

    def to_litellm_format(self) -> dict:
        """Convert message to LiteLLM's expected format.

        Returns:
            Dict with 'role' and 'content' keys
        """
        if isinstance(self.content, str):
            # Simple string content - backward compatible
            return {"role": self.role, "content": self.content}

        # Mixed content - convert each part
        content_parts = []
        for part in self.content:
            if isinstance(part, str):
                # Allow raw strings in content list for convenience
                content_parts.append({"type": "text", "text": part})
            elif isinstance(part, ContentPart):
                content_parts.append(part.to_litellm_format())
            else:
                raise TypeError(f"Unsupported content part type: {type(part)}")

        return {"role": self.role, "content": content_parts}
