import os
from typing import Optional

from rhesis.sdk.models.defaults import DEFAULT_LANGUAGE_MODELS, model_name_from_id
from rhesis.sdk.models.providers.litellm import LiteLLM

DEFAULT_MODEL = DEFAULT_LANGUAGE_MODELS["azure"]
DEFAULT_MODEL_NAME = model_name_from_id(DEFAULT_MODEL)


class AzureOpenAILLM(LiteLLM):
    """Azure OpenAI LLM provider via LiteLLM.

    Supports all Azure OpenAI deployments (GPT-4o, GPT-4, GPT-3.5-Turbo,
    o-series, etc.) using the ``azure/`` prefix understood by LiteLLM.

    Args:
        model_name: Azure deployment name (e.g. ``"my-gpt4o-deployment"``).
        api_key: Azure OpenAI API key.  Falls back to ``AZURE_API_KEY``
            env var.
        api_base: Azure OpenAI endpoint URL.  Falls back to
            ``AZURE_API_BASE`` env var.
        api_version: Azure API version string (e.g. ``"2024-08-01-preview"``).
            Falls back to ``AZURE_API_VERSION`` env var.

    Raises:
        ValueError: If neither ``api_key`` nor ``AZURE_API_KEY`` is set.
        ValueError: If neither ``api_base`` nor ``AZURE_API_BASE`` is set.

    Usage:
        >>> llm = AzureOpenAILLM(
        ...     model_name="my-gpt4o-deployment",
        ...     api_key="your-key",
        ...     api_base="https://your-resource.openai.azure.com/",
        ... )
        >>> result = llm.generate("Hello!")
    """

    PROVIDER = "azure"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        api_version: Optional[str] = None,
        **kwargs,
    ):
        api_key = api_key or os.getenv("AZURE_API_KEY")
        if api_key is None:
            raise ValueError("AZURE_API_KEY is not set")

        self.api_base = api_base or os.getenv("AZURE_API_BASE")
        if self.api_base is None:
            raise ValueError("AZURE_API_BASE is not set")

        self.api_version = api_version or os.getenv("AZURE_API_VERSION")

        super().__init__(
            self.PROVIDER + "/" + model_name,
            api_key=api_key,
        )
