import os
from typing import List, Optional

from rhesis.sdk.models.defaults import DEFAULT_LANGUAGE_MODELS, model_name_from_id

# Imported through the provider module so a slim install gets its "install [all]" error.
from rhesis.sdk.models.providers.litellm import LiteLLM, litellm

DEFAULT_MODEL = DEFAULT_LANGUAGE_MODELS["bedrock"]
DEFAULT_MODEL_NAME = model_name_from_id(DEFAULT_MODEL)

# Modes LiteLLM records for Bedrock models that can answer a chat request.
_TEXT_MODES = frozenset({"chat", "completion"})


class BedrockLLM(LiteLLM):
    """Amazon Bedrock LLM provider via LiteLLM.

    Authenticates with a Bedrock API key, which LiteLLM sends as a bearer token.
    https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html

    Args:
        model_name: Bedrock model or inference profile ID
            (e.g. ``"us.anthropic.claude-sonnet-4-5-20250929-v1:0"``).
        api_key: Bedrock API key. Falls back to ``AWS_BEARER_TOKEN_BEDROCK``.
        api_base: Regional Bedrock runtime URL
            (e.g. ``"https://bedrock-runtime.eu-central-1.amazonaws.com"``). Without it,
            LiteLLM picks the region from ``AWS_REGION_NAME``/``AWS_REGION``, else us-west-2.

    Raises:
        ValueError: If neither ``api_key`` nor ``AWS_BEARER_TOKEN_BEDROCK`` is set.

    Usage:
        >>> llm = BedrockLLM(
        ...     model_name="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        ...     api_key="your-bedrock-api-key",
        ... )
        >>> result = llm.generate("Hello!")
    """

    PROVIDER = "bedrock"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        **kwargs,
    ):
        # Without a key LiteLLM would sign with whatever AWS credentials the process has.
        api_key = api_key or os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        if not api_key:
            raise ValueError("AWS_BEARER_TOKEN_BEDROCK is not set")

        super().__init__(
            self.PROVIDER + "/" + model_name,
            api_key=api_key,
            api_base=api_base,
        )

    @classmethod
    def get_available_models(cls) -> List[str]:
        """Bedrock IDs that can generate text.

        LiteLLM's Bedrock list also holds embedding, image, rerank and realtime models,
        and pricing variants such as ``512-x-512/50-steps/<id>``.
        """
        models = []
        for model in super().get_available_models():
            mode = litellm.model_cost.get(f"{cls.PROVIDER}/{model}", {}).get("mode")
            if mode is None:
                mode = litellm.model_cost.get(model, {}).get("mode")
            # Some current Claude entries carry no mode; only a known non-text mode excludes.
            if "/" not in model and (mode is None or mode in _TEXT_MODES):
                models.append(model)
        return models
