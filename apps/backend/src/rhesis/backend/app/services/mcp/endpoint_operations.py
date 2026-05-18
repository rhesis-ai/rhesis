"""Decorated MCP search, extract, and query operations."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.constants import DEFAULT_GENERATION_MODEL
from rhesis.backend.app.utils.observability import get_test_context
from rhesis.sdk.decorators import endpoint

from .agents import _get_agent_class
from .config import _get_mcp_tool_config
from .templates import jinja_env

logger = logging.getLogger(__name__)


@endpoint(
    name="search_mcp",
    bind={
        # DEVELOPMENT ONLY: get_test_context() provides test bindings for remote testing.
        # Disabled by default in production (returns empty dict when env vars not set).
        # Only used by Rhesis developers during development.
        **get_test_context(),
        "tool_id": os.getenv("RHESIS_TOOL_ID"),
    },
    request_mapping={
        "query": "{{ input }}",
    },
    response_mapping={},
)
async def search_mcp(
    query: str, tool_id: str, db: Session, organization_id: str, user_id: str
) -> List[Dict[str, str]]:
    """
    Search MCP server for items matching query.

    Uses an AI agent to intelligently search the MCP server and return
    structured results. The agent automatically determines the best search
    strategy based on the server's available tools.

    Args:
        query: Natural language search query (e.g., "Find pages about authentication")
        tool_id: ID of the configured tool instance
        db: Database session
        organization_id: Organization ID for loading tools from database
        user_id: User ID for retrieving default generation model

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
        ...     db,
        ...     org_id,
        ...     user_id
        ... )
        >>> print(results[0]["title"])
    """
    if not user_id:
        raise ValueError("user_id is required")

    # Load MCP client from database tool configuration
    client, provider, repository_context = _get_mcp_tool_config(
        db, tool_id, organization_id, user_id
    )

    search_prompt = jinja_env.get_template("mcp_search_prompt.jinja2").render(
        provider=provider, repository_context=repository_context
    )

    # Use dynamic agent class based on RhesisClient availability
    AgentClass = _get_agent_class()
    agent = AgentClass(
        model=DEFAULT_GENERATION_MODEL,
        mcp_client=client,
        system_prompt=search_prompt,
        max_iterations=10,
        verbose=False,
    )

    result = await agent.run_async(query)

    logger.info(f"Raw Agent output: {repr(result.final_answer)}")

    # Parse response - agent returns list of items
    # (Fatal errors raise exceptions before reaching here)
    try:
        parsed_results = json.loads(result.final_answer)
        if not isinstance(parsed_results, list):
            raise ValueError("Agent returned invalid format: expected a list of items")
        return parsed_results
    except json.JSONDecodeError as e:
        raise ValueError(f"Agent returned invalid JSON: {str(e)}")


@endpoint(
    name="extract_mcp",
    bind={
        # DEVELOPMENT ONLY: get_test_context() provides test bindings for remote testing.
        # Disabled by default in production (returns empty dict when env vars not set).
        # Only used by Rhesis developers during development.
        **get_test_context(),
        "tool_id": os.getenv("RHESIS_TOOL_ID"),
    },
    request_mapping={
        "item_url": "{{ input }}",  # Map required 'input' field to item_url
        "item_id": "{{ item_id }}",  # Optional custom field for item_id
    },
    response_mapping={},
)
async def extract_mcp(
    item_id: Optional[str] = None,
    item_url: Optional[str] = None,
    tool_id: str = None,
    db: Session = None,
    organization_id: str = None,
    user_id: str = None,
) -> str:
    """
    Extract full content from an MCP item as markdown.

    Uses an AI agent to retrieve and convert item content to markdown format.
    The agent navigates the item structure and extracts all relevant content
    including text, headings, lists, and nested blocks.

    Args:
        item_id: Item identifier (optional, use if URL is not available)
        item_url: Item URL (optional, preferred if available)
        tool_id: ID of the configured tool instance
        db: Database session
        organization_id: Organization ID for loading tools from database
        user_id: User ID for retrieving default generation model

    Returns:
        Full item content formatted as markdown string

    Raises:
        ValueError: If extraction fails, item not found, or neither id nor url provided

    Example:
        >>> content = await extract_mcp(
        ...     item_id="page-id-123",
        ...     tool_id="tool-uuid-123",
        ...     db=db,
        ...     organization_id=org_id,
        ...     user_id=user_id
        ... )
        >>> print(content[:100])  # First 100 chars
    """
    if not item_id and not item_url:
        raise ValueError("Either 'item_id' or 'item_url' must be provided")

    if not user_id:
        raise ValueError("user_id is required")

    # Load MCP client and provider from database tool configuration
    client, provider, _ = _get_mcp_tool_config(db, tool_id, organization_id, user_id)

    extract_prompt = jinja_env.get_template("mcp_extract_prompt.jinja2").render(
        item_id=item_id,
        item_url=item_url,
        provider=provider,
    )

    # Use dynamic agent class based on RhesisClient availability
    AgentClass = _get_agent_class()
    agent = AgentClass(
        model=DEFAULT_GENERATION_MODEL,
        mcp_client=client,
        system_prompt=extract_prompt,
        max_iterations=15,
        verbose=False,
    )

    # Use URL if available, otherwise use ID for the prompt
    item_reference = item_url if item_url else item_id
    result = await agent.run_async(f"Extract content from item {item_reference}")

    # Parse response - agent returns content as text
    # (Fatal errors raise exceptions before reaching here)
    return result.final_answer


@endpoint(
    name="query_mcp",
    bind={
        # DEVELOPMENT ONLY: get_test_context() provides test bindings for remote testing.
        # Disabled by default in production (returns empty dict when env vars not set).
        # Only used by Rhesis developers during development.
        **get_test_context(),
        "tool_id": os.getenv("RHESIS_TOOL_ID"),
    },
    request_mapping={
        "query": "{{ input }}",
    },
    response_mapping={},
)
async def query_mcp(
    query: str,
    tool_id: str,
    db: Session,
    organization_id: str,
    user_id: str,
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
        db: Database session
        organization_id: Organization ID for loading tools from database
        user_id: User ID for retrieving default generation model
        system_prompt: Custom agent instructions (optional)
        max_iterations: Maximum reasoning steps (default: 10)

    Returns:
        Dict with execution details and result

    Raises:
        ValueError: If task execution fails

    Example:
        >>> result = await query_mcp(
        ...     "Create a page titled 'Q1 Goals'",
        ...     "tool-uuid-123", db, org_id, user_id
        ... )
    """
    if not user_id:
        raise ValueError("user_id is required")

    # Load MCP client from database tool configuration
    client, provider, repository_context = _get_mcp_tool_config(
        db, tool_id, organization_id, user_id
    )

    if not system_prompt:
        system_prompt = jinja_env.get_template("mcp_default_query_prompt.jinja2").render(
            provider=provider, repository_context=repository_context
        )

    # Use dynamic agent class based on RhesisClient availability
    AgentClass = _get_agent_class()
    agent = AgentClass(
        model=DEFAULT_GENERATION_MODEL,
        mcp_client=client,
        system_prompt=system_prompt,
        max_iterations=max_iterations,
        verbose=False,
    )

    result = await agent.run_async(query)

    # Agent now raises exceptions for errors, so if we get here, it succeeded
    return result.model_dump()
