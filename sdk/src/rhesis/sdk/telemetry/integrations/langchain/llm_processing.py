"""LLM response processing utilities for LangChain callback handler.

This module handles the complex task of extracting token usage and completion
content from LangChain LLM responses. Different providers return tokens in
different locations and formats, so this module provides multiple fallback
strategies.
"""

import logging
from typing import Any, Dict, List

from opentelemetry import trace

from rhesis.sdk.telemetry.attributes import AIAttributes, AIEvents
from rhesis.sdk.telemetry.utils import extract_token_usage

from .extractors import MAX_CONTENT_LENGTH, extract_model_name, extract_provider

logger = logging.getLogger(__name__)


def set_llm_attributes(span: trace.Span, serialized: Dict, kwargs: Dict, request_type: str) -> None:
    """Set common LLM span attributes (operation type, model, provider)."""
    span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_LLM_INVOKE)
    span.set_attribute(AIAttributes.MODEL_NAME, extract_model_name(serialized, kwargs))
    span.set_attribute(AIAttributes.LLM_REQUEST_TYPE, request_type)

    provider = extract_provider(serialized, kwargs)
    if provider:
        span.set_attribute(AIAttributes.MODEL_PROVIDER, provider)


def add_chat_prompt_event(span: trace.Span, messages: List[List[Any]]) -> None:
    """Add prompt event from chat messages."""
    if not messages or not messages[0]:
        return

    first_msg = messages[0][0]
    content = str(getattr(first_msg, "content", ""))[:MAX_CONTENT_LENGTH]
    role = getattr(first_msg, "type", "user")
    span.add_event(
        AIEvents.PROMPT,
        {AIAttributes.PROMPT_ROLE: role, AIAttributes.PROMPT_CONTENT: content},
    )


def extract_and_set_tokens(span: trace.Span, response: Any) -> None:
    """Extract token usage from LLM response and set span attributes.

    This function tries multiple sources to extract token counts, as different
    providers store this information in different locations:

    1. llm_output.token_usage (OpenAI, most common)
    2. llm_output.usage (Anthropic format)
    3. response.usage (direct usage attribute)
    4. message.usage_metadata (LangChain v0.1+ / newer providers)
    5. message.response_metadata.token_usage (some providers)
    6. generation.usage_metadata (fallback)
    7. generation_info (various providers)

    Also extracts completion content and tool calls from the response.
    """
    input_tokens, output_tokens, total_tokens = 0, 0, 0
    token_source = None  # Track where we got tokens from for debugging

    # Source 1: llm_output.token_usage (OpenAI, most common)
    if hasattr(response, "llm_output") and response.llm_output:
        usage = response.llm_output.get("token_usage", {})
        if usage:
            input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
            if total_tokens:
                token_source = "llm_output.token_usage"
                logger.debug(
                    f"📊 Tokens from llm_output.token_usage: "
                    f"in={input_tokens}, out={output_tokens}, total={total_tokens}"
                )

        # Source 2: llm_output.usage (Anthropic format)
        if not total_tokens:
            usage = response.llm_output.get("usage", {})
            if usage:
                input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
                if total_tokens:
                    token_source = "llm_output.usage"
                    logger.debug(
                        f"📊 Tokens from llm_output.usage: "
                        f"in={input_tokens}, out={output_tokens}, total={total_tokens}"
                    )

    # Source 3: response.usage (direct usage attribute)
    if not total_tokens and hasattr(response, "usage") and response.usage:
        usage = response.usage
        if isinstance(usage, dict):
            input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
        else:
            # Handle usage as object with attributes
            usage_dict = {}
            for attr in [
                "input_tokens",
                "output_tokens",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
            ]:
                if hasattr(usage, attr):
                    usage_dict[attr] = getattr(usage, attr)
            if usage_dict:
                input_tokens, output_tokens, total_tokens = extract_token_usage(usage_dict)
        if total_tokens:
            token_source = "response.usage"
            logger.debug(
                f"📊 Tokens from response.usage: "
                f"in={input_tokens}, out={output_tokens}, total={total_tokens}"
            )

    # Process generations for completion content and additional token sources
    if hasattr(response, "generations") and response.generations:
        tokens_result = _process_generations(
            span, response.generations, input_tokens, output_tokens, total_tokens, token_source
        )
        input_tokens, output_tokens, total_tokens, token_source = tokens_result

    # Set token attributes
    _set_token_attributes(span, input_tokens, output_tokens, total_tokens, token_source, response)


def _process_generations(
    span: trace.Span,
    generations: List,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    token_source: str | None,
) -> tuple[int, int, int, str | None]:
    """Process generations to extract completion content and tokens."""
    gen = generations[0][0]

    # Extract completion content
    completion_content = ""
    tool_calls_extracted = []

    # Get content from gen.text first (if available)
    if hasattr(gen, "text") and gen.text:
        completion_content = gen.text

    # Always check message for content (fallback), tool calls, and tokens
    if hasattr(gen, "message"):
        msg = gen.message

        # Get text content if we don't have it yet
        if not completion_content and hasattr(msg, "content") and msg.content:
            completion_content = str(msg.content)

        # Extract tool calls
        tool_calls_extracted = _extract_tool_calls(msg)

        # Try to get tokens from message (works for Gemini and many providers)
        if not total_tokens:
            tokens = _extract_tokens_from_message(msg)
            if tokens[2]:  # total_tokens
                input_tokens, output_tokens, total_tokens = tokens[:3]
                token_source = tokens[3]

    # Build completion content
    if not completion_content and tool_calls_extracted:
        completion_content = f"[Tool calls: {', '.join(tool_calls_extracted)}]"

    # Always add completion event
    content = completion_content[:MAX_CONTENT_LENGTH] if completion_content else "[No content]"
    span.add_event(
        AIEvents.COMPLETION,
        {AIAttributes.COMPLETION_CONTENT: content},
    )

    # Source 6: generation.usage_metadata (fallback)
    if not total_tokens and hasattr(gen, "usage_metadata"):
        usage = getattr(gen, "usage_metadata", None)
        if usage:
            tokens = _extract_from_usage_object(usage)
            if tokens[2]:
                input_tokens, output_tokens, total_tokens = tokens
                token_source = "generation.usage_metadata"
                logger.debug(
                    f"📊 Tokens from generation.usage_metadata: "
                    f"in={input_tokens}, out={output_tokens}, total={total_tokens}"
                )

    # Source 7: generation_info (various providers)
    if hasattr(gen, "generation_info") and gen.generation_info:
        info = gen.generation_info
        if finish := info.get("finish_reason"):
            span.set_attribute(AIAttributes.LLM_FINISH_REASON, finish)

        if not total_tokens:
            tokens = _extract_tokens_from_generation_info(info)
            if tokens[2]:
                input_tokens, output_tokens, total_tokens = tokens[:3]
                token_source = tokens[3]

    return input_tokens, output_tokens, total_tokens, token_source


def _extract_tool_calls(msg: Any) -> List[str]:
    """Extract tool call names from a message."""
    tool_calls_extracted = []

    # Location 1: msg.tool_calls (standard LangChain)
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        for tc in msg.tool_calls:
            if isinstance(tc, dict):
                tool_calls_extracted.append(tc.get("name", "unknown"))
            else:
                tool_calls_extracted.append(getattr(tc, "name", "unknown"))

    # Location 2: additional_kwargs.tool_calls (some providers)
    if not tool_calls_extracted:
        additional = getattr(msg, "additional_kwargs", {}) or {}
        if "tool_calls" in additional:
            for tc in additional["tool_calls"]:
                if isinstance(tc, dict):
                    func = tc.get("function", tc)
                    tool_calls_extracted.append(func.get("name", "unknown"))

    # Location 3: additional_kwargs.function_call (older format)
    if not tool_calls_extracted:
        additional = getattr(msg, "additional_kwargs", {}) or {}
        if "function_call" in additional:
            fc = additional["function_call"]
            tool_calls_extracted.append(fc.get("name", "unknown"))

    return tool_calls_extracted


def _extract_tokens_from_message(msg: Any) -> tuple[int, int, int, str | None]:
    """Extract tokens from message metadata."""
    input_tokens, output_tokens, total_tokens = 0, 0, 0
    token_source = None

    # Source 4: message.usage_metadata (LangChain v0.1+ / newer providers)
    usage = getattr(msg, "usage_metadata", None)
    if usage:
        tokens = _extract_from_usage_object(usage)
        if tokens[2]:
            input_tokens, output_tokens, total_tokens = tokens
            token_source = "message.usage_metadata"
            logger.debug(
                f"📊 Tokens from message.usage_metadata: "
                f"in={input_tokens}, out={output_tokens}, total={total_tokens}"
            )

    # Source 5: message.response_metadata.token_usage (some providers)
    if not total_tokens:
        response_meta = getattr(msg, "response_metadata", {}) or {}
        if isinstance(response_meta, dict):
            usage = response_meta.get("token_usage", {})
            if usage:
                input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
                if total_tokens:
                    token_source = "message.response_metadata.token_usage"
                    logger.debug(
                        f"📊 Tokens from response_metadata.token_usage: "
                        f"in={input_tokens}, out={output_tokens}, total={total_tokens}"
                    )

    return input_tokens, output_tokens, total_tokens, token_source


def _extract_from_usage_object(usage: Any) -> tuple[int, int, int]:
    """Extract tokens from a usage object (dict or object)."""
    if isinstance(usage, dict):
        return extract_token_usage(usage)
    else:
        # Handle UsageMetadata object
        usage_dict = {}
        for attr in ["input_tokens", "output_tokens", "total_tokens"]:
            if hasattr(usage, attr):
                usage_dict[attr] = getattr(usage, attr)
        if usage_dict:
            return extract_token_usage(usage_dict)
    return 0, 0, 0


def _extract_tokens_from_generation_info(info: Dict) -> tuple[int, int, int, str | None]:
    """Extract tokens from generation_info dict."""
    input_tokens, output_tokens, total_tokens = 0, 0, 0
    token_source = None

    for key in ["usage_metadata", "token_usage", "usage"]:
        usage = info.get(key, {})
        if usage:
            if isinstance(usage, dict):
                tokens = extract_token_usage(usage)
            else:
                usage_dict = {}
                token_attrs = [
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "prompt_tokens",
                    "completion_tokens",
                ]
                for attr in token_attrs:
                    if hasattr(usage, attr):
                        usage_dict[attr] = getattr(usage, attr)
                tokens = extract_token_usage(usage_dict) if usage_dict else (0, 0, 0)
            input_tokens, output_tokens, total_tokens = tokens
            if total_tokens:
                token_source = f"generation_info.{key}"
                logger.debug(
                    f"📊 Tokens from generation_info.{key}: "
                    f"in={input_tokens}, out={output_tokens}, total={total_tokens}"
                )
                break

    return input_tokens, output_tokens, total_tokens, token_source


def _set_token_attributes(
    span: trace.Span,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    token_source: str | None,
    response: Any,
) -> None:
    """Set token attributes on span or log warning if not found."""
    if input_tokens or output_tokens or total_tokens:
        span.set_attribute(AIAttributes.LLM_TOKENS_INPUT, input_tokens)
        span.set_attribute(AIAttributes.LLM_TOKENS_OUTPUT, output_tokens)
        span.set_attribute(
            AIAttributes.LLM_TOKENS_TOTAL, total_tokens or (input_tokens + output_tokens)
        )
        logger.info(
            f"✅ Set token attributes from {token_source}: "
            f"input={input_tokens}, output={output_tokens}, "
            f"total={total_tokens or (input_tokens + output_tokens)}"
        )
    else:
        # Log warning with available response structure for debugging
        logger.warning(
            f"⚠️  Could not extract tokens from LLM response. "
            f"Response type: {type(response).__name__}, "
            f"Has llm_output: {hasattr(response, 'llm_output')}, "
            f"Has generations: {hasattr(response, 'generations')}, "
            f"Has usage: {hasattr(response, 'usage')}"
        )
        # Log available keys for debugging
        if hasattr(response, "llm_output") and response.llm_output:
            logger.debug(f"   llm_output keys: {list(response.llm_output.keys())}")
        if hasattr(response, "generations") and response.generations:
            gen = response.generations[0][0]
            if hasattr(gen, "message"):
                msg = gen.message
                logger.debug(
                    f"   message attrs: usage_metadata={hasattr(msg, 'usage_metadata')}, "
                    f"response_metadata={hasattr(msg, 'response_metadata')}"
                )
