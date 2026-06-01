"""MCP integration service package."""

from rhesis.backend.app.services.tool.mcp.agents import get_agent_event_handlers
from rhesis.backend.app.services.tool.mcp.config import (
    _get_mcp_client_from_params,
    _get_mcp_tool_config,
)
from rhesis.backend.app.services.tool.mcp.exceptions import handle_mcp_exception
from rhesis.backend.app.services.tool.mcp.operations import extract_mcp, query_mcp, search_mcp
from rhesis.backend.app.services.tool.mcp.templates import jinja_env
from rhesis.backend.app.services.tool.mcp.workflows import (
    create_jira_ticket_from_task,
    run_mcp_authentication_test,
)

__all__ = [
    "get_agent_event_handlers",
    "_get_mcp_client_from_params",
    "_get_mcp_tool_config",
    "create_jira_ticket_from_task",
    "extract_mcp",
    "handle_mcp_exception",
    "jinja_env",
    "query_mcp",
    "run_mcp_authentication_test",
    "search_mcp",
]
