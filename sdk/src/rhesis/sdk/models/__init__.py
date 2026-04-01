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

# Provider classes are loaded lazily via __getattr__ so that importing
# ``rhesis.sdk.models`` does not transitively pull in heavy dependencies
# (litellm → gRPC) at module-import time.  This matters in Celery workers
# that use prefork: any native extension loaded before fork() can corrupt
# child-process state and cause SIGSEGV.

_PROVIDER_IMPORTS = {
    "AzureAILLM": "rhesis.sdk.models.providers.azure_ai",
    "AzureOpenAILLM": "rhesis.sdk.models.providers.azure_openai",
    "GeminiEmbedder": "rhesis.sdk.models.providers.gemini",
    "GeminiLLM": "rhesis.sdk.models.providers.gemini",
    "LiteLLM": "rhesis.sdk.models.providers.litellm",
    "LiteLLMProxy": "rhesis.sdk.models.providers.litellm_proxy",
    "RhesisLLM": "rhesis.sdk.models.providers.native",
    "OpenAIEmbedder": "rhesis.sdk.models.providers.openai",
    "OpenAILLM": "rhesis.sdk.models.providers.openai",
    "OpenRouterLLM": "rhesis.sdk.models.providers.openrouter",
    "PolyphemusLLM": "rhesis.sdk.models.providers.polyphemus",
    "VertexAIEmbedder": "rhesis.sdk.models.providers.vertex_ai",
    "VertexAILLM": "rhesis.sdk.models.providers.vertex_ai",
    "HuggingFaceLLM": "rhesis.sdk.models.providers.huggingface",
}


def __getattr__(name: str):
    if name == "HUGGINGFACE_AVAILABLE":
        try:
            __getattr__("HuggingFaceLLM")
            return True
        except ImportError:
            return False

    module_path = _PROVIDER_IMPORTS.get(name)
    if module_path is not None:
        import importlib

        mod = importlib.import_module(module_path)
        obj = getattr(mod, name)
        globals()[name] = obj
        return obj

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AzureAILLM",
    "AzureOpenAILLM",
    "BaseEmbedder",
    "BaseLLM",
    "BaseModel",
    "ModelType",
    "GeminiEmbedder",
    "GeminiLLM",
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
    "HuggingFaceLLM",
]
