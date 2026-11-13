import os
from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.models.providers.bedrock import DEFAULT_MODEL_NAME, BedrockLLM

PROFILE_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
EU_RUNTIME = "https://bedrock-runtime.eu-central-1.amazonaws.com"


def test_bedrock_defaults():
    assert BedrockLLM.PROVIDER == "bedrock"
    assert DEFAULT_MODEL_NAME


class TestBedrockLLMInit:
    def test_init_with_explicit_key(self):
        llm = BedrockLLM(model_name=PROFILE_ID, api_key="bedrock-key")
        assert llm.api_key == "bedrock-key"
        assert llm.api_base is None
        assert llm.model_name == f"bedrock/{PROFILE_ID}"

    def test_init_with_regional_endpoint(self):
        llm = BedrockLLM(model_name=PROFILE_ID, api_key="bedrock-key", api_base=EU_RUNTIME)
        assert llm.api_base == EU_RUNTIME

    def test_init_with_env_key(self):
        with patch.dict(os.environ, {"AWS_BEARER_TOKEN_BEDROCK": "env-key"}, clear=True):
            assert BedrockLLM().api_key == "env-key"

    def test_explicit_key_overrides_env(self):
        with patch.dict(os.environ, {"AWS_BEARER_TOKEN_BEDROCK": "env-key"}, clear=True):
            assert BedrockLLM(api_key="explicit").api_key == "explicit"

    def test_iam_keys_alone_are_not_enough(self):
        # Without a Bedrock key LiteLLM would sign with the process's own AWS credentials.
        env = {"AWS_ACCESS_KEY_ID": "AKIA...", "AWS_SECRET_ACCESS_KEY": "secret"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="AWS_BEARER_TOKEN_BEDROCK is not set"):
                BedrockLLM()

    def test_empty_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="AWS_BEARER_TOKEN_BEDROCK is not set"):
                BedrockLLM(api_key="")


class TestBedrockLLMGenerate:
    @patch("rhesis.sdk.models.providers.litellm.acompletion")
    def test_generate_sends_key_and_endpoint(self, mock_acompletion):
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = "hello"
        mock_acompletion.return_value = response

        llm = BedrockLLM(model_name=PROFILE_ID, api_key="bedrock-key", api_base=EU_RUNTIME)
        assert llm.generate("hi") == "hello"

        kwargs = mock_acompletion.call_args.kwargs
        assert kwargs["model"] == f"bedrock/{PROFILE_ID}"
        assert kwargs["api_key"] == "bedrock-key"
        assert kwargs["api_base"] == EU_RUNTIME


class TestBedrockModelListing:
    def test_lists_text_models_without_the_provider_prefix(self):
        models = BedrockLLM.get_available_models()
        assert any("anthropic.claude" in m for m in models)
        assert not any(m.startswith("bedrock/") for m in models)

    def test_drops_models_that_cannot_generate_text(self):
        models = BedrockLLM.get_available_models()
        for not_text in (
            "amazon.titan-embed-text-v2:0",
            "cohere.embed-v4:0",
            "amazon.rerank-v1:0",
            "amazon.nova-canvas-v1:0",
            "stability.sd3-large-v1:0",
        ):
            assert not_text not in models
        assert not any("/" in m for m in models)

    def test_keeps_a_model_whose_mode_litellm_does_not_record(self):
        listed = ["anthropic.claude-v2", "cohere.embed-v4:0"]
        costs = {"bedrock/cohere.embed-v4:0": {"mode": "embedding"}}
        with (
            patch(
                "rhesis.sdk.models.providers.litellm.LiteLLM.get_available_models",
                return_value=listed,
            ),
            patch.dict("litellm.model_cost", costs, clear=True),
        ):
            assert BedrockLLM.get_available_models() == ["anthropic.claude-v2"]
