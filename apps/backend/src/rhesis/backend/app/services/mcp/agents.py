"""Agent factory helpers for MCP operations."""

import logging
from typing import List

from rhesis.sdk.agents.events import AgentEventHandler

logger = logging.getLogger(__name__)


def get_agent_event_handlers(model_name: str = "unknown") -> List[AgentEventHandler]:
    """Return [TracingHandler] when observability is enabled, [] otherwise.

    Args:
        model_name: LLM model identifier, recorded as ``ai.model.name`` on spans.
    """
    from rhesis.backend.app.utils.observability import rhesis_client

    if rhesis_client is not None and not getattr(rhesis_client, "is_disabled", False):
        from rhesis.sdk.agents.tracing import TracingHandler

        logger.info("OTel tracing enabled for MCP agent")
        return [TracingHandler(model_name=model_name)]

    logger.info("OTel tracing disabled for MCP agent")
    return []
