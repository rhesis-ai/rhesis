import os
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from rhesis.sdk.models.providers.openrouter import (
    DEFAULT_MODEL_NAME,
    OpenRouterLLM,
)


def test_openrouter_defaults():
    assert OpenRouterLLM.PROVIDER == "openrouter"
    assert DEFAULT_MODEL_NAME is not None
    assert DEFAULT_MODEL_NAME != ""


class TestOpenRouterLLM:
    def test_init_with_api_key(self):
        """Test initialization with explicit API key"""
        api_key = "test_api_key"
        llm = OpenRouterLLM(api_key=api_key)
        assert llm.api_key == api_key
        assert llm.model_name == OpenRouterLLM.PROVIDER + "/" + DEFAULT_MODEL_NAME

    def test_init_with_env_api_key(self):
        """Test initialization with environment variable API key"""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "env_api_key"}):
            llm = OpenRouterLLM()
            assert llm.api_key == "env_api_key"

    def test_init_without_api_key_raises_error(self):
        """Test initialization without API key raises ValueError"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY is not set"):
                OpenRouterLLM()

    def test_init_with_custom_model(self):
        """Test initialization with custom model name"""
        custom_model = "anthropic/claude-3.5-sonnet"
        llm = OpenRouterLLM(model_name=custom_model, api_key="test_key")
        assert llm.model_name == OpenRouterLLM.PROVIDER + "/" + custom_model

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_without_schema(self, mock_completion):
        """Test generate method without schema returns string response"""
        # Mock the completion response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello, this is a test response"
        mock_completion.return_value = mock_response

        llm = OpenRouterLLM(api_key="test_key")
        prompt = "Hello, how are you?"

        result = llm.generate(prompt)

        assert result == "Hello, this is a test response"
        mock_completion.assert_called_once_with(
            model=f"openrouter/{DEFAULT_MODEL_NAME}",
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

        llm = OpenRouterLLM(api_key="test_key")
        prompt = "Generate a person's information"

        result = llm.generate(prompt, schema=TestSchema)

        assert isinstance(result, dict)
        assert result["name"] == "John"
        assert result["age"] == 30
        assert result["city"] == "New York"

        mock_completion.assert_called_once_with(
            model=f"openrouter/{DEFAULT_MODEL_NAME}",
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

        llm = OpenRouterLLM(api_key="test_key")
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

        llm = OpenRouterLLM(api_key="test_key")
        prompt = "Test prompt"

        llm.generate(prompt, temperature=0.7, max_tokens=100)

        mock_completion.assert_called_once_with(
            model=f"openrouter/{DEFAULT_MODEL_NAME}",
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

        custom_model = "meta-llama/llama-3.1-8b-instruct"
        llm = OpenRouterLLM(model_name=custom_model, api_key="test_key")
        prompt = "Test prompt"

        llm.generate(prompt)

        mock_completion.assert_called_once_with(
            model=f"openrouter/{custom_model}",
            messages=[{"role": "user", "content": prompt}],
            response_format=None,
            api_key="test_key",
        )

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_system_prompt(self, mock_completion):
        """Test generate method with system prompt"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_completion.return_value = mock_response

        llm = OpenRouterLLM(api_key="test_key")
        prompt = "Test prompt"
        system_prompt = "You are a helpful assistant"

        llm.generate(prompt, system_prompt=system_prompt)

        mock_completion.assert_called_once_with(
            model=f"openrouter/{DEFAULT_MODEL_NAME}",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format=None,
            api_key="test_key",
        )
