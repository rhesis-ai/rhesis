"""
Provider-agnostic utilities for identifying LLM providers.

This module provides utilities for identifying which LLM provider is being used
based on model names, class names, or other hints. This works across all frameworks
(LangChain, LlamaIndex, direct API calls, etc.).
"""

from typing import Optional

# Provider name constants
PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GOOGLE = "google"
PROVIDER_COHERE = "cohere"
PROVIDER_META = "meta"
PROVIDER_MISTRAL = "mistralai"
PROVIDER_AWS = "aws"
PROVIDER_AZURE = "azure"
PROVIDER_HUGGINGFACE = "huggingface"
PROVIDER_UNKNOWN = "unknown"


def identify_provider_from_model_name(model_name: str) -> Optional[str]:
    """
    Identify provider from a model name or identifier.

    This function uses pattern matching to identify the provider based on
    common model naming conventions used across the industry.

    Args:
        model_name: Model name or identifier (e.g., "gpt-4", "claude-3-opus", "gemini-pro")

    Returns:
        Provider identifier or None if not recognized

    Examples:
        >>> identify_provider_from_model_name("gpt-4-turbo")
        'openai'
        >>> identify_provider_from_model_name("claude-3-opus-20240229")
        'anthropic'
        >>> identify_provider_from_model_name("gemini-1.5-pro")
        'google'
        >>> identify_provider_from_model_name("command-r-plus")
        'cohere'
    """
    if not model_name:
        return None

    model_lower = model_name.lower()

    # Check compound patterns first (to avoid false matches)
    # Azure OpenAI patterns (check before plain OpenAI/GPT)
    if "azure" in model_lower:
        return PROVIDER_AZURE

    # AWS Bedrock patterns (check before provider-specific patterns)
    if any(pattern in model_lower for pattern in ["bedrock", "amazon.titan"]):
        return PROVIDER_AWS

    # OpenAI patterns
    if any(pattern in model_lower for pattern in ["gpt", "text-davinci", "text-curie", "chatgpt"]):
        return PROVIDER_OPENAI

    # Anthropic patterns
    if any(pattern in model_lower for pattern in ["claude", "anthropic"]):
        return PROVIDER_ANTHROPIC

    # Google patterns
    if any(pattern in model_lower for pattern in ["gemini", "palm", "bard"]):
        return PROVIDER_GOOGLE

    # Cohere patterns
    if any(pattern in model_lower for pattern in ["command", "cohere"]):
        return PROVIDER_COHERE

    # Meta/Llama patterns
    if any(pattern in model_lower for pattern in ["llama", "meta-llama"]):
        return PROVIDER_META

    # Mistral patterns
    if any(pattern in model_lower for pattern in ["mistral", "mixtral"]):
        return PROVIDER_MISTRAL

    return None


def identify_provider_from_class_name(class_name: str) -> Optional[str]:
    """
    Identify provider from a class name.

    Useful for framework integrations where the LLM class name contains
    provider information (e.g., "ChatOpenAI", "ChatAnthropic").

    Args:
        class_name: Class name (e.g., "ChatOpenAI", "Anthropic", "GoogleGenerativeAI")

    Returns:
        Provider identifier or None if not recognized

    Examples:
        >>> identify_provider_from_class_name("ChatOpenAI")
        'openai'
        >>> identify_provider_from_class_name("ChatAnthropic")
        'anthropic'
        >>> identify_provider_from_class_name("HuggingFaceHub")
        'huggingface'
    """
    if not class_name:
        return None

    class_lower = class_name.lower()

    # Check for provider names in class name
    if "openai" in class_lower:
        return PROVIDER_OPENAI
    elif "anthropic" in class_lower:
        return PROVIDER_ANTHROPIC
    elif "google" in class_lower or "gemini" in class_lower:
        return PROVIDER_GOOGLE
    elif "cohere" in class_lower:
        return PROVIDER_COHERE
    elif "huggingface" in class_lower or "hugging" in class_lower:
        return PROVIDER_HUGGINGFACE
    elif "bedrock" in class_lower or "aws" in class_lower:
        return PROVIDER_AWS
    elif "azure" in class_lower:
        return PROVIDER_AZURE
    elif "mistral" in class_lower:
        return PROVIDER_MISTRAL
    elif "meta" in class_lower or "llama" in class_lower:
        return PROVIDER_META

    return None


def identify_provider(
    model_name: Optional[str] = None, class_name: Optional[str] = None, **kwargs
) -> str:
    """
    Identify provider using multiple strategies.

    This is the main entry point for provider identification. It tries multiple
    strategies in order of reliability:
    1. Model name pattern matching
    2. Class name pattern matching
    3. Additional kwargs hints

    Args:
        model_name: Model name/identifier
        class_name: Class or model type name
        **kwargs: Additional hints (e.g., provider="openai", model="gpt-4")

    Returns:
        Provider identifier (defaults to "unknown" if not found)

    Examples:
        >>> identify_provider(model_name="gpt-4")
        'openai'
        >>> identify_provider(class_name="ChatAnthropic")
        'anthropic'
        >>> identify_provider(model_name="custom-model", provider="openai")
        'openai'
    """
    # Strategy 1: Check explicit provider kwarg
    if "provider" in kwargs:
        return kwargs["provider"].lower()

    # Strategy 2: Try model name pattern matching
    if model_name:
        provider = identify_provider_from_model_name(model_name)
        if provider:
            return provider

    # Strategy 3: Try class name pattern matching
    if class_name:
        provider = identify_provider_from_class_name(class_name)
        if provider:
            return provider

    # Strategy 4: Check other kwargs for hints
    # Some frameworks pass model in different keys
    for key in ["model", "model_id", "model_type", "engine"]:
        if key in kwargs and kwargs[key]:
            provider = identify_provider_from_model_name(str(kwargs[key]))
            if provider:
                return provider

    return PROVIDER_UNKNOWN
