"""Tests for multimodal generation functionality."""

from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from rhesis.sdk.models.content import (
    AudioContent,
    FileContent,
    ImageContent,
    Message,
    TextContent,
    VideoContent,
)
from rhesis.sdk.models.providers.litellm import LiteLLM


class TestLiteLLMMultimodal:
    """Test multimodal generation in LiteLLM."""
    
    @patch("rhesis.sdk.models.providers.litellm.completion")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_generate_multimodal_text_only(self, mock_audio, mock_vision, mock_completion):
        """Test generate_multimodal with text-only messages."""
        mock_vision.return_value = True
        mock_audio.return_value = False
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_completion.return_value = mock_response
        
        llm = LiteLLM(model_name="gemini/gemini-2.0-flash", api_key="test_key")
        messages = [Message(role="user", content="Hello!")]
        
        result = llm.generate_multimodal(messages)
        
        assert result == "Test response"
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "gemini/gemini-2.0-flash"
        assert call_kwargs["messages"] == [{"role": "user", "content": "Hello!"}]
    
    @patch("rhesis.sdk.models.providers.litellm.completion")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_generate_multimodal_with_image_url(self, mock_audio, mock_vision, mock_completion):
        """Test generate_multimodal with image URL content."""
        mock_vision.return_value = True
        mock_audio.return_value = False
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "I see a cat"
        mock_completion.return_value = mock_response
        
        llm = LiteLLM(model_name="gemini/gemini-2.0-flash", api_key="test_key")
        messages = [
            Message(role="user", content=[
                TextContent("Describe this image:"),
                ImageContent.from_url("https://example.com/cat.jpg")
            ])
        ]
        
        result = llm.generate_multimodal(messages)
        
        assert result == "I see a cat"
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args[1]
        assert len(call_kwargs["messages"]) == 1
        assert len(call_kwargs["messages"][0]["content"]) == 2
    
    @patch("rhesis.sdk.models.providers.litellm.completion")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_generate_multimodal_with_base64_image(self, mock_audio, mock_vision, mock_completion):
        """Test generate_multimodal with base64 image content."""
        mock_vision.return_value = True
        mock_audio.return_value = False
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "I see a dog"
        mock_completion.return_value = mock_response
        
        llm = LiteLLM(model_name="gemini/gemini-2.0-flash", api_key="test_key")
        messages = [
            Message(role="user", content=[
                ImageContent.from_bytes(b"fake image data", "image/jpeg"),
                TextContent("What is this?")
            ])
        ]
        
        result = llm.generate_multimodal(messages)
        
        assert result == "I see a dog"
        mock_completion.assert_called_once()
    
    @patch("rhesis.sdk.models.providers.litellm.completion")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_generate_multimodal_multiple_images(self, mock_audio, mock_vision, mock_completion):
        """Test generate_multimodal with multiple images."""
        mock_vision.return_value = True
        mock_audio.return_value = False
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Both are animals"
        mock_completion.return_value = mock_response
        
        llm = LiteLLM(model_name="gemini/gemini-2.0-flash", api_key="test_key")
        messages = [
            Message(role="user", content=[
                TextContent("Compare these images:"),
                ImageContent.from_url("https://example.com/cat.jpg"),
                ImageContent.from_url("https://example.com/dog.jpg"),
                TextContent("What are the differences?")
            ])
        ]
        
        result = llm.generate_multimodal(messages)
        
        assert result == "Both are animals"
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args[1]
        assert len(call_kwargs["messages"][0]["content"]) == 4
    
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_generate_multimodal_raises_error_no_vision_support(self, mock_audio, mock_vision):
        """Test that generate_multimodal raises error when model lacks vision support."""
        mock_vision.return_value = False
        mock_audio.return_value = False
        
        llm = LiteLLM(model_name="gpt-3.5-turbo", api_key="test_key")
        messages = [
            Message(role="user", content=[
                ImageContent.from_url("https://example.com/image.jpg"),
                TextContent("Describe this")
            ])
        ]
        
        with pytest.raises(ValueError, match="does not support vision/image inputs"):
            llm.generate_multimodal(messages)
    
    @patch("rhesis.sdk.models.providers.litellm.completion")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_generate_multimodal_with_audio(self, mock_audio, mock_vision, mock_completion):
        """Test generate_multimodal with audio content."""
        mock_vision.return_value = True
        mock_audio.return_value = True  # Model supports audio
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "I hear music"
        mock_completion.return_value = mock_response
        
        llm = LiteLLM(model_name="gemini/gemini-1.5-pro", api_key="test_key")
        messages = [
            Message(role="user", content=[
                AudioContent.from_url("https://example.com/audio.mp3"),
                TextContent("What is in this audio?")
            ])
        ]
        
        result = llm.generate_multimodal(messages)
        
        assert result == "I hear music"
    
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_generate_multimodal_raises_error_no_audio_support(self, mock_audio, mock_vision):
        """Test that generate_multimodal raises error when model lacks audio support."""
        mock_vision.return_value = True
        mock_audio.return_value = False
        
        llm = LiteLLM(model_name="gpt-4o", api_key="test_key")
        messages = [
            Message(role="user", content=[
                AudioContent.from_url("https://example.com/audio.mp3"),
                TextContent("Transcribe this")
            ])
        ]
        
        with pytest.raises(ValueError, match="does not support audio inputs"):
            llm.generate_multimodal(messages)
    
    @patch("rhesis.sdk.models.providers.litellm.completion")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_generate_multimodal_with_video(self, mock_audio, mock_vision, mock_completion):
        """Test generate_multimodal with video content."""
        mock_vision.return_value = True
        mock_audio.return_value = False
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "I see a video"
        mock_completion.return_value = mock_response
        
        llm = LiteLLM(model_name="gemini/gemini-1.5-pro", api_key="test_key")
        messages = [
            Message(role="user", content=[
                VideoContent.from_url("https://example.com/video.mp4"),
                TextContent("What happens in this video?")
            ])
        ]
        
        result = llm.generate_multimodal(messages)
        
        assert result == "I see a video"
    
    @patch("rhesis.sdk.models.providers.litellm.completion")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_generate_multimodal_with_file(self, mock_audio, mock_vision, mock_completion):
        """Test generate_multimodal with file/PDF content."""
        mock_vision.return_value = True
        mock_audio.return_value = True
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This is a contract"
        mock_completion.return_value = mock_response
        
        llm = LiteLLM(model_name="gemini/gemini-2.0-flash", api_key="test_key")
        messages = [
            Message(role="user", content=[
                FileContent.from_url("https://example.com/document.pdf"),
                TextContent("Summarize this document")
            ])
        ]
        
        result = llm.generate_multimodal(messages)
        
        assert result == "This is a contract"
    
    @patch("rhesis.sdk.models.providers.litellm.completion")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_generate_multimodal_mixed_content(self, mock_audio, mock_vision, mock_completion):
        """Test generate_multimodal with mixed content types."""
        mock_vision.return_value = True
        mock_audio.return_value = True  # Model supports audio for mixed content
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Complex response"
        mock_completion.return_value = mock_response
        
        llm = LiteLLM(model_name="gemini/gemini-1.5-pro", api_key="test_key")
        messages = [
            Message(role="user", content=[
                TextContent("Analyze these:"),
                ImageContent.from_url("https://example.com/image.jpg"),
                AudioContent.from_url("https://example.com/audio.mp3"),
                TextContent("What do you notice?")
            ])
        ]
        
        result = llm.generate_multimodal(messages)
        
        assert result == "Complex response"
    
    @patch("rhesis.sdk.models.providers.litellm.completion")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_generate_multimodal_with_schema(self, mock_audio, mock_vision, mock_completion):
        """Test generate_multimodal with schema returns validated dict."""
        mock_vision.return_value = True
        mock_audio.return_value = False
        
        class ImageAnalysis(BaseModel):
            objects: list[str]
            description: str
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"objects": ["cat", "dog"], "description": "Animals"}'
        mock_completion.return_value = mock_response
        
        llm = LiteLLM(model_name="gemini/gemini-2.0-flash", api_key="test_key")
        messages = [
            Message(role="user", content=[
                ImageContent.from_url("https://example.com/image.jpg"),
                TextContent("Analyze this image")
            ])
        ]
        
        result = llm.generate_multimodal(messages, schema=ImageAnalysis)
        
        assert isinstance(result, dict)
        assert result["objects"] == ["cat", "dog"]
        assert result["description"] == "Animals"


class TestAnalyzeContent:
    """Test analyze_content convenience method."""
    
    @patch("rhesis.sdk.models.providers.litellm.completion")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_analyze_content_single_image(self, mock_audio, mock_vision, mock_completion):
        """Test analyze_content with single image."""
        mock_vision.return_value = True
        mock_audio.return_value = False
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "A beautiful sunset"
        mock_completion.return_value = mock_response
        
        llm = LiteLLM(model_name="gemini/gemini-2.0-flash", api_key="test_key")
        result = llm.analyze_content(
            ImageContent.from_url("https://example.com/sunset.jpg"),
            "Describe this image"
        )
        
        assert result == "A beautiful sunset"
    
    @patch("rhesis.sdk.models.providers.litellm.completion")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_analyze_content_multiple_parts(self, mock_audio, mock_vision, mock_completion):
        """Test analyze_content with multiple content parts."""
        mock_vision.return_value = True
        mock_audio.return_value = False
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Both show nature"
        mock_completion.return_value = mock_response
        
        llm = LiteLLM(model_name="gemini/gemini-2.0-flash", api_key="test_key")
        result = llm.analyze_content(
            [
                ImageContent.from_url("https://example.com/image1.jpg"),
                ImageContent.from_url("https://example.com/image2.jpg")
            ],
            "Compare these images"
        )
        
        assert result == "Both show nature"
    
    @patch("rhesis.sdk.models.providers.litellm.completion")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_analyze_content_with_system_prompt(self, mock_audio, mock_vision, mock_completion):
        """Test analyze_content with system prompt."""
        mock_vision.return_value = True
        mock_audio.return_value = False
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Professional analysis"
        mock_completion.return_value = mock_response
        
        llm = LiteLLM(model_name="gemini/gemini-2.0-flash", api_key="test_key")
        result = llm.analyze_content(
            ImageContent.from_url("https://example.com/image.jpg"),
            "Analyze this",
            system_prompt="You are an expert analyst"
        )
        
        assert result == "Professional analysis"
        call_kwargs = mock_completion.call_args[1]
        # Should have system message + user message
        assert len(call_kwargs["messages"]) == 2
        assert call_kwargs["messages"][0]["role"] == "system"
    
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_analyze_content_raises_error_unsupported_model(self, mock_audio, mock_vision):
        """Test that analyze_content raises error for unsupported model."""
        mock_vision.return_value = False
        mock_audio.return_value = False
        
        llm = LiteLLM(model_name="gpt-3.5-turbo", api_key="test_key")
        
        with pytest.raises(ValueError, match="does not support vision"):
            llm.analyze_content(
                ImageContent.from_url("https://example.com/image.jpg"),
                "Describe this"
            )

