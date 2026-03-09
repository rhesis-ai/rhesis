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

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_with_system_prompt(self, mock_post):
        """Test generate method with system prompt includes both messages"""
        mock_response = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test response"}}]}
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
            "choices": [{"message": {"content": '{"name": "John", "age": 30, "city": "New York"}'}}]
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

        # Verify that schema instructions were added to system prompt
        call_args = mock_post.call_args
        messages = call_args.kwargs["json"]["messages"]
        assert len(messages) == 2

        # System message should contain /no_think and schema instructions
        system_message = messages[0]["content"]
        assert messages[0]["role"] == "system"
        assert "/no_think" in system_message
        assert "JSON matching this schema" in system_message

        # User message should contain the original prompt
        user_message = messages[1]["content"]
        assert messages[1]["role"] == "user"
        assert user_message == prompt

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
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test response"}}]}
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
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test response"}}]}
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
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test response"}}]}
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
                {"message": {"content": "<think>This is reasoning</think>The actual response"}}
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
                {"message": {"content": "<think>This is reasoning</think>The actual response"}}
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
            "choices": [{"message": {"content": "<THINK>Uppercase reasoning</THINK>Response"}}]
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
    def test_create_completion_without_params(self, mock_post):
        """Test create_completion without extra parameters only includes messages"""
        mock_response = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test"}}]}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        llm.create_completion(messages=messages)

        call_args = mock_post.call_args
        request_data = call_args.kwargs["json"]

        # Check that only messages are included when no params passed
        assert "messages" in request_data
        assert request_data["messages"] == messages
        # Default values should not be included unless explicitly passed
        assert "temperature" not in request_data
        assert "max_tokens" not in request_data
        assert "stream" not in request_data
        assert "repetition_penalty" not in request_data
        assert "top_p" not in request_data
        assert "top_k" not in request_data

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


class TestGenerateBatch:
    def _make_batch_response(self, contents):
        """Build a mock batch API response from a list of content strings."""
        return {
            "responses": [
                {"choices": [{"message": {"content": c}}], "model": "polyphemus-default"}
                for c in contents
            ]
        }

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_empty_prompts(self, mock_post):
        """generate_batch returns [] immediately for an empty prompt list."""
        llm = PolyphemusLLM(api_key="test_key")
        result = llm.generate_batch([])
        assert result == []
        mock_post.assert_not_called()

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_returns_strings_without_schema(self, mock_post):
        """generate_batch returns a list of strings when no schema is given."""
        mock_response = Mock()
        mock_response.json.return_value = self._make_batch_response(["Answer 1", "Answer 2"])
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        results = llm.generate_batch(["Prompt 1", "Prompt 2"])

        assert results == ["Answer 1", "Answer 2"]

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_preserves_order(self, mock_post):
        """Results are returned in the same order as the input prompts."""
        mock_response = Mock()
        mock_response.json.return_value = self._make_batch_response(["First", "Second", "Third"])
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        results = llm.generate_batch(["P1", "P2", "P3"])

        assert results == ["First", "Second", "Third"]

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_with_system_prompt(self, mock_post):
        """generate_batch includes a shared system message in every sub-request."""
        mock_response = Mock()
        mock_response.json.return_value = self._make_batch_response(["R1", "R2"])
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        llm.generate_batch(["P1", "P2"], system_prompt="You are helpful.")

        call_args = mock_post.call_args
        sent_requests = call_args.kwargs["json"]["requests"]
        assert len(sent_requests) == 2
        for req in sent_requests:
            assert req["messages"][0]["role"] == "system"
            assert req["messages"][0]["content"] == "You are helpful."

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_builds_correct_messages(self, mock_post):
        """Each sub-request contains exactly the right user message."""
        mock_response = Mock()
        mock_response.json.return_value = self._make_batch_response(["R1", "R2"])
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        llm.generate_batch(["Hello", "World"])

        sent_requests = mock_post.call_args.kwargs["json"]["requests"]
        assert sent_requests[0]["messages"][-1] == {"role": "user", "content": "Hello"}
        assert sent_requests[1]["messages"][-1] == {"role": "user", "content": "World"}

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_with_schema_returns_dicts(self, mock_post):
        """generate_batch with a schema returns a list of validated dicts."""

        class PersonSchema(BaseModel):
            name: str
            age: int

        mock_response = Mock()
        mock_response.json.return_value = self._make_batch_response(
            ['{"name": "Alice", "age": 30}', '{"name": "Bob", "age": 25}']
        )
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        results = llm.generate_batch(["P1", "P2"], schema=PersonSchema)

        assert results == [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_with_schema_injects_system_prompt(self, mock_post):
        """generate_batch injects /no_think and schema instructions when schema is given."""

        class SimpleSchema(BaseModel):
            value: str

        mock_response = Mock()
        mock_response.json.return_value = self._make_batch_response(['{"value": "x"}'])
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        llm.generate_batch(["Prompt"], schema=SimpleSchema)

        sent_messages = mock_post.call_args.kwargs["json"]["requests"][0]["messages"]
        assert sent_messages[0]["role"] == "system"
        assert "/no_think" in sent_messages[0]["content"]
        assert "JSON matching this schema" in sent_messages[0]["content"]

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_with_schema_no_json_in_response(self, mock_post):
        """When a response item contains no JSON, generate_batch returns an error dict."""

        class SimpleSchema(BaseModel):
            value: str

        mock_response = Mock()
        mock_response.json.return_value = self._make_batch_response(["not json at all"])
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        results = llm.generate_batch(["Prompt"], schema=SimpleSchema)

        assert results == [{"error": "No valid JSON found in response."}]

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_per_item_error_from_server(self, mock_post):
        """A per-item server error is surfaced as an error string (no schema)."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "responses": [
                {"choices": [{"message": {"content": "OK"}}]},
                {"error": "Internal model error"},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        results = llm.generate_batch(["P1", "P2"])

        assert results[0] == "OK"
        assert results[1] == "Internal model error"

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_per_item_error_with_schema(self, mock_post):
        """A per-item server error is surfaced as an error dict when schema is given."""

        class SimpleSchema(BaseModel):
            value: str

        mock_response = Mock()
        mock_response.json.return_value = {
            "responses": [
                {"error": "Vertex timeout"},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        results = llm.generate_batch(["P1"], schema=SimpleSchema)

        assert results == [{"error": "Vertex timeout"}]

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_per_item_no_choices(self, mock_post):
        """A response item with empty choices returns the right fallback."""
        mock_response = Mock()
        mock_response.json.return_value = {"responses": [{"choices": []}]}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        results = llm.generate_batch(["P1"])

        assert results == ["No response generated."]

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_strips_reasoning_tokens_by_default(self, mock_post):
        """Reasoning tokens are stripped from each item when include_reasoning is False."""
        mock_response = Mock()
        mock_response.json.return_value = self._make_batch_response(
            ["<think>reasoning</think>Answer 1", "<think>more</think>Answer 2"]
        )
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        results = llm.generate_batch(["P1", "P2"], include_reasoning=False)

        assert results == ["Answer 1", "Answer 2"]

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_includes_reasoning_when_requested(self, mock_post):
        """Reasoning tokens are preserved in each item when include_reasoning is True."""
        mock_response = Mock()
        mock_response.json.return_value = self._make_batch_response(
            ["<think>reasoning</think>Answer"]
        )
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        results = llm.generate_batch(["P1"], include_reasoning=True)

        assert results == ["<think>reasoning</think>Answer"]

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_http_error_returns_error_list(self, mock_post):
        """An HTTP error causes every item to be filled with an error string."""
        import requests as req_lib

        mock_post.side_effect = req_lib.exceptions.HTTPError("500 Server Error")

        llm = PolyphemusLLM(api_key="test_key")
        results = llm.generate_batch(["P1", "P2"])

        assert len(results) == 2
        assert all("error occurred" in r.lower() for r in results)

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_http_error_with_schema_returns_error_dicts(self, mock_post):
        """An HTTP error with schema causes every item to be an error dict."""
        import requests as req_lib

        class SimpleSchema(BaseModel):
            value: str

        mock_post.side_effect = req_lib.exceptions.HTTPError("500 Server Error")

        llm = PolyphemusLLM(api_key="test_key")
        results = llm.generate_batch(["P1", "P2"], schema=SimpleSchema)

        assert len(results) == 2
        assert all(isinstance(r, dict) and "error" in r for r in results)

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_includes_model_name_in_requests(self, mock_post):
        """When model_name is set, every sub-request includes the model field."""
        mock_response = Mock()
        mock_response.json.return_value = self._make_batch_response(["R1", "R2"])
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        custom_model = "meta-llama/Llama-3.1-70B-Instruct"
        llm = PolyphemusLLM(model_name=custom_model, api_key="test_key")
        llm.generate_batch(["P1", "P2"])

        sent_requests = mock_post.call_args.kwargs["json"]["requests"]
        for req in sent_requests:
            assert req["model"] == custom_model

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_generate_batch_posts_to_generate_batch_url(self, mock_post):
        """generate_batch calls /generate_batch, not /generate."""
        mock_response = Mock()
        mock_response.json.return_value = self._make_batch_response(["R1"])
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        custom_url = "https://custom.polyphemus.url"
        llm = PolyphemusLLM(api_key="test_key", base_url=custom_url)
        llm.generate_batch(["P1"])

        called_url = mock_post.call_args.args[0]
        assert called_url == f"{custom_url}/generate_batch"


class TestCreateBatchCompletion:
    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_create_batch_completion_uses_correct_url(self, mock_post):
        """create_batch_completion posts to /generate_batch."""
        mock_response = Mock()
        mock_response.json.return_value = {"responses": []}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        custom_url = "https://custom.url"
        llm = PolyphemusLLM(api_key="test_key", base_url=custom_url)
        llm.create_batch_completion([])

        assert mock_post.call_args.args[0] == f"{custom_url}/generate_batch"

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_create_batch_completion_wraps_requests_in_top_level_key(self, mock_post):
        """create_batch_completion sends {"requests": [...]} as the body."""
        mock_response = Mock()
        mock_response.json.return_value = {"responses": []}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        requests_list = [{"messages": [{"role": "user", "content": "Hi"}]}]
        llm.create_batch_completion(requests_list)

        body = mock_post.call_args.kwargs["json"]
        assert "requests" in body
        assert body["requests"] == requests_list

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_create_batch_completion_includes_auth_headers(self, mock_post):
        """create_batch_completion includes the Bearer token header."""
        mock_response = Mock()
        mock_response.json.return_value = {"responses": []}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        api_key = "my_key"
        llm = PolyphemusLLM(api_key=api_key)
        llm.create_batch_completion([])

        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == f"Bearer {api_key}"
        assert headers["Content-Type"] == "application/json"

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_create_batch_completion_raises_on_http_error(self, mock_post):
        """create_batch_completion raises HTTPError on a non-2xx response."""
        import requests as req_lib

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = req_lib.exceptions.HTTPError("500")
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        with pytest.raises(req_lib.exceptions.HTTPError):
            llm.create_batch_completion([])

    @patch("rhesis.sdk.models.providers.polyphemus.requests.post")
    def test_create_batch_completion_returns_parsed_json(self, mock_post):
        """create_batch_completion returns the parsed JSON body."""
        expected = {
            "responses": [
                {"choices": [{"message": {"content": "hi"}}], "model": "polyphemus-default"}
            ]
        }
        mock_response = Mock()
        mock_response.json.return_value = expected
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        llm = PolyphemusLLM(api_key="test_key")
        result = llm.create_batch_completion([{"messages": [{"role": "user", "content": "hi"}]}])

        assert result == expected
