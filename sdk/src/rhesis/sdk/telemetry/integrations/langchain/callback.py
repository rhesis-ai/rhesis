"""LangChain callback handler for OpenTelemetry tracing."""

import logging
from typing import Any, Dict, List, Optional

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from rhesis.sdk.telemetry.attributes import AIAttributes, AIEvents
from rhesis.sdk.telemetry.context import is_llm_observation_active
from rhesis.sdk.telemetry.schemas import AIOperationType
from rhesis.sdk.telemetry.utils import (
    extract_token_usage,
    identify_provider_from_class_name,
    identify_provider_from_model_name,
)

logger = logging.getLogger(__name__)

# Provider patterns for LangChain module paths
_PROVIDER_PATTERNS = {
    "openai": ["openai", "langchain_openai"],
    "anthropic": ["anthropic", "langchain_anthropic"],
    "google": ["google", "langchain_google"],
    "cohere": ["cohere", "langchain_cohere"],
    "huggingface": ["huggingface", "langchain_huggingface"],
    "aws": ["aws", "bedrock", "langchain_aws"],
    "azure": ["azure"],
    "mistralai": ["mistral", "langchain_mistralai"],
}


def create_langchain_callback():
    """Create and return a LangChain callback handler for OpenTelemetry tracing."""
    try:
        from langchain_core.callbacks.base import BaseCallbackHandler
    except ImportError:
        from langchain.callbacks.base import BaseCallbackHandler

    class RhesisLangChainCallback(BaseCallbackHandler):
        """OpenTelemetry callback handler for LangChain operations."""

        def __init__(self):
            super().__init__()
            self.tracer = trace.get_tracer(__name__)
            self._spans: Dict[str, tuple[trace.Span, Any, Any]] = {}
            self._active_run_ids: set = set()

        # =========================================================================
        # Span Management
        # =========================================================================

        def _start_span(
            self, name: str, run_id: Any, parent_run_id: Any = None
        ) -> tuple[trace.Span, Any, Any]:
            """Start a span with proper parent context and make it current."""
            parent_token = None
            if parent_run_id and str(parent_run_id) in self._spans:
                parent_span, _, _ = self._spans[str(parent_run_id)]
                parent_token = otel_context.attach(trace.set_span_in_context(parent_span))

            span = self.tracer.start_span(name=name, kind=SpanKind.CLIENT)
            current_token = otel_context.attach(trace.set_span_in_context(span))
            return span, parent_token, current_token

        def _end_span(self, run_id: Any) -> None:
            """End span and detach context tokens in reverse order."""
            run_id_str = str(run_id)
            if run_id_str not in self._spans:
                return

            span, parent_token, current_token = self._spans.pop(run_id_str)
            span.end()
            self._active_run_ids.discard(run_id_str)

            if current_token:
                otel_context.detach(current_token)
            if parent_token:
                otel_context.detach(parent_token)

        def _should_skip_llm(self, run_id: Any) -> bool:
            """Check if LLM span should be skipped (deduplication)."""
            if is_llm_observation_active():
                logger.debug(f"Skipping LLM span - @observe.llm() active for {run_id}")
                return True
            if str(run_id) in self._active_run_ids:
                logger.debug(f"Skipping duplicate LLM span for {run_id}")
                return True
            return False

        # =========================================================================
        # LLM Callbacks
        # =========================================================================

        def on_chat_model_start(
            self,
            serialized: Dict[str, Any],
            messages: List[List[Any]],
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Start span for chat model invocation."""
            if self._should_skip_llm(run_id):
                return

            run_id_str = str(run_id)
            self._active_run_ids.add(run_id_str)

            span, parent_token, current_token = self._start_span(
                AIOperationType.LLM_INVOKE, run_id, parent_run_id
            )
            self._set_llm_attributes(span, serialized, kwargs, request_type="chat")
            self._add_chat_prompt_event(span, messages)
            self._spans[run_id_str] = (span, parent_token, current_token)

        def on_llm_start(
            self,
            serialized: Dict[str, Any],
            prompts: List[str],
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Start span for non-chat LLM invocation."""
            if self._should_skip_llm(run_id):
                return

            run_id_str = str(run_id)
            self._active_run_ids.add(run_id_str)

            span, parent_token, current_token = self._start_span(
                AIOperationType.LLM_INVOKE, run_id, parent_run_id
            )
            self._set_llm_attributes(
                span, serialized, kwargs, request_type=serialized.get("_type", "llm")
            )

            if prompts:
                span.add_event(
                    AIEvents.PROMPT,
                    {
                        AIAttributes.PROMPT_ROLE: "user",
                        AIAttributes.PROMPT_CONTENT: prompts[0][:1000],
                    },
                )
            self._spans[run_id_str] = (span, parent_token, current_token)

        def on_llm_end(
            self, response: Any, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
        ) -> None:
            """End LLM span with token counts and completion."""
            span_data = self._spans.get(str(run_id))
            if not span_data:
                return

            span, _, _ = span_data
            try:
                self._extract_and_set_tokens(span, response)
                span.set_status(Status(StatusCode.OK))
            finally:
                self._end_span(run_id)

        def on_llm_error(
            self, error: Exception, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
        ) -> None:
            """Handle LLM errors."""
            span_data = self._spans.get(str(run_id))
            if span_data:
                span_data[0].set_status(Status(StatusCode.ERROR, str(error)))
                span_data[0].record_exception(error)
                self._end_span(run_id)

        # =========================================================================
        # Tool Callbacks
        # =========================================================================

        def on_tool_start(
            self,
            serialized: Dict[str, Any],
            input_str: str,
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Start tool span."""
            run_id_str = str(run_id)
            if run_id_str in self._active_run_ids:
                return

            self._active_run_ids.add(run_id_str)
            span, parent_token, current_token = self._start_span(
                AIOperationType.TOOL_INVOKE, run_id, parent_run_id
            )

            span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_TOOL_INVOKE)
            span.set_attribute(AIAttributes.TOOL_NAME, serialized.get("name", "unknown"))
            span.set_attribute(AIAttributes.TOOL_TYPE, "function")
            span.add_event(AIEvents.TOOL_INPUT, {AIAttributes.TOOL_INPUT_CONTENT: input_str[:1000]})

            self._spans[run_id_str] = (span, parent_token, current_token)

        def on_tool_end(
            self, output: Any, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
        ) -> None:
            """End tool span."""
            span_data = self._spans.get(str(run_id))
            if span_data:
                output_str = self._extract_tool_output(output)
                span_data[0].add_event(
                    AIEvents.TOOL_OUTPUT, {AIAttributes.TOOL_OUTPUT_CONTENT: output_str[:1000]}
                )
                span_data[0].set_status(Status(StatusCode.OK))
                self._end_span(run_id)

        def on_tool_error(
            self, error: Exception, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
        ) -> None:
            """Handle tool errors."""
            span_data = self._spans.get(str(run_id))
            if span_data:
                span_data[0].set_status(Status(StatusCode.ERROR, str(error)))
                span_data[0].record_exception(error)
                self._end_span(run_id)

        # =========================================================================
        # Agent Callbacks (for multi-agent systems)
        # =========================================================================

        def on_chain_start(
            self,
            serialized: Dict[str, Any],
            inputs: Dict[str, Any],
            *,
            run_id: Any,
            parent_run_id: Any = None,
            tags: List[str] | None = None,
            metadata: Dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> None:
            """Start agent span if this represents an agent."""
            run_id_str = str(run_id)
            if run_id_str in self._active_run_ids:
                return

            # Extract agent name
            agent_name = self._extract_agent_name(serialized, tags, metadata)

            # Only create spans for agents, skip everything else
            if not self._is_agent(agent_name, tags, metadata):
                return

            self._active_run_ids.add(run_id_str)

            span, parent_token, current_token = self._start_span(
                AIOperationType.AGENT_INVOKE, run_id, parent_run_id
            )

            span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_AGENT_INVOKE)
            span.set_attribute(AIAttributes.AGENT_NAME, agent_name)

            self._spans[run_id_str] = (span, parent_token, current_token)

        def on_chain_end(
            self,
            outputs: Dict[str, Any],
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """End agent span."""
            span_data = self._spans.get(str(run_id))
            if span_data:
                span_data[0].set_status(Status(StatusCode.OK))
                self._end_span(run_id)

        def on_chain_error(
            self,
            error: BaseException,
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Handle agent errors."""
            span_data = self._spans.get(str(run_id))
            if span_data:
                span_data[0].set_status(Status(StatusCode.ERROR, str(error)))
                span_data[0].record_exception(error)
                self._end_span(run_id)

        # =========================================================================
        # Helper Methods
        # =========================================================================

        @staticmethod
        def _extract_agent_name(
            serialized: Dict, tags: List[str] | None, metadata: Dict | None
        ) -> str:
            """Extract agent name from metadata or serialized data."""
            # Priority 1: Explicit agent name in metadata
            if metadata:
                if agent_name := metadata.get("agent_name"):
                    return agent_name
                # LangGraph uses langgraph_node for node names
                if agent_name := metadata.get("langgraph_node"):
                    return agent_name

            # Priority 2: Name from serialized
            if name := serialized.get("name"):
                return name

            # Priority 3: Extract from id path
            if "id" in serialized and isinstance(serialized["id"], list):
                return serialized["id"][-1] if serialized["id"] else "unknown"

            return "unknown"

        @staticmethod
        def _is_agent(name: str, tags: List[str] | None, metadata: Dict | None) -> bool:
            """Determine if this represents an agent."""
            # Check for agent-related patterns in name
            agent_patterns = [
                "agent",
                "specialist",
                "orchestrator",
                "coordinator",
                "supervisor",
            ]
            name_lower = name.lower()
            if any(p in name_lower for p in agent_patterns):
                return True

            # Check tags for agent markers
            if tags:
                for tag in tags:
                    if any(p in tag.lower() for p in agent_patterns):
                        return True

            # Check metadata for agent indicators
            if metadata:
                if metadata.get("is_agent") or metadata.get("agent_name"):
                    return True

            return False

        def _set_llm_attributes(
            self, span: trace.Span, serialized: Dict, kwargs: Dict, request_type: str
        ) -> None:
            """Set common LLM span attributes."""
            span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_LLM_INVOKE)
            span.set_attribute(
                AIAttributes.MODEL_NAME, self._extract_model_name(serialized, kwargs)
            )
            span.set_attribute(AIAttributes.LLM_REQUEST_TYPE, request_type)

            provider = self._extract_provider(serialized, kwargs)
            if provider:
                span.set_attribute(AIAttributes.MODEL_PROVIDER, provider)

        def _add_chat_prompt_event(self, span: trace.Span, messages: List[List[Any]]) -> None:
            """Add prompt event from chat messages."""
            if not messages or not messages[0]:
                return

            first_msg = messages[0][0]
            content = str(getattr(first_msg, "content", ""))[:1000]
            role = getattr(first_msg, "type", "user")
            span.add_event(
                AIEvents.PROMPT,
                {AIAttributes.PROMPT_ROLE: role, AIAttributes.PROMPT_CONTENT: content},
            )

        def _extract_and_set_tokens(self, span: trace.Span, response: Any) -> None:
            """Extract token usage from response and set span attributes."""
            input_tokens, output_tokens, total_tokens = 0, 0, 0

            # Try llm_output.token_usage
            if hasattr(response, "llm_output") and response.llm_output:
                usage = response.llm_output.get("token_usage", {})
                if usage:
                    input_tokens, output_tokens, total_tokens = extract_token_usage(usage)

            # Try generations
            if hasattr(response, "generations") and response.generations:
                gen = response.generations[0][0]

                # Extract completion
                if hasattr(gen, "text"):
                    span.add_event(
                        AIEvents.COMPLETION, {AIAttributes.COMPLETION_CONTENT: gen.text[:1000]}
                    )
                elif hasattr(gen, "message") and hasattr(gen.message, "content"):
                    span.add_event(
                        AIEvents.COMPLETION,
                        {AIAttributes.COMPLETION_CONTENT: str(gen.message.content)[:1000]},
                    )

                # Try message.usage_metadata
                if not total_tokens and hasattr(gen, "message"):
                    usage = getattr(gen.message, "usage_metadata", None)
                    if usage:
                        input_tokens, output_tokens, total_tokens = extract_token_usage(usage)

                # Try generation_info
                if hasattr(gen, "generation_info") and gen.generation_info:
                    info = gen.generation_info
                    if finish := info.get("finish_reason"):
                        span.set_attribute(AIAttributes.LLM_FINISH_REASON, finish)

                    if not total_tokens:
                        for key in ["usage_metadata", "token_usage"]:
                            if usage := info.get(key, {}):
                                tokens = extract_token_usage(usage)
                                input_tokens, output_tokens, total_tokens = tokens
                                if total_tokens:
                                    break

            # Set token attributes
            if input_tokens or output_tokens or total_tokens:
                span.set_attribute(AIAttributes.LLM_TOKENS_INPUT, input_tokens)
                span.set_attribute(AIAttributes.LLM_TOKENS_OUTPUT, output_tokens)
                span.set_attribute(
                    AIAttributes.LLM_TOKENS_TOTAL, total_tokens or (input_tokens + output_tokens)
                )

        @staticmethod
        def _extract_tool_output(output: Any) -> str:
            """Extract string content from tool output."""
            if isinstance(output, str):
                return output
            if hasattr(output, "content"):
                content = output.content
                return str(content) if isinstance(content, (str, list)) else str(output)
            if isinstance(output, dict):
                return str(output.get("content", output))
            return str(output)

        @staticmethod
        def _extract_model_name(serialized: Dict, kwargs: Dict) -> str:
            """Extract model name from LangChain invocation."""
            if "model" in kwargs:
                return str(kwargs["model"])
            if "kwargs" in serialized and isinstance(serialized["kwargs"], dict):
                for key in ["model", "model_name"]:
                    if key in serialized["kwargs"]:
                        return str(serialized["kwargs"][key])
            return serialized.get("name", "unknown")

        @staticmethod
        def _extract_provider(serialized: Dict, kwargs: Dict) -> Optional[str]:
            """Extract provider from model info."""
            # Check module path
            module_path = ""
            if "id" in serialized and isinstance(serialized["id"], list):
                module_path = ".".join(serialized["id"]).lower()
            elif "kwargs" in serialized and "_type" in serialized["kwargs"]:
                module_path = serialized["kwargs"]["_type"].lower()

            for provider, patterns in _PROVIDER_PATTERNS.items():
                if any(p in module_path for p in patterns):
                    return provider

            # Try class name
            if class_name := serialized.get("name", ""):
                if provider := identify_provider_from_class_name(class_name):
                    return provider

            # Try model name
            if "model" in kwargs:
                if provider := identify_provider_from_model_name(str(kwargs["model"])):
                    return provider

            return "unknown"

    return RhesisLangChainCallback()
