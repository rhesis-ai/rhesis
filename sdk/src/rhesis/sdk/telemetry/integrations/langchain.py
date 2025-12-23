"""LangChain framework integration."""

import logging
from typing import Any, Dict, List, Optional

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from rhesis.sdk.telemetry.attributes import AIAttributes, AIEvents
from rhesis.sdk.telemetry.integrations.base import BaseIntegration
from rhesis.sdk.telemetry.schemas import AIOperationType
from rhesis.sdk.telemetry.utils import (
    extract_token_usage,
    identify_provider_from_class_name,
    identify_provider_from_model_name,
)

logger = logging.getLogger(__name__)


class LangChainIntegration(BaseIntegration):
    """LangChain framework integration."""

    @property
    def framework_name(self) -> str:
        return "langchain"

    def is_installed(self) -> bool:
        """Check if LangChain is installed."""
        try:
            import langchain_core  # noqa: F401

            return True
        except ImportError:
            return False

    def _create_callback(self):
        """Create LangChain callback handler."""
        try:
            # LangChain 1.0+ (callbacks in langchain_core)
            from langchain_core.callbacks.base import BaseCallbackHandler
        except ImportError:
            # LangChain < 1.0 (fallback to old path)
            from langchain.callbacks.base import BaseCallbackHandler

        class RhesisLangChainCallback(BaseCallbackHandler):
            """Rhesis OpenTelemetry callback for LangChain."""

            def __init__(self):
                super().__init__()
                self.tracer = trace.get_tracer(__name__)
                self._spans: Dict[str, trace.Span] = {}

            def on_llm_start(
                self,
                serialized: Dict[str, Any],
                prompts: List[str],
                *,
                run_id: Any,
                parent_run_id: Any = None,
                **kwargs: Any,
            ) -> None:
                """Start LLM span."""
                span = self.tracer.start_span(
                    name=AIOperationType.LLM_INVOKE,
                    kind=SpanKind.CLIENT,
                )

                # Use centralized attribute constants
                span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_LLM_INVOKE)

                # Extract model name and provider using robust methods
                model_name = self._extract_model_name(serialized, kwargs)
                span.set_attribute(AIAttributes.MODEL_NAME, model_name)
                span.set_attribute(AIAttributes.LLM_REQUEST_TYPE, serialized.get("_type", "llm"))

                provider = self._extract_provider(serialized, kwargs)
                if provider:
                    span.set_attribute(AIAttributes.MODEL_PROVIDER, provider)

                # Add prompt as event using centralized constants
                if prompts:
                    span.add_event(
                        name=AIEvents.PROMPT,
                        attributes={
                            AIAttributes.PROMPT_ROLE: "user",
                            AIAttributes.PROMPT_CONTENT: prompts[0][:1000],
                        },
                    )

                self._spans[str(run_id)] = span

            def on_llm_end(
                self,
                response: Any,
                *,
                run_id: Any,
                parent_run_id: Any = None,
                **kwargs: Any,
            ) -> None:
                """End LLM span with token counts."""
                span = self._spans.get(str(run_id))
                if not span:
                    return

                try:
                    logger.info(f"🔍 LangChain on_llm_end called for run_id={run_id}")
                    logger.debug(
                        f"Response type: {type(response).__name__}, "
                        f"Has llm_output: {hasattr(response, 'llm_output')}, "
                        f"Has generations: {hasattr(response, 'generations')}"
                    )

                    # ============================================================================
                    # TOKEN EXTRACTION - PROVIDER-AGNOSTIC APPROACH
                    # ============================================================================
                    # Token extraction logic is in utils/token_extraction.py
                    # This allows it to be reused by other framework integrations
                    # (LlamaIndex, Haystack, direct API calls, etc.)
                    input_tokens = 0
                    output_tokens = 0
                    total_tokens = 0

                    # Strategy 1: Check response.llm_output.token_usage
                    if hasattr(response, "llm_output") and response.llm_output:
                        token_usage = response.llm_output.get("token_usage", {})
                        if token_usage:
                            input_tokens, output_tokens, total_tokens = extract_token_usage(
                                token_usage
                            )

                    # Extract completion and check for tokens in generation_info
                    if hasattr(response, "generations") and response.generations:
                        first_gen = response.generations[0][0]

                        # Extract completion text
                        if hasattr(first_gen, "text"):
                            span.add_event(
                                name=AIEvents.COMPLETION,
                                attributes={AIAttributes.COMPLETION_CONTENT: first_gen.text[:1000]},
                            )
                        elif hasattr(first_gen, "message") and hasattr(
                            first_gen.message, "content"
                        ):
                            # Some providers use message.content instead of text
                            span.add_event(
                                name=AIEvents.COMPLETION,
                                attributes={
                                    AIAttributes.COMPLETION_CONTENT: str(first_gen.message.content)[
                                        :1000
                                    ]
                                },
                            )

                        # Strategy 2: Check message.usage_metadata
                        if (
                            not total_tokens
                            and hasattr(first_gen, "message")
                            and hasattr(first_gen.message, "usage_metadata")
                        ):
                            usage_metadata = first_gen.message.usage_metadata
                            if usage_metadata:
                                input_tokens, output_tokens, total_tokens = extract_token_usage(
                                    usage_metadata
                                )

                        # Strategy 3: Check generation_info (fallback)
                        if hasattr(first_gen, "generation_info") and first_gen.generation_info:
                            gen_info = first_gen.generation_info

                            # Extract finish reason (metadata, not token usage)
                            finish_reason = gen_info.get("finish_reason")
                            if finish_reason:
                                span.set_attribute(AIAttributes.LLM_FINISH_REASON, finish_reason)

                            # If we haven't found tokens yet, check generation_info
                            if not total_tokens:
                                # Try usage_metadata nested object
                                usage_metadata = gen_info.get("usage_metadata", {})
                                if usage_metadata:
                                    (
                                        input_tokens,
                                        output_tokens,
                                        total_tokens,
                                    ) = extract_token_usage(usage_metadata)

                                # Try token_usage nested object (alternative structure)
                                if not total_tokens:
                                    token_usage = gen_info.get("token_usage", {})
                                    if token_usage:
                                        (
                                            input_tokens,
                                            output_tokens,
                                            total_tokens,
                                        ) = extract_token_usage(token_usage)

                    # Set token attributes if we found any
                    if total_tokens > 0 or input_tokens > 0 or output_tokens > 0:
                        logger.debug(
                            f"Setting token attributes: input={input_tokens}, "
                            f"output={output_tokens}, total={total_tokens}"
                        )
                        span.set_attribute(AIAttributes.LLM_TOKENS_INPUT, input_tokens)
                        span.set_attribute(AIAttributes.LLM_TOKENS_OUTPUT, output_tokens)
                        span.set_attribute(
                            AIAttributes.LLM_TOKENS_TOTAL,
                            total_tokens or (input_tokens + output_tokens),
                        )
                    else:
                        # Log when tokens aren't found
                        resp_type = type(response).__name__
                        logger.debug(f"No token usage for LLM response (type: {resp_type})")

                    span.set_status(Status(StatusCode.OK))
                finally:
                    span.end()
                    del self._spans[str(run_id)]

            def on_llm_error(
                self,
                error: Exception,
                *,
                run_id: Any,
                parent_run_id: Any = None,
                **kwargs: Any,
            ) -> None:
                """Handle LLM errors."""
                span = self._spans.get(str(run_id))
                if span:
                    span.set_status(Status(StatusCode.ERROR, str(error)))
                    span.record_exception(error)
                    span.end()
                    del self._spans[str(run_id)]

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
                span = self.tracer.start_span(
                    name=AIOperationType.TOOL_INVOKE,
                    kind=SpanKind.CLIENT,
                )

                span.set_attribute(AIAttributes.OPERATION_TYPE, AIAttributes.OPERATION_TOOL_INVOKE)
                span.set_attribute(AIAttributes.TOOL_NAME, serialized.get("name", "unknown"))
                span.set_attribute(AIAttributes.TOOL_TYPE, "function")

                span.add_event(
                    name=AIEvents.TOOL_INPUT,
                    attributes={AIAttributes.TOOL_INPUT_CONTENT: input_str[:1000]},
                )

                self._spans[str(run_id)] = span

            def on_tool_end(
                self,
                output: str,
                *,
                run_id: Any,
                parent_run_id: Any = None,
                **kwargs: Any,
            ) -> None:
                """End tool span."""
                span = self._spans.get(str(run_id))
                if span:
                    span.add_event(
                        name=AIEvents.TOOL_OUTPUT,
                        attributes={AIAttributes.TOOL_OUTPUT_CONTENT: output[:1000]},
                    )
                    span.set_status(Status(StatusCode.OK))
                    span.end()
                    del self._spans[str(run_id)]

            def on_tool_error(
                self,
                error: Exception,
                *,
                run_id: Any,
                parent_run_id: Any = None,
                **kwargs: Any,
            ) -> None:
                """Handle tool errors."""
                span = self._spans.get(str(run_id))
                if span:
                    span.set_status(Status(StatusCode.ERROR, str(error)))
                    span.record_exception(error)
                    span.end()
                    del self._spans[str(run_id)]

            @staticmethod
            def _extract_model_name(serialized: Dict, kwargs: Dict) -> str:
                """
                Extract model name from LangChain invocation.

                Priority:
                1. Model parameter from kwargs (most accurate - actual model ID)
                2. Model parameter from serialized kwargs
                3. Class name from serialized (fallback)
                """
                # Check invocation kwargs first
                if "model" in kwargs:
                    return str(kwargs["model"])

                # Check serialized kwargs
                if "kwargs" in serialized and isinstance(serialized["kwargs"], dict):
                    if "model" in serialized["kwargs"]:
                        return str(serialized["kwargs"]["model"])
                    if "model_name" in serialized["kwargs"]:
                        return str(serialized["kwargs"]["model_name"])

                # Fallback to class name
                return serialized.get("name", "unknown")

            @staticmethod
            def _extract_provider(serialized: Dict, kwargs: Dict) -> Optional[str]:
                """
                Extract provider from model info using multiple strategies.

                Strategy priority:
                1. Check module path (LangChain-specific, most reliable)
                2. Use shared utilities for class/model name matching
                3. Check invocation kwargs

                Universal provider identification logic is in utils/provider_detection.py
                """
                # Strategy 1: Check module path (LangChain-specific, most reliable)
                module_path = ""
                if "id" in serialized and isinstance(serialized["id"], list):
                    # Format: ["langchain", "chat_models", "openai", "ChatOpenAI"]
                    module_path = ".".join(serialized["id"]).lower()
                elif "kwargs" in serialized and "_type" in serialized["kwargs"]:
                    module_path = serialized["kwargs"]["_type"].lower()

                # Map module paths to providers (LangChain-specific patterns)
                if "openai" in module_path or "langchain_openai" in module_path:
                    return "openai"
                elif "anthropic" in module_path or "langchain_anthropic" in module_path:
                    return "anthropic"
                elif "google" in module_path or "langchain_google" in module_path:
                    return "google"
                elif "cohere" in module_path or "langchain_cohere" in module_path:
                    return "cohere"
                elif "huggingface" in module_path or "langchain_huggingface" in module_path:
                    return "huggingface"
                elif (
                    "aws" in module_path
                    or "bedrock" in module_path
                    or "langchain_aws" in module_path
                ):
                    return "aws"
                elif "azure" in module_path:
                    return "azure"
                elif "mistral" in module_path or "langchain_mistralai" in module_path:
                    return "mistralai"

                # Strategy 2: Use shared utility for class name matching
                class_name = serialized.get("name", "")
                if class_name:
                    provider = identify_provider_from_class_name(class_name)
                    if provider:
                        return provider

                # Strategy 3: Use shared utility for model parameter hints
                if "model" in kwargs:
                    provider = identify_provider_from_model_name(str(kwargs["model"]))
                    if provider:
                        return provider

                return "unknown"

        return RhesisLangChainCallback()

    def enable(self) -> bool:
        """
        Enable observation for LangChain.

        This registers the callback globally using LangChain's configure() method.

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

            # Configure globally using LangChain's configure() method
            try:
                # LangChain 1.0+ approach
                from langchain_core.callbacks.manager import CallbackManager
                from langchain_core.globals import set_default_callback_manager

                # Create callback manager with our handler
                callback_manager = CallbackManager(handlers=[self._callback])
                set_default_callback_manager(callback_manager)

                logger.debug("Configured LangChain callback via set_default_callback_manager")
            except (ImportError, AttributeError) as e:
                logger.debug(f"Could not use set_default_callback_manager: {e}")
                # Fallback: try to add to existing global callbacks
                try:
                    from langchain_core.callbacks import manager as callback_module

                    if hasattr(callback_module, "_default_callback_manager"):
                        if callback_module._default_callback_manager is None:
                            from langchain_core.callbacks.manager import CallbackManager

                            callback_module._default_callback_manager = CallbackManager(
                                handlers=[self._callback]
                            )
                        else:
                            callback_module._default_callback_manager.add_handler(self._callback)
                        logger.debug("Added callback to _default_callback_manager")
                except Exception as e2:
                    logger.debug(f"Fallback also failed: {e2}")

            self._enabled = True
            logger.info(f"✓ Observing {self.framework_name}")
            return True
        except Exception as e:
            logger.warning(f"Failed to enable {self.framework_name}: {e}")
            logger.debug(f"Full error: {e}", exc_info=True)
            return False


# Singleton instance
_langchain_integration = LangChainIntegration()


def get_integration() -> LangChainIntegration:
    """Get the singleton LangChain integration instance."""
    return _langchain_integration
