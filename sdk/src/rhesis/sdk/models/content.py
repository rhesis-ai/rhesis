"""Multimodal content types for LLM messages.

This module provides content type classes for building multimodal messages
that can include text, images, audio, video, and files. Each content type
knows how to convert itself to LiteLLM's expected format.
"""

import base64
import mimetypes
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, Union


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
        ".mp4": "video/mp4",
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
    """

    url: Optional[str] = None
    data: Optional[bytes] = None
    mime_type: str = "image/jpeg"
    detail: Literal["auto", "low", "high"] = "auto"

    @property
    def type(self) -> str:
        return "image"

    @classmethod
    def from_url(cls, url: str, detail: Literal["auto", "low", "high"] = "auto") -> "ImageContent":
        """Create ImageContent from a URL.

        Args:
            url: Image URL
            detail: Detail level for vision models

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
                    "format": self.mime_type.split("/")[-1],  # Extract format from MIME type
                },
            }
        else:
            raise ValueError("AudioContent must have either url or data")


@dataclass
class VideoContent(ContentPart):
    """Video content part.

    Due to size constraints, only URL-based video is supported.
    Used by models like Gemini 1.5+.
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
            raise ValueError("FileContent must have either url or data")


@dataclass
class Message:
    """A message in a multimodal conversation.

    Can contain either simple string content or a list of mixed content parts
    (text, images, audio, video, files).
    """

    role: Literal["user", "assistant", "system"]
    content: Union[str, list[ContentPart]]

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
                # Allow raw strings in content list
                content_parts.append({"type": "text", "text": part})
            elif isinstance(part, ContentPart):
                content_parts.append(part.to_litellm_format())
            else:
                raise TypeError(f"Unsupported content part type: {type(part)}")

        return {"role": self.role, "content": content_parts}
