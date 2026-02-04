"""LangChain callback handler for OpenTelemetry tracing."""

import logging
from typing import Any, Dict, List

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from rhesis.sdk.telemetry.attributes import AIAttributes, AIEvents
from rhesis.sdk.telemetry.context import is_llm_observation_active
from rhesis.sdk.telemetry.schemas import AIOperationType

from .extractors import (
    MAX_CONTENT_LENGTH,
    extract_agent_input,
    extract_agent_name,
    extract_agent_output,
    extract_tool_output,
    is_agent,
)
from .llm_processing import (
    add_chat_prompt_event,
    extract_and_set_tokens,
    set_llm_attributes,
)

logger = logging.getLogger(__name__)


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
            # Agent deduplication: track active agents to avoid nested duplicates
            self._active_agents: set = set()  # Currently active agent names
            self._agent_run_ids: Dict[str, str] = {}  # run_id -> agent_name mapping
            # Track agents for handoff detection
            self._current_agent: str | None = None
            self._last_ended_agent: str | None = None

        # =====================================================================
        # Span Management
        # =====================================================================

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

        # =====================================================================
        # LLM Callbacks
        # =====================================================================

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
            set_llm_attributes(span, serialized, kwargs, request_type="chat")
            add_chat_prompt_event(span, messages)
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
            set_llm_attributes(
                span, serialized, kwargs, request_type=serialized.get("_type", "llm")
            )

            if prompts:
                span.add_event(
                    AIEvents.PROMPT,
                    {
                        AIAttributes.PROMPT_ROLE: "user",
                        AIAttributes.PROMPT_CONTENT: prompts[0][:MAX_CONTENT_LENGTH],
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
                extract_and_set_tokens(span, response)
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

        # =====================================================================
        # Tool Callbacks
        # =====================================================================

        def on_tool_start(
            self,
            serialized: Dict[str, Any],
            input_str: str,
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Start tool span or handoff span."""
            run_id_str = str(run_id)
            if run_id_str in self._active_run_ids:
                return

            self._active_run_ids.add(run_id_str)
            tool_name = serialized.get("name", "unknown")

            # Detect handoff tools (transfer_to_* pattern)
            if tool_name.startswith("transfer_to_"):
                # Extract target agent from tool name
                target_agent = tool_name.replace("transfer_to_", "")

                span, parent_token, current_token = self._start_span(
                    AIOperationType.AGENT_HANDOFF, run_id, parent_run_id
                )

                span.set_attribute(
                    AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_AGENT_HANDOFF
                )
                if self._current_agent:
                    span.set_attribute(AIAttributes.AGENT_HANDOFF_FROM, self._current_agent)
                span.set_attribute(AIAttributes.AGENT_HANDOFF_TO, target_agent)
            else:
                # Regular tool invocation
                span, parent_token, current_token = self._start_span(
                    AIOperationType.TOOL_INVOKE, run_id, parent_run_id
                )

                span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_TOOL_INVOKE)
                span.set_attribute(AIAttributes.TOOL_NAME, tool_name)
                span.set_attribute(AIAttributes.TOOL_TYPE, "function")
                span.add_event(
                    AIEvents.TOOL_INPUT,
                    {AIAttributes.TOOL_INPUT_CONTENT: input_str[:MAX_CONTENT_LENGTH]},
                )

            self._spans[run_id_str] = (span, parent_token, current_token)

        def on_tool_end(
            self, output: Any, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
        ) -> None:
            """End tool span."""
            span_data = self._spans.get(str(run_id))
            if span_data:
                output_str = extract_tool_output(output)
                span_data[0].add_event(
                    AIEvents.TOOL_OUTPUT,
                    {AIAttributes.TOOL_OUTPUT_CONTENT: output_str[:MAX_CONTENT_LENGTH]},
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

        # =====================================================================
        # Agent Callbacks (for multi-agent systems)
        # =====================================================================

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

            # Skip if we've already processed this run
            if run_id_str in self._active_run_ids:
                return

            # Extract agent name
            agent_name = extract_agent_name(serialized, tags, metadata)

            # Only create spans for agents, skip everything else
            if not is_agent(agent_name, tags, metadata):
                return

            # Deduplicate: Only create one span per agent name at a time
            if agent_name in self._active_agents:
                return

            # Detect handoff: if a different agent is starting after another ended
            if (
                self._last_ended_agent
                and self._last_ended_agent != agent_name
                and self._last_ended_agent not in self._active_agents
            ):
                self._create_handoff_span(
                    from_agent=self._last_ended_agent,
                    to_agent=agent_name,
                    parent_run_id=parent_run_id,
                )
                self._last_ended_agent = None

            self._active_run_ids.add(run_id_str)
            self._active_agents.add(agent_name)
            self._agent_run_ids[run_id_str] = agent_name
            self._current_agent = agent_name

            span, parent_token, current_token = self._start_span(
                AIOperationType.AGENT_INVOKE, run_id, parent_run_id
            )

            span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_AGENT_INVOKE)
            span.set_attribute(AIAttributes.AGENT_NAME, agent_name)

            # Capture agent input
            input_str = extract_agent_input(inputs)
            if input_str:
                span.add_event(
                    AIEvents.AGENT_INPUT,
                    {AIAttributes.AGENT_INPUT_CONTENT: input_str[:MAX_CONTENT_LENGTH]},
                )

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
            run_id_str = str(run_id)
            span_data = self._spans.get(run_id_str)
            if span_data:
                # Capture agent output
                output_str = extract_agent_output(outputs)
                if output_str:
                    span_data[0].add_event(
                        AIEvents.AGENT_OUTPUT,
                        {AIAttributes.AGENT_OUTPUT_CONTENT: output_str[:MAX_CONTENT_LENGTH]},
                    )
                span_data[0].set_status(Status(StatusCode.OK))
                self._end_span(run_id)
                # Clear agent from active set and track for handoff detection
                if run_id_str in self._agent_run_ids:
                    agent_name = self._agent_run_ids.pop(run_id_str)
                    self._active_agents.discard(agent_name)
                    self._last_ended_agent = agent_name

        def on_chain_error(
            self,
            error: BaseException,
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Handle agent errors."""
            run_id_str = str(run_id)
            span_data = self._spans.get(run_id_str)
            if span_data:
                span_data[0].set_status(Status(StatusCode.ERROR, str(error)))
                span_data[0].record_exception(error)
                self._end_span(run_id)
                # Clear agent from active set
                if run_id_str in self._agent_run_ids:
                    agent_name = self._agent_run_ids.pop(run_id_str)
                    self._active_agents.discard(agent_name)

        # =====================================================================
        # Helper Methods
        # =====================================================================

        def _create_handoff_span(
            self, from_agent: str, to_agent: str, parent_run_id: Any = None
        ) -> None:
            """Create a handoff span to trace agent transitions."""
            import uuid

            handoff_run_id = str(uuid.uuid4())

            span, parent_token, current_token = self._start_span(
                AIOperationType.AGENT_HANDOFF, handoff_run_id, parent_run_id
            )

            span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_AGENT_HANDOFF)
            span.set_attribute(AIAttributes.AGENT_HANDOFF_FROM, from_agent)
            span.set_attribute(AIAttributes.AGENT_HANDOFF_TO, to_agent)

            # End the handoff span immediately (it's a point-in-time event)
            span.set_status(Status(StatusCode.OK))
            span.end()

            # Clean up context tokens
            if current_token:
                otel_context.detach(current_token)
            if parent_token:
                otel_context.detach(parent_token)

    return RhesisLangChainCallback()
