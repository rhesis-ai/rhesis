"""Model providers and factory; heavy provider backends load on first use."""

from __future__ import annotations

import importlib
import importlib.util
from typing import TYPE_CHECKING

from rhesis.sdk.models.base import BaseEmbedder, BaseLLM, BaseModel
from rhesis.sdk.models.factory import (
    ModelType,
    get_available_embedding_models,
    get_available_language_models,
    get_embedder,
    get_embedding_model,
    get_language_model,
    get_model,
)

if TYPE_CHECKING:
    from rhesis.sdk.models.providers.azure_ai import AzureAILLM
    from rhesis.sdk.models.providers.azure_openai import AzureOpenAILLM
    from rhesis.sdk.models.providers.gemini import GeminiEmbedder, GeminiLLM
    from rhesis.sdk.models.providers.huggingface import HuggingFaceLLM
    from rhesis.sdk.models.providers.litellm import LiteLLM
    from rhesis.sdk.models.providers.litellm_proxy import LiteLLMProxy
    from rhesis.sdk.models.providers.native import RhesisLLM
    from rhesis.sdk.models.providers.openai import OpenAIEmbedder, OpenAILLM
    from rhesis.sdk.models.providers.openrouter import OpenRouterLLM
    from rhesis.sdk.models.providers.polyphemus import PolyphemusLLM
    from rhesis.sdk.models.providers.vertex_ai import VertexAIEmbedder, VertexAILLM


def _huggingface_deps_installed() -> bool:
    """Cheap check without importing torch/transformers."""
    return (
        importlib.util.find_spec("torch") is not None
        and importlib.util.find_spec("transformers") is not None
    )


# Cheap runtime flag (find_spec only; does not import torch/transformers).
HUGGINGFACE_AVAILABLE = _huggingface_deps_installed()


_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "AzureAILLM": ("rhesis.sdk.models.providers.azure_ai", "AzureAILLM"),
    "AzureOpenAILLM": ("rhesis.sdk.models.providers.azure_openai", "AzureOpenAILLM"),
    "GeminiEmbedder": ("rhesis.sdk.models.providers.gemini", "GeminiEmbedder"),
    "GeminiLLM": ("rhesis.sdk.models.providers.gemini", "GeminiLLM"),
    "LiteLLM": ("rhesis.sdk.models.providers.litellm", "LiteLLM"),
    "LiteLLMProxy": ("rhesis.sdk.models.providers.litellm_proxy", "LiteLLMProxy"),
    "RhesisLLM": ("rhesis.sdk.models.providers.native", "RhesisLLM"),
    "OpenAIEmbedder": ("rhesis.sdk.models.providers.openai", "OpenAIEmbedder"),
    "OpenAILLM": ("rhesis.sdk.models.providers.openai", "OpenAILLM"),
    "OpenRouterLLM": ("rhesis.sdk.models.providers.openrouter", "OpenRouterLLM"),
    "PolyphemusLLM": ("rhesis.sdk.models.providers.polyphemus", "PolyphemusLLM"),
    "VertexAIEmbedder": ("rhesis.sdk.models.providers.vertex_ai", "VertexAIEmbedder"),
    "VertexAILLM": ("rhesis.sdk.models.providers.vertex_ai", "VertexAILLM"),
}


def __getattr__(name: str):
    if name == "HuggingFaceLLM":
        try:
            mod = importlib.import_module("rhesis.sdk.models.providers.huggingface")
            return mod.HuggingFaceLLM
        except ImportError as exc:
            raise AttributeError(
                f"module {__name__!r} has no attribute {name!r}"
            ) from exc
    spec = _LAZY_EXPORTS.get(name)
    if spec is not None:
        module_name, attr_name = spec
        mod = importlib.import_module(module_name)
        return getattr(mod, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)


__all__ = [
    "AzureAILLM",
    "AzureOpenAILLM",
    "BaseEmbedder",
    "BaseLLM",
    "BaseModel",
    "ModelType",
    "GeminiEmbedder",
    "GeminiLLM",
    "HUGGINGFACE_AVAILABLE",
    "HuggingFaceLLM",
    "LiteLLM",
    "LiteLLMProxy",
    "OpenAIEmbedder",
    "OpenAILLM",
    "OpenRouterLLM",
    "PolyphemusLLM",
    "RhesisLLM",
    "VertexAIEmbedder",
    "VertexAILLM",
    "get_available_embedding_models",
    "get_available_language_models",
    "get_embedder",
    "get_embedding_model",
    "get_language_model",
    "get_model",
]
