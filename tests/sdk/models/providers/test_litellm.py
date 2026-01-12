from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from rhesis.sdk.models import LiteLLM


class TestLiteLLM:
    def test_init_without_api_key(self):
        model_name = "provider/model"
        llm = LiteLLM(model_name)
        assert llm.model_name == model_name
        assert llm.api_key is None

    def test_init_with_api_key(self):
        api_key = "test_api_key"
        model_name = "provider/model"
        llm = LiteLLM(model_name, api_key=api_key)
        assert llm.model_name == model_name
        assert llm.api_key == api_key

    def test_init_without_name(self):
        with pytest.raises(ValueError):
            LiteLLM(None)

    def test_init_with_empty_string(self):
        with pytest.raises(ValueError):
            LiteLLM("")

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_without_schema_without_api_key(self, mock_completion):
        """Test generate method without schema returns string response"""
        # Mock the completion response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello, this is a test response"
        mock_completion.return_value = mock_response

        model_name = "provider/model"
        llm = LiteLLM(model_name)
        prompt = "Hello, how are you?"

        result = llm.generate(prompt)

        assert result == "Hello, this is a test response"
        mock_completion.assert_called_once_with(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format=None,
            api_key=None,
        )

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_without_schema_with_api_key(self, mock_completion):
        """Test generate method without schema returns string response"""
        # Mock the completion response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello, this is a test response"
        mock_completion.return_value = mock_response

        model_name = "provider/model"
        api_key = "test_api_key"
        llm = LiteLLM(model_name, api_key=api_key)
        prompt = "Hello, how are you?"

        result = llm.generate(prompt)

        assert result == "Hello, this is a test response"
        mock_completion.assert_called_once_with(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format=None,
            api_key=api_key,
        )

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_schema_without_api_key(self, mock_completion):
        """Test generate method with schema returns validated dict response"""

        # Define a test schema
        class TestSchema(BaseModel):
            name: str
            age: int
            city: str

        # Mock the completion response with JSON string
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[
            0
        ].message.content = '{"name": "John", "age": 30, "city": "New York"}'
        mock_completion.return_value = mock_response

        model_name = "provider/model"
        llm = LiteLLM(model_name=model_name)
        prompt = "Generate a person's information"

        result = llm.generate(prompt, schema=TestSchema)

        assert isinstance(result, dict)
        assert result["name"] == "John"
        assert result["age"] == 30
        assert result["city"] == "New York"

        mock_completion.assert_called_once_with(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format=TestSchema,
            api_key=None,
        )

    @patch("rhesis.sdk.models.providers.litellm.completion")
    def test_generate_with_schema_with_api_key(self, mock_completion):
        """Test generate method with schema returns validated dict response"""

        # Define a test schema
        class TestSchema(BaseModel):
            name: str
            age: int
            city: str

        # Mock the completion response with JSON string
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[
            0
        ].message.content = '{"name": "John", "age": 30, "city": "New York"}'
        mock_completion.return_value = mock_response

        model_name = "provider/model"
        api_key = "test_api_key"
        llm = LiteLLM(model_name=model_name, api_key=api_key)
        prompt = "Generate a person's information"

        result = llm.generate(prompt, schema=TestSchema)

        assert isinstance(result, dict)
        assert result["name"] == "John"
        assert result["age"] == 30
        assert result["city"] == "New York"

        mock_completion.assert_called_once_with(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format=TestSchema,
            api_key=api_key,
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
        mock_response.choices[
            0
        ].message.content = '{"name": "John"}'  # Missing age field
        mock_completion.return_value = mock_response

        model_name = "provider/model"
        llm = LiteLLM(model_name=model_name)
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

        model_name = "provider/model"
        llm = LiteLLM(model_name=model_name)
        prompt = "Test prompt"

        llm.generate(prompt, temperature=0.7, max_tokens=100)

        mock_completion.assert_called_once_with(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format=None,
            api_key=None,
            temperature=0.7,
            max_tokens=100,
        )
