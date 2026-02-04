"""AI semantic conventions and helper functions."""

from typing import Any, Dict

# Import semantic layer constants from schemas (single source of truth)
from rhesis.sdk.telemetry.schemas import FORBIDDEN_SPAN_DOMAINS


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

    # Operation type values (not to be confused with span names)
    OPERATION_LLM_INVOKE = "llm.invoke"
    OPERATION_TOOL_INVOKE = "tool.invoke"
    OPERATION_RETRIEVAL = "retrieval"
    OPERATION_EMBEDDING_CREATE = "embedding.create"
    OPERATION_RERANK = "rerank"
    OPERATION_EVALUATION = "evaluation"
    OPERATION_GUARDRAIL = "guardrail"
    OPERATION_TRANSFORM = "transform"
    OPERATION_AGENT_INVOKE = "agent.invoke"
    OPERATION_AGENT_HANDOFF = "agent.handoff"

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

    # Rerank
    RERANK_MODEL = "ai.rerank.model"
    RERANK_TOP_N = "ai.rerank.top_n"
    RERANK_QUERY_TYPE = "ai.rerank.query.type"

    # Evaluation
    EVALUATION_METRIC = "ai.evaluation.metric"
    EVALUATION_EVALUATOR = "ai.evaluation.evaluator"
    EVALUATION_SCORE = "ai.evaluation.score"

    # Guardrail
    GUARDRAIL_TYPE = "ai.guardrail.type"
    GUARDRAIL_PROVIDER = "ai.guardrail.provider"
    GUARDRAIL_RESULT = "ai.guardrail.result"

    # Transform
    TRANSFORM_TYPE = "ai.transform.type"
    TRANSFORM_OPERATION = "ai.transform.operation"
    TRANSFORM_INPUT_SIZE = "ai.transform.input.size"
    TRANSFORM_OUTPUT_SIZE = "ai.transform.output.size"

    # Agent (for multi-agent systems)
    AGENT_NAME = "ai.agent.name"
    AGENT_HANDOFF_FROM = "ai.agent.handoff.from"
    AGENT_HANDOFF_TO = "ai.agent.handoff.to"
    AGENT_INPUT_CONTENT = "ai.agent.input"
    AGENT_OUTPUT_CONTENT = "ai.agent.output"

    # Error
    ERROR_TYPE = "ai.error.type"
    ERROR_RETRYABLE = "ai.error.retryable"

    # Event attribute keys (for span events)
    PROMPT_ROLE = "ai.prompt.role"
    PROMPT_CONTENT = "ai.prompt.content"
    COMPLETION_CONTENT = "ai.completion.content"
    TOOL_INPUT_CONTENT = "ai.tool.input"
    TOOL_OUTPUT_CONTENT = "ai.tool.output"

    # Function I/O attributes (semantic layer)
    FUNCTION_ARGS = "function.args"
    FUNCTION_KWARGS = "function.kwargs"
    FUNCTION_RESULT = "function.result"
    FUNCTION_RESULT_PREVIEW = "function.result_preview"

    # Function metadata attributes (semantic layer)
    FUNCTION_NAME = "function.name"
    FUNCTION_ARGS_COUNT = "function.args_count"
    FUNCTION_KWARGS_COUNT = "function.kwargs_count"
    FUNCTION_OUTPUT_CHUNKS = "function.output_chunks"


class AIEvents:
    """AI semantic convention event names."""

    PROMPT = "ai.prompt"
    COMPLETION = "ai.completion"
    TOOL_INPUT = "ai.tool.input"
    TOOL_OUTPUT = "ai.tool.output"
    RETRIEVAL_QUERY = "ai.retrieval.query"
    RETRIEVAL_RESULTS = "ai.retrieval.results"
    AGENT_INPUT = "ai.agent.input"
    AGENT_OUTPUT = "ai.agent.output"


def create_llm_attributes(
    provider: str,
    model_name: str,
    tokens_input: int = None,
    tokens_output: int = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Create standard attributes for LLM invocation.

    Use with span name AIOperationType.LLM_INVOKE.

    Example:
        with tracer.start_as_current_span(AIOperationType.LLM_INVOKE) as span:
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
        AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
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

    Use with span name AIOperationType.TOOL_INVOKE.

    Example:
        with tracer.start_as_current_span(AIOperationType.TOOL_INVOKE) as span:
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
        AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_TOOL_INVOKE,
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
    parts = span_name.split(".")
    if len(parts) >= 2 and parts[1] in FORBIDDEN_SPAN_DOMAINS:
        return False

    return True
