import os
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from rhesis.sdk.models.providers.polyphemus import (
    DEFAULT_POLYPHEMUS_URL,
    PolyphemusLLM,
)


def test_polyphemus_defaults():
    """Test default constants"""
    assert DEFAULT_POLYPHEMUS_URL == "https://polyphemus.rhesis.ai"


class TestPolyphemusLLM:
    def test_init_with_api_key(self):
        """Test initialization with explicit API key"""
        api_key = "test_api_key"
        llm = PolyphemusLLM(api_key=api_key)
        assert llm.api_key == api_key
        assert llm.base_url == DEFAULT_POLYPHEMUS_URL
        assert llm.model_name == ""

    def test_init_with_env_api_key(self):
        """Test initialization with environment variable API key"""
        with patch.dict(os.environ, {"RHESIS_API_KEY": "env_api_key"}, clear=True):
            llm = PolyphemusLLM()
            assert llm.api_key == "env_api_key"

    def test_init_without_api_key_raises_error(self):
        """Test initialization without API key raises ValueError"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="RHESIS_API_KEY is not set"):
                PolyphemusLLM()

    def test_init_with_custom_model(self):
        """Test initialization with custom model name"""
        custom_model = "meta-llama/Llama-3.1-8B-Instruct"
        llm = PolyphemusLLM(model_name=custom_model, api_key="test_key")
        assert llm.model_name == custom_model

    def test_init_with_custom_base_url(self):
        """Test initialization with custom base URL"""
        custom_url = "https://custom.polyphemus.url"
        llm = PolyphemusLLM(api_key="test_key", base_url=custom_url)
        assert llm.base_url == custom_url

    def test_load_model_sets_headers(self):
        """Test that load_model sets the correct headers"""
        api_key = "test_api_key"
        llm = PolyphemusLLM(api_key=api_key)

        assert hasattr(llm, "headers")
        assert llm.headers["Authorization"] == f"Bearer {api_key}"
        assert llm.headers["Content-Type"] == "application/json"
        assert llm.headers["accept"] == "application/json"

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_without_schema(self, mock_post):
        """Test generate method without schema returns string response"""
        # Mock the API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello, this is a test response"}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        prompt = "Hello, how are you?"

        result = llm.generate(prompt)

        assert result == "Hello, this is a test response"
        mock_post.assert_called_once()

        # Verify the request structure
        call_args = mock_post.call_args
        assert call_args.kwargs["json"]["messages"] == [{"role": "user", "content": prompt}]
        assert call_args.kwargs["json"]["temperature"] == 0.7
        assert call_args.kwargs["json"]["max_tokens"] == 512

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_with_system_prompt(self, mock_post):
        """Test generate method with system prompt includes both messages"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        prompt = "What is 2+2?"
        system_prompt = "You are a helpful assistant."

        result = llm.generate(prompt, system_prompt=system_prompt)

        assert result == "Test response"

        # Verify messages include system prompt
        call_args = mock_post.call_args
        messages = call_args.kwargs["json"]["messages"]
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": system_prompt}
        assert messages[1] == {"role": "user", "content": prompt}

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_with_schema(self, mock_post):
        """Test generate method with schema returns validated dict response"""

        # Define a test schema
        class TestSchema(BaseModel):
            name: str
            age: int
            city: str

        # Mock the API response with JSON string
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": '{"name": "John", "age": 30, "city": "New York"}'}}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        prompt = "Generate a person's information"

        result = llm.generate(prompt, schema=TestSchema)

        assert isinstance(result, dict)
        assert result["name"] == "John"
        assert result["age"] == 30
        assert result["city"] == "New York"

        # Verify that schema instructions were added to the prompt
        call_args = mock_post.call_args
        user_message = call_args.kwargs["json"]["messages"][0]["content"]
        assert "JSON matching this schema" in user_message
        assert prompt in user_message

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_with_schema_invalid_response(self, mock_post):
        """Test generate method with schema raises error for invalid response"""

        # Define a test schema
        class TestSchema(BaseModel):
            name: str
            age: int

        # Mock the API response with invalid JSON (missing age field)
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"name": "John"}'}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        prompt = "Generate a person's information"

        with pytest.raises(Exception):  # Should raise validation error
            llm.generate(prompt, schema=TestSchema)

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_with_additional_kwargs(self, mock_post):
        """Test generate method passes additional kwargs to create_completion"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        prompt = "Test prompt"

        llm.generate(prompt, temperature=0.9, max_tokens=1000, top_p=0.95)

        call_args = mock_post.call_args
        request_data = call_args.kwargs["json"]
        assert request_data["temperature"] == 0.9
        assert request_data["max_tokens"] == 1000
        assert request_data["top_p"] == 0.95

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_with_custom_model(self, mock_post):
        """Test generate method uses custom model name"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        custom_model = "meta-llama/Llama-3.1-70B-Instruct"
        llm = PolyphemusLLM(model_name=custom_model, api_key="test_key")
        prompt = "Test prompt"

        llm.generate(prompt)

        call_args = mock_post.call_args
        assert call_args.kwargs["json"]["model"] == custom_model

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_without_model_name(self, mock_post):
        """Test generate method without model name doesn't include model in request"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")  # No model_name specified
        prompt = "Test prompt"

        llm.generate(prompt)

        call_args = mock_post.call_args
        assert "model" not in call_args.kwargs["json"]

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_strip_reasoning_tokens(self, mock_post):
        """Test that reasoning tokens are stripped by default"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "<think>This is reasoning</think>The actual response"
                    }
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        prompt = "Test prompt"

        result = llm.generate(prompt, include_reasoning=False)

        assert result == "The actual response"
        assert "<think>" not in result

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_include_reasoning_tokens(self, mock_post):
        """Test that reasoning tokens are included when requested"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "<think>This is reasoning</think>The actual response"
                    }
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        prompt = "Test prompt"

        result = llm.generate(prompt, include_reasoning=True)

        assert result == "<think>This is reasoning</think>The actual response"
        assert "<think>" in result

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_strip_reasoning_multiline(self, mock_post):
        """Test that multiline reasoning tokens are stripped correctly"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "<think>\nMultiline\nreasoning\nhere\n</think>Final answer"
                    }
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        prompt = "Test prompt"

        result = llm.generate(prompt, include_reasoning=False)

        assert result == "Final answer"
        assert "<think>" not in result
        assert "reasoning" not in result

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_strip_reasoning_case_insensitive(self, mock_post):
        """Test that reasoning tokens are stripped case-insensitively"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "<THINK>Uppercase reasoning</THINK>Response"
                    }
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        prompt = "Test prompt"

        result = llm.generate(prompt, include_reasoning=False)

        assert result == "Response"
        assert "<THINK>" not in result

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_http_error(self, mock_post):
        """Test generate handles HTTP errors gracefully"""
        import requests

        mock_post.side_effect = requests.exceptions.HTTPError("API Error")

        llm = PolyphemusLLM(api_key="test_key")
        prompt = "Test prompt"

        result = llm.generate(prompt)

        assert result == "An error occurred while processing the request."

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_http_error_with_schema(self, mock_post):
        """Test generate handles HTTP errors gracefully with schema"""
        import requests

        class TestSchema(BaseModel):
            value: str

        mock_post.side_effect = requests.exceptions.HTTPError("API Error")

        llm = PolyphemusLLM(api_key="test_key")
        prompt = "Test prompt"

        result = llm.generate(prompt, schema=TestSchema)

        assert isinstance(result, dict)
        assert result == {"error": "An error occurred while processing the request."}

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_no_choices(self, mock_post):
        """Test generate handles response with no choices"""
        mock_response = Mock()
        mock_response.json.return_value = {"choices": []}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        prompt = "Test prompt"

        result = llm.generate(prompt)

        assert result == "No response generated."

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_create_completion_default_params(self, mock_post):
        """Test create_completion uses default parameters"""
        mock_response = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test"}}]}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        llm.create_completion(messages=messages)

        call_args = mock_post.call_args
        request_data = call_args.kwargs["json"]

        # Check default values
        assert request_data["temperature"] == 0.7
        assert request_data["max_tokens"] == 512
        assert request_data["stream"] is False
        assert request_data["repetition_penalty"] == 1.2
        assert request_data["top_p"] == 0
        assert request_data["top_k"] == 0

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_create_completion_custom_params(self, mock_post):
        """Test create_completion with custom parameters"""
        mock_response = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test"}}]}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        llm.create_completion(
            messages=messages,
            temperature=0.5,
            max_tokens=1024,
            stream=True,
            repetition_penalty=1.5,
            top_p=0.9,
            top_k=50,
        )

        call_args = mock_post.call_args
        request_data = call_args.kwargs["json"]

        assert request_data["temperature"] == 0.5
        assert request_data["max_tokens"] == 1024
        assert request_data["stream"] is True
        assert request_data["repetition_penalty"] == 1.5
        assert request_data["top_p"] == 0.9
        assert request_data["top_k"] == 50

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_create_completion_uses_correct_url(self, mock_post):
        """Test create_completion uses the correct API endpoint"""
        mock_response = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test"}}]}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        custom_url = "https://custom.url"
        llm = PolyphemusLLM(api_key="test_key", base_url=custom_url)
        messages = [{"role": "user", "content": "Test"}]

        llm.create_completion(messages=messages)

        call_args = mock_post.call_args
        assert call_args.args[0] == f"{custom_url}/generate"

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_create_completion_includes_headers(self, mock_post):
        """Test create_completion includes authorization headers"""
        mock_response = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test"}}]}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        api_key = "test_key"
        llm = PolyphemusLLM(api_key=api_key)
        messages = [{"role": "user", "content": "Test"}]

        llm.create_completion(messages=messages)

        call_args = mock_post.call_args
        headers = call_args.kwargs["headers"]

        assert headers["Authorization"] == f"Bearer {api_key}"
        assert headers["Content-Type"] == "application/json"
        assert headers["accept"] == "application/json"
