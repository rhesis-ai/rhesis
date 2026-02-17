"""
Canonical default model identifiers in unified provider/name form.

All defaults are stored as full model ids (e.g. "vertex_ai/gemini-2.0-flash").
Use _model_name(full_id) to get the name part when calling provider constructors.
"""

# Default when get_model() is called with no arguments (language)
DEFAULT_LANGUAGE_MODEL = "rhesis/rhesis-default"

# Default when requesting an embedding with no arguments
DEFAULT_EMBEDDING_MODEL = "rhesis/rhesis-embedding"

# Per-provider default language models (full id: provider/name)
DEFAULT_LANGUAGE_MODELS = {
    "rhesis": "rhesis/rhesis-default",
    "anthropic": "anthropic/claude-4",
    "cohere": "cohere/command-r-plus",
    "gemini": "gemini/gemini-2.0-flash",
    "groq": "groq/llama3-8b-8192",
    "huggingface": "huggingface/meta-llama/Llama-2-7b-chat-hf",
    "lmformatenforcer": "lmformatenforcer/meta-llama/Llama-2-7b-chat-hf",
    "meta_llama": "meta_llama/Llama-3.3-70B-Instruct",
    "mistral": "mistral/mistral-medium-latest",
    "ollama": "ollama/llama3.1",
    "openai": "openai/gpt-4o",
    "openrouter": "openrouter/openai/gpt-4o-mini",
    "perplexity": "perplexity/sonar-pro",
    "polyphemus": "polyphemus/",  # Polyphemus uses API's default model
    "replicate": "replicate/llama-2-70b-chat",
    "together_ai": "together_ai/togethercomputer/llama-2-70b-chat",
    "vertex_ai": "vertex_ai/gemini-2.0-flash",
}

# Per-provider default embedding models (full id: provider/name)
DEFAULT_EMBEDDING_MODELS = {
    "rhesis": "rhesis/rhesis-embedding",
    "openai": "openai/text-embedding-3-small",
    "gemini": "gemini/gemini-embedding-001",
    "vertex_ai": "vertex_ai/text-embedding-005",
}


def parse_model_id(full_id: str) -> tuple[str, str]:
    """Split a full model id into (provider, model_name).

    Args:
        full_id: Unified model id, e.g. "vertex_ai/gemini-2.0-flash"

    Returns:
        (provider, model_name), e.g. ("vertex_ai", "gemini-2.0-flash")
    """
    if not full_id:
        return "", ""
    if "/" in full_id:
        parts = full_id.split("/", 1)
        return parts[0], parts[1]
    return full_id, ""


def model_name_from_id(full_id: str) -> str:
    """Return the model name part of a full model id (after the first slash)."""
    return parse_model_id(full_id)[1]
