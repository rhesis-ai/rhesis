"""Pydantic AI framework integration."""

import logging
from typing import Any, Callable, Optional

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from rhesis.sdk.telemetry.attributes import MAX_CONTENT_LENGTH, AIAttributes, AIEvents
from rhesis.sdk.telemetry.context import is_tracing_disabled
from rhesis.sdk.telemetry.integrations.base import BaseIntegration
from rhesis.telemetry.schemas import AIOperationType

logger = logging.getLogger(__name__)

# Module-level state for Agent patching (singleton pattern)
_original_agent_run: Callable | None = None
_agent_patching_done: bool = False


class AgentPatchState:
    """Accessor for Agent.run patching state."""

    @staticmethod
    def get_run() -> Callable | None:
        return _original_agent_run

    @staticmethod
    def set_run(func: Callable) -> None:
        global _original_agent_run
        _original_agent_run = func

    @staticmethod
    def is_done() -> bool:
        return _agent_patching_done

    @staticmethod
    def set_done(done: bool = True) -> None:
        global _agent_patching_done
        _agent_patching_done = done


def _extract_user_prompt(args: tuple, kwargs: dict) -> Optional[str]:
    """Extract a safe-to-log text representation of the user_prompt argument.

    user_prompt is usually a plain string, but when files are attached it can
    be a list mixing text with multimodal parts (BinaryContent, ImageUrl, ...).
    Those parts must never be passed through str() directly - their repr can
    embed the raw attachment bytes (or signed URLs) verbatim, which would leak
    file content into the OTel span sent to the backend. Binary/file parts are
    replaced with a small placeholder instead.
    """
    prompt = args[0] if args else kwargs.get("user_prompt")
    if prompt is None:
        return None
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, (list, tuple)):
        parts = []
        for part in prompt:
            if isinstance(part, str):
                parts.append(part)
            else:
                kind = getattr(part, "kind", None) or type(part).__name__
                parts.append(f"<attachment: {kind}>")
        return " ".join(parts)
    return str(prompt)


def _record_run_start(span: trace.Span, agent: Any, user_prompt: Optional[str]) -> None:
    """Set agent/model attributes and add the prompt event on the span."""
    span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_AGENT_INVOKE)

    agent_name = getattr(agent, "name", None)
    if agent_name:
        span.set_attribute(AIAttributes.AGENT_NAME, agent_name)

    model = getattr(agent, "model", None)
    model_name = getattr(model, "model_name", None)
    if model_name:
        span.set_attribute(AIAttributes.MODEL_NAME, str(model_name))

    # model.system is not a documented public API; fall back to the model
    # class module (pydantic_ai.models.openai -> "openai") so the provider
    # degrades gracefully rather than disappearing if the attribute changes.
    provider = getattr(model, "system", None)
    if not provider and model is not None and not isinstance(model, str):
        provider = type(model).__module__.rsplit(".", 1)[-1]
    if provider:
        span.set_attribute(AIAttributes.MODEL_PROVIDER, str(provider))

    if user_prompt:
        span.add_event(
            AIEvents.PROMPT,
            {
                AIAttributes.PROMPT_ROLE: "user",
                AIAttributes.PROMPT_CONTENT: user_prompt[:MAX_CONTENT_LENGTH],
            },
        )


def _record_run_end(span: trace.Span, result: Any) -> None:
    """Record output content and token usage from an AgentRunResult."""
    output = getattr(result, "output", None)
    if output is not None:
        span.set_attribute(AIAttributes.COMPLETION_OUTPUT_TYPE, type(output).__name__)
        # Structured outputs keep their shape via JSON instead of repr()
        content = None
        dump = getattr(output, "model_dump_json", None)
        if callable(dump):
            try:
                content = dump()
            except Exception:
                content = None
        if content is None:
            content = str(output)
        span.add_event(
            AIEvents.COMPLETION,
            {AIAttributes.COMPLETION_CONTENT: content[:MAX_CONTENT_LENGTH]},
        )

    # usage is a method on AgentRunResult today; tolerate it becoming a
    # property so token counts don't silently stop being recorded.
    usage_attr = getattr(result, "usage", None)
    usage = usage_attr() if callable(usage_attr) else usage_attr
    if usage:
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        if input_tokens or output_tokens:
            span.set_attribute(AIAttributes.LLM_TOKENS_INPUT, input_tokens)
            span.set_attribute(AIAttributes.LLM_TOKENS_OUTPUT, output_tokens)
            span.set_attribute(AIAttributes.LLM_TOKENS_TOTAL, input_tokens + output_tokens)

    span.set_status(Status(StatusCode.OK))


def _record_run_error(span: trace.Span, error: Exception) -> None:
    """Record an error on the span."""
    span.set_status(Status(StatusCode.ERROR, str(error)))
    span.record_exception(error)


class PydanticAIIntegration(BaseIntegration):
    """
    Pydantic AI framework integration.

    Pydantic AI has no callback system like LangChain, so this integration
    patches Agent.run directly (the same monkey-patching approach used by
    LangGraphIntegration for CompiledGraph). run_sync() is not patched
    separately - its implementation is a thin `run_until_complete(self.run(...))`
    wrapper, so patching run() alone also instruments every run_sync() call
    without creating a duplicate nested span. Each patched call is wrapped in
    an OpenTelemetry span capturing input/output, token usage, model name,
    latency, and errors - no manual @observe calls required.
    """

    @property
    def framework_name(self) -> str:
        return "pydantic_ai"

    def is_installed(self) -> bool:
        """Check if Pydantic AI is installed."""
        try:
            import pydantic_ai  # noqa: F401

            return True
        except ImportError:
            return False

    def _create_callback(self) -> trace.Tracer:
        """Create the OpenTelemetry tracer used to wrap Agent runs."""
        return trace.get_tracer(__name__)

    def enable(self) -> bool:
        """
        Enable observation for Pydantic AI.

        Patches Agent.run to wrap every call (including run_sync, which
        delegates to run internally) in an OpenTelemetry span.

        Returns:
            True if successfully enabled, False if not installed
        """
        if self._enabled:
            logger.debug(f"{self.framework_name} observation already enabled")
            return True

        if not self.is_installed():
            logger.debug(f"{self.framework_name} not installed")
            return False

        try:
            self._callback = self._create_callback()
            self._patch_agent()
            self._enabled = True
            logger.info(f"✓ Observing {self.framework_name}")
            return True
        except Exception as e:
            logger.warning(f"⚠️  Could not enable {self.framework_name} observation: {e}")
            logger.debug("   Full error:", exc_info=True)
            return False

    def _patch_agent(self) -> None:
        """Patch Agent.run to wrap calls in OpenTelemetry spans."""
        if AgentPatchState.is_done():
            return

        from pydantic_ai import Agent

        tracer = self._callback

        AgentPatchState.set_run(Agent.run)

        async def patched_run(self_agent: Any, *args: Any, **kwargs: Any) -> Any:
            if is_tracing_disabled():
                return await AgentPatchState.get_run()(self_agent, *args, **kwargs)

            user_prompt = _extract_user_prompt(args, kwargs)
            with tracer.start_as_current_span(
                AIOperationType.AGENT_INVOKE, kind=SpanKind.CLIENT
            ) as span:
                _record_run_start(span, self_agent, user_prompt)
                try:
                    result = await AgentPatchState.get_run()(self_agent, *args, **kwargs)
                    _record_run_end(span, result)
                    return result
                except Exception as e:
                    _record_run_error(span, e)
                    raise

        Agent.run = patched_run

        AgentPatchState.set_done()
        logger.debug("Patched Agent.run for automatic span creation")


# Singleton instance
_pydantic_ai_integration = PydanticAIIntegration()


def get_integration() -> PydanticAIIntegration:
    """Get the singleton Pydantic AI integration instance."""
    return _pydantic_ai_integration
