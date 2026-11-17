import os
from unittest.mock import Mock, patch

import pytest

from rhesis.sdk.models.providers.bedrock import (
    DEFAULT_EMBEDDING_MODEL_NAME,
    DEFAULT_MODEL_NAME,
    BedrockEmbedder,
    BedrockLLM,
)

PROFILE_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
EU_RUNTIME = "https://bedrock-runtime.eu-central-1.amazonaws.com"


def test_bedrock_defaults():
    assert BedrockLLM.PROVIDER == "bedrock"
    assert DEFAULT_MODEL_NAME
    assert BedrockEmbedder.PROVIDER == "bedrock"
    assert DEFAULT_EMBEDDING_MODEL_NAME == "amazon.titan-embed-text-v2:0"


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


_LIST_ALL = "rhesis.sdk.models.providers.litellm.LiteLLM.get_available_models"


class TestBedrockModelListing:
    """Mocked catalogue: LiteLLM's real one changes with every release."""

    CATALOGUE = {
        "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0": {"mode": "chat"},
        "amazon.titan-text-express-v1": {"mode": "completion"},
        "amazon.titan-embed-text-v2:0": {"mode": "embedding"},
        "amazon.rerank-v1:0": {"mode": "rerank"},
        "amazon.nova-canvas-v1:0": {"mode": "image_generation"},
        "amazon.nova-2-sonic-v1:0": {"mode": "realtime"},
        "512-x-512/50-steps/stability.stable-diffusion-xl-v0": {"mode": "image_generation"},
    }

    def _listed(self, listed):
        with (
            patch(_LIST_ALL, return_value=listed),
            patch.dict("litellm.model_cost", self.CATALOGUE, clear=True),
        ):
            return BedrockLLM.get_available_models()

    def test_keeps_chat_and_completion_models(self):
        listed = ["us.anthropic.claude-sonnet-4-5-20250929-v1:0", "amazon.titan-text-express-v1"]
        assert self._listed(listed) == listed

    def test_drops_models_that_cannot_generate_text(self):
        listed = [
            "amazon.titan-embed-text-v2:0",
            "amazon.rerank-v1:0",
            "amazon.nova-canvas-v1:0",
            "amazon.nova-2-sonic-v1:0",
        ]
        assert self._listed(listed) == []

    def test_drops_pricing_variants(self):
        assert self._listed(["512-x-512/50-steps/stability.stable-diffusion-xl-v0"]) == []

    def test_keeps_a_model_whose_mode_litellm_does_not_record(self):
        assert self._listed(["anthropic.claude-v2"]) == ["anthropic.claude-v2"]


# --- Embedder ---


TITAN_EMBED = "amazon.titan-embed-text-v2:0"


class TestBedrockEmbedderInit:
    def test_init_with_explicit_key(self):
        emb = BedrockEmbedder(api_key="bedrock-key")
        assert emb.api_key == "bedrock-key"
        assert emb.model_name == f"bedrock/{TITAN_EMBED}"

    def test_init_with_custom_model(self):
        emb = BedrockEmbedder(model_name="amazon.titan-embed-image-v1:0", api_key="k")
        assert emb.model_name == "bedrock/amazon.titan-embed-image-v1:0"

    def test_init_with_dimensions(self):
        emb = BedrockEmbedder(api_key="k", dimensions=1024)
        assert emb.dimensions == 1024

    def test_init_with_env_key(self):
        with patch.dict(os.environ, {"AWS_BEARER_TOKEN_BEDROCK": "env-key"}, clear=True):
            assert BedrockEmbedder().api_key == "env-key"

    def test_explicit_key_overrides_env(self):
        with patch.dict(os.environ, {"AWS_BEARER_TOKEN_BEDROCK": "env-key"}, clear=True):
            assert BedrockEmbedder(api_key="explicit").api_key == "explicit"

    def test_missing_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="AWS_BEARER_TOKEN_BEDROCK is not set"):
                BedrockEmbedder()

    def test_iam_keys_alone_are_not_enough(self):
        env = {"AWS_ACCESS_KEY_ID": "AKIA...", "AWS_SECRET_ACCESS_KEY": "secret"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="AWS_BEARER_TOKEN_BEDROCK is not set"):
                BedrockEmbedder()


class TestBedrockEmbedderGenerate:
    @patch("rhesis.sdk.models.providers.litellm.aembedding")
    def test_generate_sends_key_and_dimensions(self, mock_aembedding):
        mock_aembedding.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

        emb = BedrockEmbedder(api_key="bedrock-key", dimensions=1024)
        result = emb.generate("hello")

        assert result == [0.1, 0.2, 0.3]
        kwargs = mock_aembedding.call_args.kwargs
        assert kwargs["model"] == f"bedrock/{TITAN_EMBED}"
        assert kwargs["api_key"] == "bedrock-key"
        assert kwargs["dimensions"] == 1024

    @patch("rhesis.sdk.models.providers.litellm.embedding")
    def test_generate_batch(self, mock_embedding):
        mock_embedding.return_value = {
            "data": [{"embedding": [0.1]}, {"embedding": [0.2]}]
        }

        emb = BedrockEmbedder(api_key="bedrock-key", dimensions=1024)
        result = emb.generate_batch(["hello", "world"])

        assert result == [[0.1], [0.2]]
        kwargs = mock_embedding.call_args.kwargs
        assert kwargs["input"] == ["hello", "world"]
        assert kwargs["api_key"] == "bedrock-key"
        assert kwargs["dimensions"] == 1024


_GET_VALID = "litellm.get_valid_models"


class TestBedrockEmbeddingListing:
    """Mocked catalogue: filters by mode, not by name substring."""

    CATALOGUE = {
        "bedrock/amazon.titan-embed-text-v2:0": {"mode": "embedding"},
        "amazon.titan-embed-text-v2:0": {"mode": "embedding"},
        "bedrock/amazon.titan-embed-image-v1:0": {"mode": "embedding"},
        "amazon.titan-embed-image-v1:0": {"mode": "embedding"},
        "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0": {"mode": "chat"},
        "amazon.titan-text-express-v1": {"mode": "completion"},
        "amazon.rerank-v1:0": {"mode": "rerank"},
    }

    def _listed(self, raw_models):
        with (
            patch(_GET_VALID, return_value=raw_models),
            patch.dict("litellm.model_cost", self.CATALOGUE, clear=True),
        ):
            return BedrockEmbedder.get_available_models()

    def test_keeps_embedding_models(self):
        raw = [
            "bedrock/amazon.titan-embed-text-v2:0",
            "bedrock/amazon.titan-embed-image-v1:0",
        ]
        assert self._listed(raw) == [
            "amazon.titan-embed-text-v2:0",
            "amazon.titan-embed-image-v1:0",
        ]

    def test_drops_non_embedding_models(self):
        raw = [
            "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "bedrock/amazon.titan-text-express-v1",
            "bedrock/amazon.rerank-v1:0",
        ]
        assert self._listed(raw) == []

    def test_drops_pricing_variants(self):
        catalogue = {"512-x-512/50-steps/amazon.titan-embed-text-v2:0": {"mode": "embedding"}}
        raw = ["bedrock/512-x-512/50-steps/amazon.titan-embed-text-v2:0"]
        with (
            patch(_GET_VALID, return_value=raw),
            patch.dict("litellm.model_cost", catalogue, clear=True),
        ):
            assert BedrockEmbedder.get_available_models() == []
