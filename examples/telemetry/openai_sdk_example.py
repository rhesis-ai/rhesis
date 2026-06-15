"""
Direct OpenAI / Anthropic Python SDK Telemetry Example

Demonstrates manual Rhesis instrumentation when calling provider SDKs directly
(no LangChain, CrewAI, or other orchestration frameworks):
  - Application boundaries via @observe (pipeline, tool handler)
  - LLM call spans (ai.llm.invoke) via @observe with token usage from the API
  - Optional function/tool call round-trip (OpenAI tools or Anthropic tool_use)

Note: auto_instrument() does not yet wrap the OpenAI/Anthropic Python SDKs. This
example uses explicit @observe for application and LLM boundaries. Native SDK
auto-instrumentation is tracked in https://github.com/rhesis-ai/rhesis/issues/1083.

Prerequisites:
    1. Start the backend: docker compose up -d  (or ./rh dev up + ./rh dev backend)
    2. Copy env.example to .env and set RHESIS_API_KEY, RHESIS_PROJECT_ID,
       OPENAI_API_KEY (default) or ANTHROPIC_API_KEY (set OPENAI_SDK_PROVIDER=anthropic)

Run with:
    cd examples/telemetry
    uv run --extra openai-sdk openai_sdk_example.py

Traces appear in the Rhesis UI under Traces (http://localhost:3000/traces).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from opentelemetry import trace
from rhesis.telemetry.schemas import AIOperationType

from rhesis.sdk import RhesisClient, observe
from rhesis.sdk.telemetry import auto_instrument
from rhesis.sdk.telemetry.attributes import (
    AIAttributes,
    create_llm_attributes,
    create_tool_attributes,
)

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

RhesisClient.from_environment()

print("\n🔧 Calling auto_instrument() (LangChain/LangGraph if installed)...")
instrumented = auto_instrument()
print(f"✅ Auto-instrumented: {instrumented or '(none — OpenAI/Anthropic SDK not yet covered)'}\n")
print("📋 Application + LLM boundaries use @observe in this example.")
print("   Native OpenAI/Anthropic SDK support: https://github.com/rhesis-ai/rhesis/issues/1083\n")

Provider = Literal["openai", "anthropic"]
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"

TOOL_DEFINITIONS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "lookup_observability_fact",
            "description": "Return one concrete observability fact for debugging LLM apps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Short topic keyword, e.g. latency or cost",
                    }
                },
                "required": ["topic"],
            },
        },
    }
]

TOOL_DEFINITIONS_ANTHROPIC = [
    {
        "name": "lookup_observability_fact",
        "description": "Return one concrete observability fact for debugging LLM apps.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Short topic keyword, e.g. latency or cost",
                }
            },
            "required": ["topic"],
        },
    }
]


def resolve_provider() -> Provider:
    raw = os.getenv("OPENAI_SDK_PROVIDER", "openai").strip().lower()
    if raw not in ("openai", "anthropic"):
        raise ValueError(f"OPENAI_SDK_PROVIDER must be 'openai' or 'anthropic', got {raw!r}")
    return raw  # type: ignore[return-value]


def resolve_model(provider: Provider) -> str:
    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is required when OPENAI_SDK_PROVIDER=openai")
        return os.getenv("OPENAI_SDK_MODEL", DEFAULT_OPENAI_MODEL)
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY is required when OPENAI_SDK_PROVIDER=anthropic")
    return os.getenv("ANTHROPIC_SDK_MODEL", DEFAULT_ANTHROPIC_MODEL)


def _attach_usage(span: trace.Span, usage: Any, provider: Provider) -> None:
    """Map provider usage objects onto LLM token attributes."""
    if not usage or not span.is_recording():
        return
    if provider == "openai":
        prompt = getattr(usage, "prompt_tokens", None)
        completion = getattr(usage, "completion_tokens", None)
    else:
        prompt = getattr(usage, "input_tokens", None)
        completion = getattr(usage, "output_tokens", None)
    if prompt is not None:
        span.set_attribute(AIAttributes.LLM_TOKENS_INPUT, prompt)
    if completion is not None:
        span.set_attribute(AIAttributes.LLM_TOKENS_OUTPUT, completion)
    if prompt is not None and completion is not None:
        span.set_attribute(AIAttributes.LLM_TOKENS_TOTAL, prompt + completion)


@observe(
    span_name=AIOperationType.TOOL_INVOKE,
    **create_tool_attributes(
        tool_name="lookup_observability_fact",
        tool_type="function",
    ),
)
def lookup_observability_fact(topic: str) -> str:
    """Application tool implementation (invoked when the model requests it)."""
    snippets = {
        "latency": "P95 latency per step helps isolate slow stages in direct SDK chat flows.",
        "cost": "Prompt/completion token counts on each completion make spend regressions obvious.",
        "debugging": "Trace hierarchies show which completion or tool call produced a bad answer.",
    }
    key = next((k for k in snippets if k in topic.lower()), "debugging")
    return snippets[key]


def _run_openai_chat(
    client: Any,
    model: str,
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
) -> Any:
    """Single OpenAI chat completion with manual LLM span and token attributes."""

    @observe(
        span_name=AIOperationType.LLM_INVOKE,
        **create_llm_attributes(provider="openai", model_name=model),
    )
    def _completion() -> Any:
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        response = client.chat.completions.create(**kwargs)
        span = trace.get_current_span()
        _attach_usage(span, response.usage, "openai")
        return response

    return _completion()


def _run_anthropic_chat(
    client: Any,
    model: str,
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
) -> Any:
    """Single Anthropic messages call with manual LLM span and token attributes."""

    @observe(
        span_name=AIOperationType.LLM_INVOKE,
        **create_llm_attributes(provider="anthropic", model_name=model),
    )
    def _completion() -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": 1024,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        response = client.messages.create(**kwargs)
        span = trace.get_current_span()
        _attach_usage(span, response.usage, "anthropic")
        return response

    return _completion()


def _openai_tool_loop(client: Any, model: str, user_prompt: str) -> str:
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    response = _run_openai_chat(client, model, messages, tools=TOOL_DEFINITIONS_OPENAI)
    message = response.choices[0].message
    tool_calls = message.tool_calls or []
    if not tool_calls:
        return message.content or ""

    messages.append(message.model_dump(exclude_none=True))
    for tool_call in tool_calls:
        try:
            args = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError:
            print(f"⚠️  Skipping malformed OpenAI tool arguments: {tool_call.function.arguments!r}")
            args = {}
        topic = args.get("topic", "debugging")
        fact = lookup_observability_fact(str(topic))
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": fact,
            }
        )

    follow_up = _run_openai_chat(client, model, messages)
    return follow_up.choices[0].message.content or ""


def _anthropic_tool_loop(client: Any, model: str, user_prompt: str) -> str:
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    response = _run_anthropic_chat(client, model, messages, tools=TOOL_DEFINITIONS_ANTHROPIC)
    tool_blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
    if not tool_blocks:
        text_blocks = [b.text for b in response.content if hasattr(b, "text")]
        return "".join(text_blocks)

    messages.append({"role": "assistant", "content": response.content})
    tool_results = []
    for block in tool_blocks:
        topic = (block.input or {}).get("topic", "debugging")
        fact = lookup_observability_fact(str(topic))
        tool_results.append(
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": fact,
            }
        )
    messages.append({"role": "user", "content": tool_results})

    follow_up = _run_anthropic_chat(client, model, messages)
    text_blocks = [b.text for b in follow_up.content if hasattr(b, "text")]
    return "".join(text_blocks)


@observe(
    span_name=AIOperationType.AGENT_INVOKE,
    **{AIAttributes.AGENT_NAME: "openai_sdk_chat_pipeline"},
)
def run_chat_pipeline(provider: Provider, model: str, user_prompt: str) -> str:
    """
    Chat completion with optional tool round-trip.

    Trace hierarchy:
      openai_sdk_chat_pipeline (ai.agent.invoke)
        ├─ ai.llm.invoke (initial completion)
        ├─ lookup_observability_fact (ai.tool.invoke), if requested
        └─ ai.llm.invoke (follow-up completion)
    """
    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        return _openai_tool_loop(client, model, user_prompt)

    from anthropic import Anthropic

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _anthropic_tool_loop(client, model, user_prompt)


def main() -> None:
    provider = resolve_provider()
    model = resolve_model(provider)

    print("\n" + "=" * 70)
    print("🚀 Rhesis Telemetry - Direct OpenAI / Anthropic SDK Example")
    print("=" * 70)
    print("\nInstrumentation: manual @observe (pipeline, LLM, tool)")
    print("  • @observe — ai.agent.invoke on the chat pipeline")
    print("  • @observe — ai.llm.invoke per SDK completion (tokens attached)")
    print("  • @observe — ai.tool.invoke when the model calls lookup_observability_fact")
    print("  • auto_instrument() — reserved for future native SDK support (#1083)")
    print(f"\nProvider: {provider}")
    print(f"Model: {model}")
    print("=" * 70 + "\n")

    user_prompt = (
        "Why does observability matter when calling LLM APIs directly? "
        "Use the lookup_observability_fact tool once, then answer in 2 sentences."
    )
    print(f"📍 Prompt: {user_prompt}\n")

    answer = run_chat_pipeline(provider, model, user_prompt)

    print("\n" + "=" * 70)
    print("✅ Chat pipeline complete!")
    print("=" * 70)
    print(f"\nFinal answer:\n{answer}\n")
    print("📊 View traces: http://localhost:3000/traces")
    print("   Look for: pipeline → llm.invoke → tool (optional) → llm.invoke")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
