"""Microsoft AutoGen framework integration."""

import logging
from typing import Any, Callable, Optional

from rhesis.sdk.telemetry.integrations.base import BaseIntegration
from rhesis.sdk.telemetry.integrations.tracing_helpers import (
    add_agent_io_events,
    observe_framework_call,
    set_agent_attributes,
    set_token_attributes,
)

logger = logging.getLogger(__name__)

_original_generate_reply: Optional[Callable] = None
_original_a_generate_reply: Optional[Callable] = None
_patching_done = False


class AutoGenPatchState:
    """Accessor for AutoGen patching state (used in tests)."""

    @staticmethod
    def is_done() -> bool:
        return _patching_done

    @staticmethod
    def reset() -> None:
        global _original_generate_reply, _original_a_generate_reply, _patching_done
        if _patching_done and _original_generate_reply is not None:
            try:
                from autogen import ConversableAgent

                ConversableAgent.generate_reply = _original_generate_reply
                if _original_a_generate_reply is not None:
                    ConversableAgent.a_generate_reply = _original_a_generate_reply
            except ImportError:
                pass
        _original_generate_reply = None
        _original_a_generate_reply = None
        _patching_done = False


def _extract_model_from_agent(agent: Any) -> Optional[str]:
    llm_config = getattr(agent, "llm_config", None) or {}
    if not isinstance(llm_config, dict):
        return None
    config_list = llm_config.get("config_list") or []
    if config_list and isinstance(config_list[0], dict):
        model = config_list[0].get("model")
        if isinstance(model, str):
            return model
    return None


def _extract_usage_from_reply(reply: Any) -> Any:
    if isinstance(reply, dict):
        return reply.get("usage") or reply.get("token_usage")
    return getattr(reply, "usage", None)


def _wrap_generate_reply(original: Callable) -> Callable:
    def wrapped(self, *args, **kwargs):
        agent_name = getattr(self, "name", type(self).__name__)
        model = _extract_model_from_agent(self)
        messages = kwargs.get("messages")
        if messages is None and args:
            messages = args[0]

        with observe_framework_call(
            f"autogen.generate_reply {agent_name}",
            framework="autogen",
        ) as span:
            set_agent_attributes(span, agent_name=agent_name, model=model)
            result = original(self, *args, **kwargs)
            add_agent_io_events(span, messages, result)
            set_token_attributes(span, _extract_usage_from_reply(result))
            return result

    return wrapped


def _wrap_a_generate_reply(original: Callable) -> Callable:
    async def wrapped(self, *args, **kwargs):
        agent_name = getattr(self, "name", type(self).__name__)
        model = _extract_model_from_agent(self)
        messages = kwargs.get("messages")
        if messages is None and args:
            messages = args[0]

        with observe_framework_call(
            f"autogen.a_generate_reply {agent_name}",
            framework="autogen",
        ) as span:
            set_agent_attributes(span, agent_name=agent_name, model=model)
            result = await original(self, *args, **kwargs)
            add_agent_io_events(span, messages, result)
            set_token_attributes(span, _extract_usage_from_reply(result))
            return result

    return wrapped


def _patch_autogen() -> None:
    global _original_generate_reply, _original_a_generate_reply, _patching_done
    if _patching_done:
        return

    from autogen import ConversableAgent

    _original_generate_reply = ConversableAgent.generate_reply
    ConversableAgent.generate_reply = _wrap_generate_reply(_original_generate_reply)

    if hasattr(ConversableAgent, "a_generate_reply"):
        _original_a_generate_reply = ConversableAgent.a_generate_reply
        ConversableAgent.a_generate_reply = _wrap_a_generate_reply(_original_a_generate_reply)

    _patching_done = True


class AutoGenIntegration(BaseIntegration):
    """Microsoft AutoGen framework integration."""

    @property
    def framework_name(self) -> str:
        return "autogen"

    def is_installed(self) -> bool:
        try:
            import autogen  # noqa: F401

            return True
        except ImportError:
            return False

    def _create_callback(self):
        """Patch AutoGen agent entry points for automatic tracing."""
        _patch_autogen()
        return "autogen_patched"

    def enable(self) -> bool:
        if self._enabled:
            logger.debug("autogen observation already enabled")
            return True

        if not self.is_installed():
            logger.debug("autogen not installed")
            return False

        try:
            self._callback = self._create_callback()
            self._enabled = True
            logger.info("✓ Observing autogen")
            return True
        except Exception as exc:
            logger.warning(f"Failed to enable autogen: {exc}")
            return False

    def disable(self) -> None:
        if self._enabled:
            AutoGenPatchState.reset()
        super().disable()


_autogen_integration = AutoGenIntegration()


def get_integration() -> AutoGenIntegration:
    """Get the singleton AutoGen integration instance."""
    return _autogen_integration
