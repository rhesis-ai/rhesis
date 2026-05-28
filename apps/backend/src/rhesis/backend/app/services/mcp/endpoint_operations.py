"""Decorated MCP search, extract, and query operations."""

import json
import logging
from typing import Any, Dict, Optional

from rhesis.backend.app.config.settings import get_model_settings
from rhesis.backend.app.services.local_function_registry import (
    LocalInvocationContext,
    register_local,
)
from rhesis.backend.app.utils import observability as _observability  # noqa: F401
from rhesis.sdk.agents.mcp import MCPAgent
from rhesis.sdk.decorators import endpoint

from .agents import get_agent_event_handlers
from .config import _get_mcp_tool_config
from .templates import jinja_env

logger = logging.getLogger(__name__)


@endpoint(
    name="search_mcp",
    request_mapping={
        "query": "{{ input }}",
    },
    response_mapping={
        "output": "$.final_answer",
        "tool_calls": "$.execution_history",
        "metadata": {
            "iterations_used": "$.iterations_used",
            "max_iterations_reached": "$.max_iterations_reached",
            "success": "$.success",
        },
    },
)
async def search_mcp(
    query: str,
    tool_id: str,
    ctx: LocalInvocationContext,
) -> Dict[str, Any]:
    """
    Search MCP server for items matching query.

    Uses an AI agent to intelligently search the MCP server and return
    structured results. The agent automatically determines the best search
    strategy based on the server's available tools.

    Args:
        query: Natural language search query (e.g., "Find pages about authentication")
        tool_id: ID of the configured tool instance
        ctx: Invocation context containing organization_id, user_id, and db session

    Returns:
        List of dicts, each containing:
        - id: Item identifier
        - url: Direct link to the item
        - title: Human-readable title

    Raises:
        ValueError: If search fails or returns invalid JSON

    Example:
        >>> results = await search_mcp(
        ...     "pages created last week",
        ...     "tool-uuid-123",
        ...     ctx,
        ... )
        >>> print(results[0]["title"])
    """
    if not ctx.user_id:
        raise ValueError("user_id is required")

    client, provider, repository_context = _get_mcp_tool_config(
        ctx.db, tool_id, ctx.organization_id, ctx.user_id
    )

    search_prompt = jinja_env.get_template("mcp_search_prompt.jinja2").render(
        provider=provider, repository_context=repository_context
    )

    model = get_model_settings().generation_model
    agent = MCPAgent(
        model=model,
        mcp_client=client,
        system_prompt=search_prompt,
        max_iterations=10,
        verbose=False,
        event_handlers=get_agent_event_handlers(
            model_name=getattr(model, "model_name", None) or str(model),
            agent_name="mcp-search",
        ),
    )

    result = await agent.run_async(query)

    logger.info(f"Raw Agent output: {repr(result.final_answer)}")

    try:
        parsed_results = json.loads(result.final_answer)
        if not isinstance(parsed_results, list):
            raise ValueError("Agent returned invalid format: expected a list of items")
    except json.JSONDecodeError as e:
        raise ValueError(f"Agent returned invalid JSON: {str(e)}")

    return result.model_dump()


register_local(search_mcp)


@endpoint(
    name="extract_mcp",
    request_mapping={
        "item_url": "{{ input }}",
        "item_id": "{{ item_id }}",
    },
    response_mapping={
        "output": "$.final_answer",
        "tool_calls": "$.execution_history",
        "metadata": {
            "iterations_used": "$.iterations_used",
            "max_iterations_reached": "$.max_iterations_reached",
            "success": "$.success",
        },
    },
)
async def extract_mcp(
    ctx: LocalInvocationContext,
    item_id: Optional[str] = None,
    item_url: Optional[str] = None,
    tool_id: str = None,
) -> Dict[str, Any]:
    """
    Extract full content from an MCP item as markdown.

    Uses an AI agent to retrieve and convert item content to markdown format.
    The agent navigates the item structure and extracts all relevant content
    including text, headings, lists, and nested blocks.

    Args:
        ctx: Invocation context containing organization_id, user_id, and db session
        item_id: Item identifier (optional, use if URL is not available)
        item_url: Item URL (optional, preferred if available)
        tool_id: ID of the configured tool instance

    Returns:
        Full item content formatted as markdown string

    Raises:
        ValueError: If extraction fails, item not found, or neither id nor url provided

    Example:
        >>> content = await extract_mcp(
        ...     ctx,
        ...     item_id="page-id-123",
        ...     tool_id="tool-uuid-123",
        ... )
        >>> print(content[:100])
    """
    if not item_id and not item_url:
        raise ValueError("Either 'item_id' or 'item_url' must be provided")

    if not ctx.user_id:
        raise ValueError("user_id is required")

    client, provider, _ = _get_mcp_tool_config(ctx.db, tool_id, ctx.organization_id, ctx.user_id)

    extract_prompt = jinja_env.get_template("mcp_extract_prompt.jinja2").render(
        item_id=item_id,
        item_url=item_url,
        provider=provider,
    )

    model = get_model_settings().generation_model
    agent = MCPAgent(
        model=model,
        mcp_client=client,
        system_prompt=extract_prompt,
        max_iterations=15,
        verbose=False,
        event_handlers=get_agent_event_handlers(
            model_name=getattr(model, "model_name", None) or str(model),
            agent_name="mcp-extract",
        ),
    )

    item_reference = item_url if item_url else item_id
    result = await agent.run_async(f"Extract content from item {item_reference}")

    return result.model_dump()


register_local(extract_mcp)


@endpoint(
    name="query_mcp",
    request_mapping={
        "query": "{{ input }}",
    },
    response_mapping={
        "output": "{{ final_answer }}",
        "tool_calls": "$.execution_history",
        "metadata": {
            "iterations_used": "$.iterations_used",
            "max_iterations_reached": "$.max_iterations_reached",
            "success": "$.success",
        },
    },
)
async def query_mcp(
    query: str,
    tool_id: str,
    ctx: LocalInvocationContext,
    system_prompt: Optional[str] = None,
    max_iterations: int = 10,
) -> Dict[str, Any]:
    """
    Execute arbitrary tasks on an MCP server using an AI agent.

    Unlike search/extract endpoints, this provides full flexibility for any
    MCP task with custom prompts and detailed execution traces. Use this for
    complex operations like creating, updating, or analyzing content.

    Args:
        query: Natural language task description
        tool_id: ID of the configured tool instance
        ctx: Invocation context containing organization_id, user_id, and db session
        system_prompt: Custom agent instructions (optional)
        max_iterations: Maximum reasoning steps (default: 10)

    Returns:
        Dict with execution details and result

    Raises:
        ValueError: If task execution fails

    Example:
        >>> result = await query_mcp(
        ...     "Create a page titled 'Q1 Goals'",
        ...     "tool-uuid-123",
        ...     ctx,
        ... )
    """
    if not ctx.user_id:
        raise ValueError("user_id is required")

    client, provider, repository_context = _get_mcp_tool_config(
        ctx.db, tool_id, ctx.organization_id, ctx.user_id
    )

    if not system_prompt:
        system_prompt = jinja_env.get_template("mcp_default_query_prompt.jinja2").render(
            provider=provider, repository_context=repository_context
        )

    model = get_model_settings().generation_model
    agent = MCPAgent(
        model=model,
        mcp_client=client,
        system_prompt=system_prompt,
        max_iterations=max_iterations,
        verbose=False,
        event_handlers=get_agent_event_handlers(
            model_name=getattr(model, "model_name", None) or str(model),
            agent_name="mcp-query",
        ),
    )

    result = await agent.run_async(query)

    return result.model_dump()


register_local(query_mcp)
