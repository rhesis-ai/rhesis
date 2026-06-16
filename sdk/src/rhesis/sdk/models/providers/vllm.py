import os
from typing import Optional

from rhesis.sdk.errors import NO_MODEL_NAME_PROVIDED
from rhesis.sdk.models.providers.litellm import LiteLLM

"""
LiteLLM routes OpenAI-compatible vLLM servers through the hosted_vllm provider.
https://docs.litellm.ai/docs/providers/vllm
"""

DEFAULT_API_BASE = "http://localhost:8000"


class VllmLLM(LiteLLM):
    PROVIDER = "hosted_vllm"

    def __init__(
        self,
        model_name: str,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs,
    ):
        """
        VllmLLM: vLLM LLM Provider

        This class provides an interface to models served by a vLLM OpenAI-compatible
        inference server via LiteLLM.

        In order to use this class, you need a running vLLM server exposing
        /v1/chat/completions. See https://docs.vllm.ai/ for setup instructions.

        Args:
            model_name: The model name as served by your vLLM instance
                (e.g. "meta-llama/Llama-2-7b-chat-hf").
            api_base: Base URL of the vLLM server (without /v1).
                Defaults to HOSTED_VLLM_API_BASE env var or http://localhost:8000.
            api_key: Optional API key when the vLLM server requires authentication.
                Defaults to HOSTED_VLLM_API_KEY env var.
            **kwargs: Additional parameters passed to the underlying LiteLLM completion call.

        Usage:
            >>> llm = VllmLLM(
            ...     model_name="meta-llama/Llama-2-7b-chat-hf",
            ...     api_base="http://localhost:8000",
            ... )
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and
        returned as a dict.
        """
        if not model_name or not isinstance(model_name, str) or model_name.strip() == "":
            raise ValueError(NO_MODEL_NAME_PROVIDED)
        resolved_api_base = api_base or os.getenv("HOSTED_VLLM_API_BASE") or DEFAULT_API_BASE
        resolved_api_key = api_key or os.getenv("HOSTED_VLLM_API_KEY")
        super().__init__(
            self.PROVIDER + "/" + model_name,
            api_key=resolved_api_key,
            api_base=resolved_api_base,
        )
