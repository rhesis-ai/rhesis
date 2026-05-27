"""MCP agent class selection."""

import logging

from rhesis.sdk.services.mcp import MCPAgent
from rhesis.sdk.services.mcp.observable_agent import ObservableMCPAgent

logger = logging.getLogger(__name__)


def _get_agent_class():
    """
    Determine which agent class to use based on RhesisClient availability.

    Returns:
        ObservableMCPAgent if RhesisClient is available and not disabled, otherwise MCPAgent
    """
    from rhesis.backend.app.utils.observability import rhesis_client

    if rhesis_client is not None and not getattr(rhesis_client, "is_disabled", False):
        logger.info("Using ObservableMCPAgent for MCP operations (observability enabled)")
        return ObservableMCPAgent
    else:
        logger.info("Using standard MCPAgent for MCP operations (observability disabled)")
        return MCPAgent
