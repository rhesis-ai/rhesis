import os
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from rhesis.sdk.models.providers.gemini import (
    DEFAULT_MODEL_NAME,
    GeminiLLM,
)


def test_gemini_defaults():
    assert GeminiLLM.PROVIDER == "gemini"
    assert DEFAULT_MODEL_NAME is not None
    assert DEFAULT_MODEL_NAME != ""


class TestGeminiLLM:
    def test_init_with_api_key(self):
        """Test initialization with explicit API key"""
        api_key = "test_api_key"
        llm = GeminiLLM(api_key=api_key)
        assert llm.api_key == api_key
        assert llm.model_name == GeminiLLM.PROVIDER + "/" + DEFAULT_MODEL_NAME

    def test_init_with_env_api_key(self):
        """Test initialization with environment variable API key"""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env_api_key"}, clear=True):
            llm = GeminiLLM()
            assert llm.api_key == "env_api_key"

    def test_init_with_google_api_key(self):
        """Test initialization with GOOGLE_API_KEY environment variable"""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "google_api_key"}, clear=True):
            llm = GeminiLLM()
            assert llm.api_key == "google_api_key"

    def test_init_without_api_key_raises_error(self):
        """Test initialization without API key raises ValueError"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="GEMINI_API_KEY or GOOGLE_API_KEY is not set"):
                GeminiLLM()

    def test_init_with_custom_model(self):
        """Test initialization with custom model name"""
        custom_model = "gemini-pro"
        llm = GeminiLLM(model_name=custom_model, api_key="test_key")
        assert llm.model_name == GeminiLLM.PROVIDER + "/" + custom_model

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_without_schema(self, mock_completion):
        """Test generate method without schema returns string response"""
        # Mock the completion response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello, this is a test response"
        mock_completion.return_value = mock_response

        llm = GeminiLLM(api_key="test_key")
        prompt = "Hello, how are you?"

        result = llm.generate(prompt)

        assert result == "Hello, this is a test response"
        mock_completion.assert_called_once_with(
            model=f"gemini/{DEFAULT_MODEL_NAME}",
            messages=[{"role": "user", "content": prompt}],
            response_format=None,
            api_key="test_key",
        )

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_schema(self, mock_completion):
        """Test generate method with schema returns validated dict response"""

        # Define a test schema
        class TestSchema(BaseModel):
            name: str
            age: int
            city: str

        # Mock the completion response with JSON string
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"name": "John", "age": 30, "city": "New York"}'
        mock_completion.return_value = mock_response

        llm = GeminiLLM(api_key="test_key")
        prompt = "Generate a person's information"

        result = llm.generate(prompt, schema=TestSchema)

        assert isinstance(result, dict)
        assert result["name"] == "John"
        assert result["age"] == 30
        assert result["city"] == "New York"

        mock_completion.assert_called_once_with(
            model=f"gemini/{DEFAULT_MODEL_NAME}",
            messages=[{"role": "user", "content": prompt}],
            response_format=TestSchema,
            api_key="test_key",
        )

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_schema_invalid_response(self, mock_completion):
        """Test generate method with schema raises error for invalid response"""

        # Define a test schema
        class TestSchema(BaseModel):
            name: str
            age: int

        # Mock the completion response with invalid JSON
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"name": "John"}'  # Missing age field
        mock_completion.return_value = mock_response

        llm = GeminiLLM(api_key="test_key")
        prompt = "Generate a person's information"

        with pytest.raises(Exception):  # Should raise validation error
            llm.generate(prompt, schema=TestSchema)

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_additional_kwargs(self, mock_completion):
        """Test generate method passes additional kwargs to completion"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_completion.return_value = mock_response

        llm = GeminiLLM(api_key="test_key")
        prompt = "Test prompt"

        llm.generate(prompt, temperature=0.7, max_tokens=100)

        mock_completion.assert_called_once_with(
            model=f"gemini/{DEFAULT_MODEL_NAME}",
            messages=[{"role": "user", "content": prompt}],
            response_format=None,
            api_key="test_key",
            temperature=0.7,
            max_tokens=100,
        )

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_custom_model(self, mock_completion):
        """Test generate method uses custom model name"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_completion.return_value = mock_response

        custom_model = "gemini-pro"
        llm = GeminiLLM(model_name=custom_model, api_key="test_key")
        prompt = "Test prompt"

        llm.generate(prompt)

        mock_completion.assert_called_once_with(
            model=f"gemini/{custom_model}",
            messages=[{"role": "user", "content": prompt}],
            response_format=None,
            api_key="test_key",
        )

    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_supports_vision_property(self, mock_audio, mock_vision):
        """Test supports_vision property returns correct value"""
        mock_vision.return_value = True
        mock_audio.return_value = False

        llm = GeminiLLM(api_key="test_key")

        assert llm.supports_vision is True
        mock_vision.assert_called_with(model=f"gemini/{DEFAULT_MODEL_NAME}")

    @patch("rhesis.sdk.models.providers.litellm.completion")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_generate_multimodal_with_image(self, mock_audio, mock_vision, mock_completion):
        """Test generate_multimodal method with image content"""
        from rhesis.sdk.models.content import ImageContent, Message, TextContent

        mock_vision.return_value = True
        mock_audio.return_value = False
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "I see a cat"
        mock_completion.return_value = mock_response

        llm = GeminiLLM(api_key="test_key")
        messages = [
            Message(
                role="user",
                content=[
                    TextContent("Describe this:"),
                    ImageContent.from_url("https://example.com/cat.jpg"),
                ],
            )
        ]

        result = llm.generate_multimodal(messages)

        assert result == "I see a cat"
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == f"gemini/{DEFAULT_MODEL_NAME}"
        assert len(call_kwargs["messages"]) == 1
        assert len(call_kwargs["messages"][0]["content"]) == 2

    @patch("rhesis.sdk.models.providers.litellm.completion")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_vision")
    @patch("rhesis.sdk.models.capabilities.litellm.supports_audio_input")
    def test_analyze_content(self, mock_audio, mock_vision, mock_completion):
        """Test analyze_content convenience method"""
        from rhesis.sdk.models.content import ImageContent

        mock_vision.return_value = True
        mock_audio.return_value = False
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "A beautiful sunset"
        mock_completion.return_value = mock_response

        llm = GeminiLLM(api_key="test_key")
        result = llm.analyze_content(
            ImageContent.from_url("https://example.com/sunset.jpg"), "Describe this image"
        )

        assert result == "A beautiful sunset"
        mock_completion.assert_called_once()
