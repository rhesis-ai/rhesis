"""AI semantic conventions and helper functions."""

from typing import Any, Dict


class AIAttributes:
    """
    AI semantic convention attribute keys.

    These attributes follow OpenTelemetry semantic conventions for AI operations.
    """

    # System
    SYSTEM = "ai.system"
    REQUEST_ID = "ai.request.id"
    SESSION_ID = "ai.session.id"

    # Operation
    OPERATION_TYPE = "ai.operation.type"

    # Model
    MODEL_PROVIDER = "ai.model.provider"
    MODEL_NAME = "ai.model.name"

    # LLM
    LLM_REQUEST_TYPE = "ai.llm.request.type"
    LLM_TOKENS_INPUT = "ai.llm.tokens.input"
    LLM_TOKENS_OUTPUT = "ai.llm.tokens.output"
    LLM_TOKENS_TOTAL = "ai.llm.tokens.total"
    LLM_FINISH_REASON = "ai.llm.finish_reason"
    LLM_TEMPERATURE = "ai.llm.temperature"
    LLM_MAX_TOKENS = "ai.llm.max_tokens"

    # Tool
    TOOL_NAME = "ai.tool.name"
    TOOL_TYPE = "ai.tool.type"

    # Retrieval
    RETRIEVAL_BACKEND = "ai.retrieval.backend"
    RETRIEVAL_TOP_K = "ai.retrieval.top_k"
    RETRIEVAL_QUERY_TYPE = "ai.retrieval.query.type"

    # Embedding
    EMBEDDING_VECTOR_SIZE = "ai.embedding.vector.size"
    EMBEDDING_MODEL = "ai.embedding.model"

    # Error
    ERROR_TYPE = "ai.error.type"
    ERROR_RETRYABLE = "ai.error.retryable"


class AIEvents:
    """AI semantic convention event names."""

    PROMPT = "ai.prompt"
    COMPLETION = "ai.completion"
    TOOL_INPUT = "ai.tool.input"
    TOOL_OUTPUT = "ai.tool.output"
    RETRIEVAL_QUERY = "ai.retrieval.query"
    RETRIEVAL_RESULTS = "ai.retrieval.results"


def create_llm_attributes(
    provider: str,
    model_name: str,
    tokens_input: int = None,
    tokens_output: int = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Create standard attributes for LLM invocation.

    Use with span name 'ai.llm.invoke'.

    Example:
        with tracer.start_as_current_span("ai.llm.invoke") as span:
            attrs = create_llm_attributes(provider="openai", model_name="gpt-4")
            span.set_attributes(attrs)

    Args:
        provider: Model provider (e.g., 'openai', 'anthropic')
        model_name: Model name (e.g., 'gpt-4')
        tokens_input: Input token count
        tokens_output: Output token count
        **kwargs: Additional attributes (e.g., temperature, max_tokens)

    Returns:
        Dictionary of attributes following AI semantic conventions
    """
    attrs = {
        AIAttributes.OPERATION_TYPE: "llm.invoke",
        AIAttributes.MODEL_PROVIDER: provider,
        AIAttributes.MODEL_NAME: model_name,
    }

    if tokens_input is not None:
        attrs[AIAttributes.LLM_TOKENS_INPUT] = tokens_input

    if tokens_output is not None:
        attrs[AIAttributes.LLM_TOKENS_OUTPUT] = tokens_output

    if tokens_input is not None and tokens_output is not None:
        attrs[AIAttributes.LLM_TOKENS_TOTAL] = tokens_input + tokens_output

    attrs.update(kwargs)
    return attrs


def create_tool_attributes(
    tool_name: str,
    tool_type: str,
    **kwargs,
) -> Dict[str, Any]:
    """
    Create standard attributes for tool invocation.

    Use with span name 'ai.tool.invoke'.

    Example:
        with tracer.start_as_current_span("ai.tool.invoke") as span:
            attrs = create_tool_attributes(
                tool_name="weather_api",
                tool_type="http"
            )
            span.set_attributes(attrs)

    Args:
        tool_name: Tool name (e.g., 'weather_api', 'calculator')
        tool_type: Tool type (e.g., 'http', 'function', 'database')
        **kwargs: Additional attributes (e.g., http.method, http.url)

    Returns:
        Dictionary of attributes following AI semantic conventions
    """
    attrs = {
        AIAttributes.OPERATION_TYPE: "tool.invoke",
        AIAttributes.TOOL_NAME: tool_name,
        AIAttributes.TOOL_TYPE: tool_type,
    }

    attrs.update(kwargs)
    return attrs


def validate_span_name(span_name: str) -> bool:
    """
    Client-side validation for span names (non-blocking).

    Valid patterns:
    - ai.<domain>.<action> (e.g., ai.llm.invoke)
    - function.<name> (e.g., function.process_data)

    Invalid: Framework concepts (agent, chain, workflow, pipeline)

    This validation matches what the backend enforces. Invalid span names
    will be rejected with HTTP 422.

    Args:
        span_name: Span name to validate

    Returns:
        True if valid, False otherwise
    """
    import re

    # Allow function.* pattern
    if span_name.startswith("function."):
        return True

    # Validate ai.* pattern
    pattern = r"^ai\.[a-z]+(\.[a-z]+)?$"
    if not re.match(pattern, span_name):
        return False

    # Reject framework concepts
    forbidden_domains = ["agent", "chain", "workflow", "pipeline"]
    parts = span_name.split(".")
    if len(parts) >= 2 and parts[1] in forbidden_domains:
        return False

    return True
