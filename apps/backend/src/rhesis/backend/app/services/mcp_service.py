"""MCP service for generic integration using MCPAgent."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import jinja2
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.llm_utils import get_user_generation_model
from rhesis.sdk.services.mcp import MCPAgent, MCPClientManager

# Initialize Jinja2 environment for loading prompt templates
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=jinja2.select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _get_mcp_client_for_tool(db: Session, organization_id: str, provider: str):
    """
    Get MCPClientManager from database configuration.

    Args:
        db: Database session
        organization_id: Organization ID
        provider: Tool provider value (e.g., 'notion', 'github')

    Returns:
        MCPClientManager configured from database tool

    Raises:
        ValueError: If tool not found or not an MCP integration
    """
    tool = crud.get_tool_by_provider(db, organization_id, provider)

    if not tool:
        raise ValueError(
            f"Tool provider '{provider}' not configured. Please add it in /integrations/tools"
        )

    # Verify tool type is MCP
    if tool.tool_type.type_value != "mcp":
        raise ValueError(f"Tool '{provider}' is not an MCP integration")

    # Create MCPClientManager with token substitution
    return MCPClientManager.from_tool_config(
        tool_name=f"{provider}Api",
        tool_config=tool.tool_metadata,
        auth_token=tool.auth_token,
    )


async def search_mcp(
    query: str, server_name: str, db: Session, user: User, organization_id: str
) -> List[Dict[str, str]]:
    """
    Search MCP server for items matching query.

    Uses an AI agent to intelligently search the MCP server and return
    structured results. The agent automatically determines the best search
    strategy based on the server's available tools.

    Args:
        query: Natural language search query (e.g., "Find pages about authentication")
        server_name: Name of the MCP server (e.g., "notionApi", "github")
        db: Database session
        user: Current user (for retrieving default generation model)
        organization_id: Organization ID for loading tools from database

    Returns:
        List of dicts, each containing:
        - id: Item identifier (required for extraction)
        - url: Direct link to the item
        - title: Human-readable title

    Raises:
        ValueError: If search fails or returns invalid JSON

    Example:
        >>> results = await search_mcp(
        ...     "pages created last week",
        ...     "notionApi",
        ...     db,
        ...     user,
        ...     org_id
        ... )
        >>> print(results[0]["title"])
    """
    model = get_user_generation_model(db, user)

    # Load MCP client from database tool configuration
    manager = _get_mcp_client_for_tool(db, organization_id, server_name)
    client = manager.create_client(f"{server_name}Api")

    search_prompt = jinja_env.get_template("mcp_search_prompt.jinja2").render()
    agent = MCPAgent(
        model=model,
        mcp_client=client,
        system_prompt=search_prompt,
        max_iterations=10,
        verbose=False,
    )

    result = await agent.run_async(query)

    if not result.success:
        raise ValueError(f"Search failed: {result.error}")

    return json.loads(result.final_answer)


async def extract_mcp(
    id: str, server_name: str, db: Session, user: User, organization_id: str
) -> str:
    """
    Extract full content from an MCP item as markdown.

    Uses an AI agent to retrieve and convert item content to markdown format.
    The agent navigates the item structure and extracts all relevant content
    including text, headings, lists, and nested blocks.

    Args:
        id: Item identifier (typically obtained from search_mcp results)
        server_name: Name of the MCP server (e.g., "notionApi", "github")
        db: Database session
        user: Current user (for retrieving default generation model)
        organization_id: Organization ID for loading tools from database

    Returns:
        Full item content formatted as markdown string

    Raises:
        ValueError: If extraction fails or item not found

    Example:
        >>> content = await extract_mcp(
        ...     "page-id-123",
        ...     "notionApi",
        ...     db,
        ...     user,
        ...     org_id
        ... )
        >>> print(content[:100])  # First 100 chars
    """
    model = get_user_generation_model(db, user)

    # Load MCP client from database tool configuration
    manager = _get_mcp_client_for_tool(db, organization_id, server_name)
    client = manager.create_client(f"{server_name}Api")

    extract_prompt = jinja_env.get_template("mcp_extract_prompt.jinja2").render()
    agent = MCPAgent(
        model=model,
        mcp_client=client,
        system_prompt=extract_prompt,
        max_iterations=15,
        verbose=False,
    )

    result = await agent.run_async(f"Extract content from item {id}")

    if not result.success:
        raise ValueError(f"Extraction failed: {result.error}")

    return result.final_answer


async def query_mcp(
    query: str,
    server_name: str,
    db: Session,
    user: User,
    organization_id: str,
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
        server_name: Name of the MCP server (e.g., "notionApi", "github")
        db: Database session
        user: Current user (for retrieving default generation model)
        organization_id: Organization ID for loading tools from database
        system_prompt: Custom agent instructions (optional)
        max_iterations: Maximum reasoning steps (default: 10)

    Returns:
        Dict with execution details and result

    Raises:
        ValueError: If task execution fails

    Example:
        >>> result = await query_mcp(
        ...     "Create a page titled 'Q1 Goals'",
        ...     "notionApi", db, user, org_id
        ... )
    """
    model = get_user_generation_model(db, user)

    # Load MCP client from database tool configuration
    manager = _get_mcp_client_for_tool(db, organization_id, server_name)
    client = manager.create_client(f"{server_name}Api")

    if not system_prompt:
        system_prompt = jinja_env.get_template("mcp_default_query_prompt.jinja2").render()

    agent = MCPAgent(
        model=model,
        mcp_client=client,
        system_prompt=system_prompt,
        max_iterations=max_iterations,
        verbose=False,
    )

    result = await agent.run_async(query)

    if not result.success:
        raise ValueError(f"Query failed: {result.error}")

    return result.model_dump()
