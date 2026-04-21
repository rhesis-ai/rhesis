import os
from unittest.mock import Mock, patch

import pytest
import requests
from pydantic import BaseModel

from rhesis.sdk.models.providers.litellm_proxy import (
    DEFAULT_API_BASE,
    LiteLLMProxy,
)


def _mock_openai_response(content: str) -> Mock:
    """Build a mock requests.Response matching the OpenAI chat completions format."""
    mock_response = Mock(spec=requests.Response)
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "id": "test-id",
        "model": "gemini",
        "object": "chat.completion",
        "choices": [
            {
                "finish_reason": "stop",
                "index": 0,
                "message": {"content": content, "role": "assistant"},
            }
        ],
        "usage": {
            "completion_tokens": 10,
            "prompt_tokens": 5,
            "total_tokens": 15,
        },
    }
    return mock_response


class TestLiteLLMProxyInit:
    def test_init_with_defaults(self):
        llm = LiteLLMProxy(model_name="gemini")
        assert llm.model_name == "gemini"
        assert llm.api_base == DEFAULT_API_BASE
        assert llm.api_key is None

    def test_init_with_custom_api_base(self):
        llm = LiteLLMProxy(model_name="gemini", api_base="http://localhost:8000")
        assert llm.api_base == "http://localhost:8000"

    def test_init_with_env_api_base(self):
        with patch.dict(os.environ, {"LITELLM_PROXY_BASE_URL": "http://env:9000"}):
            llm = LiteLLMProxy(model_name="gemini")
            assert llm.api_base == "http://env:9000"

    def test_init_explicit_api_base_overrides_env(self):
        with patch.dict(os.environ, {"LITELLM_PROXY_BASE_URL": "http://env:9000"}):
            llm = LiteLLMProxy(model_name="gemini", api_base="http://explicit:7000")
            assert llm.api_base == "http://explicit:7000"

    def test_init_with_api_key(self):
        llm = LiteLLMProxy(model_name="gemini", api_key="sk-test-key")
        assert llm.api_key == "sk-test-key"

    def test_init_with_env_api_key(self):
        with patch.dict(os.environ, {"LITELLM_PROXY_API_KEY": "sk-env-key"}):
            llm = LiteLLMProxy(model_name="gemini")
            assert llm.api_key == "sk-env-key"

    def test_init_without_model_name_raises(self):
        with pytest.raises(ValueError):
            LiteLLMProxy(model_name="")

    def test_init_with_none_model_name_raises(self):
        with pytest.raises(ValueError):
            LiteLLMProxy(model_name=None)

    def test_init_with_whitespace_model_name_raises(self):
        with pytest.raises(ValueError):
            LiteLLMProxy(model_name="   ")

    def test_provider_attribute(self):
        assert LiteLLMProxy.PROVIDER == "litellm_proxy"


class TestLiteLLMProxyGenerate:
    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_without_schema(self, mock_post):
        mock_post.return_value = _mock_openai_response("Hello there!")

        llm = LiteLLMProxy(model_name="gemini")
        result = llm.generate("Hi")

        assert result == "Hello there!"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert payload["model"] == "gemini"
        assert payload["messages"] == [{"role": "user", "content": "Hi"}]

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_with_system_prompt(self, mock_post):
        mock_post.return_value = _mock_openai_response("I am Arkadiusz Kwasigroch.")

        llm = LiteLLMProxy(model_name="gemini")
        result = llm.generate(
            "what is your name?",
            system_prompt="You are an LLM Arkadiusz Kwasigroch",
        )

        assert result == "I am Arkadiusz Kwasigroch."
        payload = mock_post.call_args[1]["json"]
        assert payload["messages"] == [
            {
                "role": "system",
                "content": "You are an LLM Arkadiusz Kwasigroch",
            },
            {"role": "user", "content": "what is your name?"},
        ]

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_with_pydantic_schema(self, mock_post):
        class PersonInfo(BaseModel):
            name: str
            age: int

        mock_post.return_value = _mock_openai_response('{"name": "Alice", "age": 30}')

        llm = LiteLLMProxy(model_name="gemini")
        result = llm.generate("Tell me about Alice", schema=PersonInfo)

        assert isinstance(result, dict)
        assert result == {"name": "Alice", "age": 30}

        payload = mock_post.call_args[1]["json"]
        assert "response_format" in payload
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["name"] == "PersonInfo"

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_with_pydantic_schema_is_azure_strict_compatible(self, mock_post):
        """Regression for issue #1657.

        Azure OpenAI's strict mode rejects schemas that don't set
        ``additionalProperties: false`` on every object node (including nested
        ``$defs``). The provider must emit a strict-compliant schema so that
        test set generation works when Azure is fronted by a LiteLLM Proxy.
        """

        class Inner(BaseModel):
            name: str

        class Outer(BaseModel):
            inner: Inner
            label: str

        mock_post.return_value = _mock_openai_response(
            '{"inner": {"name": "x"}, "label": "y"}'
        )

        llm = LiteLLMProxy(model_name="gemini")
        llm.generate("hi", schema=Outer)

        response_format = mock_post.call_args[1]["json"]["response_format"]
        assert response_format["type"] == "json_schema"
        json_schema = response_format["json_schema"]
        assert json_schema["strict"] is True

        schema = json_schema["schema"]
        assert schema["additionalProperties"] is False
        assert schema["$defs"]["Inner"]["additionalProperties"] is False

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_with_dict_schema(self, mock_post):
        dict_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "TestSchema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                    },
                    "required": ["value"],
                },
            },
        }

        mock_post.return_value = _mock_openai_response('{"value": "test"}')

        llm = LiteLLMProxy(model_name="gemini")
        result = llm.generate("test prompt", schema=dict_schema)

        assert result == {"value": "test"}
        payload = mock_post.call_args[1]["json"]
        assert payload["response_format"] == dict_schema

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_with_schema_invalid_response(self, mock_post):
        class StrictSchema(BaseModel):
            name: str
            age: int

        mock_post.return_value = _mock_openai_response('{"name": "Alice"}')

        llm = LiteLLMProxy(model_name="gemini")
        with pytest.raises(Exception):
            llm.generate("test", schema=StrictSchema)

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_with_additional_kwargs(self, mock_post):
        mock_post.return_value = _mock_openai_response("response")

        llm = LiteLLMProxy(model_name="gemini")
        llm.generate("test", temperature=0.7, max_tokens=100)

        payload = mock_post.call_args[1]["json"]
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 100

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_http_error(self, mock_post):
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Server Error"
        )
        mock_post.return_value = mock_response

        llm = LiteLLMProxy(model_name="gemini")
        with pytest.raises(requests.exceptions.HTTPError):
            llm.generate("test")

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_sends_auth_header_when_api_key_set(self, mock_post):
        mock_post.return_value = _mock_openai_response("ok")

        llm = LiteLLMProxy(model_name="gemini", api_key="sk-secret")
        llm.generate("test")

        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer sk-secret"
        assert headers["Content-Type"] == "application/json"

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_no_auth_header_without_api_key(self, mock_post):
        mock_post.return_value = _mock_openai_response("ok")

        llm = LiteLLMProxy(model_name="gemini")
        llm.generate("test")

        headers = mock_post.call_args[1]["headers"]
        assert "Authorization" not in headers

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_correct_url(self, mock_post):
        mock_post.return_value = _mock_openai_response("ok")

        llm = LiteLLMProxy(model_name="gemini", api_base="http://myproxy:4000")
        llm.generate("test")

        url = mock_post.call_args[0][0]
        assert url == "http://myproxy:4000/chat/completions"

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_strips_trailing_slash_from_api_base(self, mock_post):
        mock_post.return_value = _mock_openai_response("ok")

        llm = LiteLLMProxy(model_name="gemini", api_base="http://myproxy:4000/")
        llm.generate("test")

        url = mock_post.call_args[0][0]
        assert url == "http://myproxy:4000/chat/completions"


class TestLiteLLMProxyGenerateBatch:
    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_batch_without_schema(self, mock_post):
        mock_post.side_effect = [
            _mock_openai_response("Response 1"),
            _mock_openai_response("Response 2"),
        ]

        llm = LiteLLMProxy(model_name="gemini")
        results = llm.generate_batch(["Prompt 1", "Prompt 2"])

        assert results == ["Response 1", "Response 2"]
        assert mock_post.call_count == 2

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_batch_with_system_prompt(self, mock_post):
        mock_post.return_value = _mock_openai_response("Response")

        llm = LiteLLMProxy(model_name="gemini")
        llm.generate_batch(["Prompt 1"], system_prompt="Be helpful")

        payload = mock_post.call_args[1]["json"]
        assert payload["messages"][0] == {
            "role": "system",
            "content": "Be helpful",
        }

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_batch_with_schema(self, mock_post):
        class Item(BaseModel):
            name: str
            value: int

        mock_post.side_effect = [
            _mock_openai_response('{"name": "A", "value": 1}'),
            _mock_openai_response('{"name": "B", "value": 2}'),
        ]

        llm = LiteLLMProxy(model_name="gemini")
        results = llm.generate_batch(["item A", "item B"], schema=Item)

        assert len(results) == 2
        assert results[0] == {"name": "A", "value": 1}
        assert results[1] == {"name": "B", "value": 2}

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_batch_with_n_greater_than_one(self, mock_post):
        mock_post.side_effect = [
            _mock_openai_response("R1a"),
            _mock_openai_response("R1b"),
            _mock_openai_response("R2a"),
            _mock_openai_response("R2b"),
        ]

        llm = LiteLLMProxy(model_name="gemini")
        results = llm.generate_batch(["P1", "P2"], n=2)

        assert results == ["R1a", "R1b", "R2a", "R2b"]
        assert mock_post.call_count == 4

    @patch("rhesis.sdk.models.providers.litellm_proxy.requests.post")
    def test_generate_batch_empty_prompts(self, mock_post):
        llm = LiteLLMProxy(model_name="gemini")
        results = llm.generate_batch([])

        assert results == []
        mock_post.assert_not_called()
