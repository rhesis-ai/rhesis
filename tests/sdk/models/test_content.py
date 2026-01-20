"""Tests for multimodal content types."""

import base64
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from rhesis.sdk.models.content import (
    AudioContent,
    FileContent,
    ImageContent,
    Message,
    TextContent,
    VideoContent,
    detect_mime_type,
)


class TestDetectMimeType:
    """Test MIME type detection."""

    def test_detect_mime_type_image(self):
        """Test MIME type detection for images."""
        assert detect_mime_type("image.jpg") == "image/jpeg"
        assert detect_mime_type("image.jpeg") == "image/jpeg"
        assert detect_mime_type("image.png") == "image/png"
        assert detect_mime_type("image.gif") == "image/gif"
        assert detect_mime_type("image.webp") == "image/webp"

    def test_detect_mime_type_audio(self):
        """Test MIME type detection for audio."""
        assert detect_mime_type("audio.mp3") == "audio/mpeg"
        # Note: mimetypes module returns 'audio/x-wav' for .wav files
        assert detect_mime_type("audio.wav") == "audio/x-wav"

    def test_detect_mime_type_video(self):
        """Test MIME type detection for video."""
        assert detect_mime_type("video.mp4") == "video/mp4"

    def test_detect_mime_type_pdf(self):
        """Test MIME type detection for PDF."""
        assert detect_mime_type("document.pdf") == "application/pdf"

    def test_detect_mime_type_unknown(self):
        """Test fallback for unknown extensions."""
        # Use a truly unknown extension that won't be in mimetypes
        assert detect_mime_type("file.unknownext123") == "application/octet-stream"


class TestTextContent:
    """Test TextContent class."""

    def test_creation(self):
        """Test TextContent creation."""
        content = TextContent(text="Hello, world!")
        assert content.text == "Hello, world!"
        assert content.type == "text"

    def test_to_litellm_format(self):
        """Test conversion to LiteLLM format."""
        content = TextContent(text="Hello, world!")
        result = content.to_litellm_format()

        assert result == {"type": "text", "text": "Hello, world!"}


class TestImageContent:
    """Test ImageContent class."""

    def test_from_url(self):
        """Test creating ImageContent from URL."""
        content = ImageContent.from_url("https://example.com/image.jpg")

        assert content.url == "https://example.com/image.jpg"
        assert content.data is None
        assert content.detail == "auto"

    def test_from_url_with_detail(self):
        """Test creating ImageContent from URL with detail parameter."""
        content = ImageContent.from_url("https://example.com/image.jpg", detail="high")

        assert content.detail == "high"

    @patch("builtins.open", new_callable=mock_open, read_data=b"fake image data")
    @patch("rhesis.sdk.models.content.detect_mime_type", return_value="image/jpeg")
    def test_from_file(self, mock_detect, mock_file):
        """Test creating ImageContent from file."""
        content = ImageContent.from_file("/path/to/image.jpg")

        assert content.data == b"fake image data"
        assert content.mime_type == "image/jpeg"
        assert content.url is None
        mock_file.assert_called_once_with(Path("/path/to/image.jpg"), "rb")

    def test_from_bytes(self):
        """Test creating ImageContent from bytes."""
        data = b"fake image data"
        content = ImageContent.from_bytes(data, "image/png")

        assert content.data == data
        assert content.mime_type == "image/png"
        assert content.url is None

    def test_to_litellm_format_url(self):
        """Test conversion to LiteLLM format with URL."""
        content = ImageContent.from_url("https://example.com/image.jpg", detail="high")
        result = content.to_litellm_format()

        assert result == {
            "type": "image_url",
            "image_url": {"url": "https://example.com/image.jpg", "detail": "high"},
        }

    def test_to_litellm_format_base64(self):
        """Test conversion to LiteLLM format with base64 data."""
        data = b"fake image data"
        content = ImageContent.from_bytes(data, "image/jpeg")
        result = content.to_litellm_format()

        expected_b64 = base64.standard_b64encode(data).decode("utf-8")
        assert result == {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{expected_b64}", "detail": "auto"},
        }

    def test_to_litellm_format_no_url_or_data(self):
        """Test that conversion fails without URL or data."""
        content = ImageContent()
        with pytest.raises(ValueError, match="must have either url or data"):
            content.to_litellm_format()


class TestAudioContent:
    """Test AudioContent class."""

    def test_from_url(self):
        """Test creating AudioContent from URL."""
        content = AudioContent.from_url("https://example.com/audio.mp3")

        assert content.url == "https://example.com/audio.mp3"
        assert content.data is None
        assert content.mime_type == "audio/mpeg"

    @patch("builtins.open", new_callable=mock_open, read_data=b"fake audio data")
    @patch("rhesis.sdk.models.content.detect_mime_type", return_value="audio/wav")
    def test_from_file(self, mock_detect, mock_file):
        """Test creating AudioContent from file."""
        content = AudioContent.from_file("/path/to/audio.wav")

        assert content.data == b"fake audio data"
        assert content.mime_type == "audio/wav"
        mock_file.assert_called_once_with(Path("/path/to/audio.wav"), "rb")

    def test_from_bytes(self):
        """Test creating AudioContent from bytes."""
        data = b"fake audio data"
        content = AudioContent.from_bytes(data, "audio/mpeg")

        assert content.data == data
        assert content.mime_type == "audio/mpeg"

    def test_to_litellm_format_url(self):
        """Test conversion to LiteLLM format with URL."""
        content = AudioContent.from_url("https://example.com/audio.mp3")
        result = content.to_litellm_format()

        assert result == {
            "type": "input_audio",
            "input_audio": {"url": "https://example.com/audio.mp3"},
        }

    def test_to_litellm_format_base64(self):
        """Test conversion to LiteLLM format with base64 data."""
        data = b"fake audio data"
        content = AudioContent.from_bytes(data, "audio/mpeg")
        result = content.to_litellm_format()

        expected_b64 = base64.standard_b64encode(data).decode("utf-8")
        assert result == {
            "type": "input_audio",
            "input_audio": {"data": expected_b64, "format": "mpeg"},
        }


class TestVideoContent:
    """Test VideoContent class."""

    def test_from_url(self):
        """Test creating VideoContent from URL."""
        content = VideoContent.from_url("https://example.com/video.mp4")

        assert content.url == "https://example.com/video.mp4"
        assert content.mime_type == "video/mp4"

    def test_to_litellm_format(self):
        """Test conversion to LiteLLM format."""
        content = VideoContent.from_url("https://example.com/video.mp4")
        result = content.to_litellm_format()

        assert result == {"type": "video", "video": {"url": "https://example.com/video.mp4"}}


class TestFileContent:
    """Test FileContent class."""

    def test_from_url(self):
        """Test creating FileContent from URL."""
        content = FileContent.from_url("https://example.com/document.pdf")

        assert content.url == "https://example.com/document.pdf"
        assert content.data is None

    @patch("builtins.open", new_callable=mock_open, read_data=b"fake pdf data")
    @patch("rhesis.sdk.models.content.detect_mime_type", return_value="application/pdf")
    def test_from_file(self, mock_detect, mock_file):
        """Test creating FileContent from file."""
        content = FileContent.from_file("/path/to/document.pdf")

        assert content.data == b"fake pdf data"
        assert content.mime_type == "application/pdf"
        mock_file.assert_called_once_with(Path("/path/to/document.pdf"), "rb")

    def test_from_bytes(self):
        """Test creating FileContent from bytes."""
        data = b"fake pdf data"
        content = FileContent.from_bytes(data, "application/pdf")

        assert content.data == data
        assert content.mime_type == "application/pdf"

    def test_to_litellm_format_url(self):
        """Test conversion to LiteLLM format with URL."""
        content = FileContent.from_url("https://example.com/document.pdf")
        result = content.to_litellm_format()

        assert result == {"type": "file", "file": {"url": "https://example.com/document.pdf"}}

    def test_to_litellm_format_base64(self):
        """Test conversion to LiteLLM format with base64 data."""
        data = b"fake pdf data"
        content = FileContent.from_bytes(data, "application/pdf")
        result = content.to_litellm_format()

        expected_b64 = base64.standard_b64encode(data).decode("utf-8")
        assert result == {
            "type": "image_url",
            "image_url": {"url": f"data:application/pdf;base64,{expected_b64}"},
        }


class TestMessage:
    """Test Message class."""

    def test_creation_with_string(self):
        """Test Message creation with string content."""
        msg = Message(role="user", content="Hello!")

        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_creation_with_content_list(self):
        """Test Message creation with list of content parts."""
        msg = Message(
            role="user",
            content=[TextContent("Hello!"), ImageContent.from_url("https://example.com/image.jpg")],
        )

        assert msg.role == "user"
        assert isinstance(msg.content, list)
        assert len(msg.content) == 2

    def test_to_litellm_format_string(self):
        """Test conversion to LiteLLM format with string content."""
        msg = Message(role="user", content="Hello!")
        result = msg.to_litellm_format()

        assert result == {"role": "user", "content": "Hello!"}

    def test_to_litellm_format_mixed_content(self):
        """Test conversion to LiteLLM format with mixed content."""
        msg = Message(
            role="user",
            content=[
                TextContent("Describe this:"),
                ImageContent.from_url("https://example.com/image.jpg"),
                "What do you see?",
            ],
        )
        result = msg.to_litellm_format()

        assert result["role"] == "user"
        assert isinstance(result["content"], list)
        assert len(result["content"]) == 3
        assert result["content"][0] == {"type": "text", "text": "Describe this:"}
        assert result["content"][1]["type"] == "image_url"
        assert result["content"][2] == {"type": "text", "text": "What do you see?"}

    def test_to_litellm_format_unsupported_type(self):
        """Test that unsupported content types raise TypeError."""
        msg = Message(role="user", content=[123])  # Invalid type

        with pytest.raises(TypeError, match="Unsupported content part type"):
            msg.to_litellm_format()
