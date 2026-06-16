import os
from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.models.providers.vllm import DEFAULT_API_BASE, VllmLLM


class TestVllmLLM:
    def test_provider_constant(self):
        assert VllmLLM.PROVIDER == "hosted_vllm"

    def test_init_sets_litellm_model_name(self):
        llm = VllmLLM(model_name="meta-llama/Llama-2-7b-chat-hf")
        assert llm.model_name == "hosted_vllm/meta-llama/Llama-2-7b-chat-hf"
        assert llm.api_base == DEFAULT_API_BASE
        assert llm.api_key is None

    def test_init_with_api_base_and_api_key(self):
        llm = VllmLLM(
            model_name="facebook/opt-125m",
            api_base="https://vllm.example.com",
            api_key="secret",
        )
        assert llm.model_name == "hosted_vllm/facebook/opt-125m"
        assert llm.api_base == "https://vllm.example.com"
        assert llm.api_key == "secret"

    def test_init_uses_env_vars(self, monkeypatch):
        monkeypatch.setenv("HOSTED_VLLM_API_BASE", "http://vllm.local:8000")
        monkeypatch.setenv("HOSTED_VLLM_API_KEY", "env-key")

        llm = VllmLLM(model_name="qwen")

        assert llm.api_base == "http://vllm.local:8000"
        assert llm.api_key == "env-key"

    def test_init_without_name(self):
        with pytest.raises(ValueError):
            VllmLLM("")

    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_generate_calls_litellm_with_api_base(self, mock_completion):
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "ok"
        mock_completion.return_value = mock_response

        llm = VllmLLM(
            model_name="facebook/opt-125m",
            api_base="http://localhost:8000",
        )
        result = llm.generate("ping")

        assert result == "ok"
        mock_completion.assert_called_once_with(
            model="hosted_vllm/facebook/opt-125m",
            messages=[{"role": "user", "content": "ping"}],
            response_format=None,
            api_key=None,
            api_base="http://localhost:8000",
            api_version=None,
        )

    @patch("rhesis.sdk.models.factory._create_from_spec")
    def test_get_model_registry_wires_vllm(self, mock_create):
        from rhesis.sdk.models.factory import get_model

        get_model("vllm", "my-model", api_base="http://localhost:8000")

        mock_create.assert_called_once()
        spec, model_type, model_name, api_key, dimensions = mock_create.call_args[0]
        kwargs = mock_create.call_args[1]
        assert spec.module.endswith(".vllm")
        assert spec.class_name == "VllmLLM"
        assert model_type.value == "language"
        assert model_name == "my-model"
        assert api_key is None
        assert kwargs == {"api_base": "http://localhost:8000"}
