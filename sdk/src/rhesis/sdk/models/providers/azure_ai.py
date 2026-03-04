import os
from typing import Optional

from rhesis.sdk.models.defaults import DEFAULT_LANGUAGE_MODELS, model_name_from_id
from rhesis.sdk.models.providers.litellm import LiteLLM

DEFAULT_MODEL = DEFAULT_LANGUAGE_MODELS["azure_ai"]
DEFAULT_MODEL_NAME = model_name_from_id(DEFAULT_MODEL)


class AzureAILLM(LiteLLM):
    """Azure AI Studio LLM provider via LiteLLM.

    Supports all models hosted on Azure AI Studio (Cohere, Mistral,
    AI21, Meta, etc.) using the ``azure_ai/`` prefix understood by
    LiteLLM.

    Args:
        model_name: Deployment or model name on Azure AI Studio
            (e.g. ``"command-r-plus"``).
        api_key: Azure AI API key.  Falls back to ``AZURE_AI_API_KEY``
            env var.
        api_base: Azure AI inference endpoint URL.  Falls back to
            ``AZURE_AI_API_BASE`` env var.

    Raises:
        ValueError: If neither ``api_key`` nor ``AZURE_AI_API_KEY`` is set.
        ValueError: If neither ``api_base`` nor ``AZURE_AI_API_BASE`` is set.

    Usage:
        >>> llm = AzureAILLM(
        ...     model_name="command-r-plus",
        ...     api_key="your-key",
        ...     api_base="https://your-endpoint.inference.ai.azure.com/",
        ... )
        >>> result = llm.generate("Hello!")
    """

    PROVIDER = "azure_ai"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        **kwargs,
    ):
        api_key = api_key or os.getenv("AZURE_AI_API_KEY")
        if api_key is None:
            raise ValueError("AZURE_AI_API_KEY is not set")

        self.api_base = api_base or os.getenv("AZURE_AI_API_BASE")
        if self.api_base is None:
            raise ValueError("AZURE_AI_API_BASE is not set")

        super().__init__(
            self.PROVIDER + "/" + model_name,
            api_key=api_key,
        )
