"""MCP service for generic integration using MCPAgent."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import jinja2
from sqlalchemy.orm import Session

from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.llm_utils import get_user_generation_model
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.mcp import MCPAgent, MCPClientManager

# Initialize Jinja2 environment for loading prompt templates
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=jinja2.select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


async def search_mcp(query: str, server_name: str, db: Session, user: User) -> List[Dict[str, str]]:
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
        ...     user
        ... )
        >>> print(results[0]["title"])
    """
    model: Union[str, BaseLLM] = get_user_generation_model(db, user)

    manager = MCPClientManager()
    client = manager.create_client(server_name)

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


async def extract_mcp(id: str, server_name: str, db: Session, user: User) -> str:
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

    Returns:
        Full item content formatted as markdown string

    Raises:
        ValueError: If extraction fails or item not found

    Example:
        >>> content = await extract_mcp(
        ...     "page-id-123",
        ...     "notionApi",
        ...     db,
        ...     user
        ... )
        >>> print(content[:100])  # First 100 chars
    """
    model: Union[str, BaseLLM] = get_user_generation_model(db, user)

    manager = MCPClientManager()
    client = manager.create_client(server_name)

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
        system_prompt: Custom agent instructions (optional)
        max_iterations: Maximum reasoning steps (default: 10)

    Returns:
        Dict with execution details and result

    Raises:
        ValueError: If task execution fails

    Example:
        >>> result = await query_mcp(
        ...     "Create a page titled 'Q1 Goals'",
        ...     "notionApi", db, user
        ... )
    """
    model: Union[str, BaseLLM] = get_user_generation_model(db, user)

    manager = MCPClientManager()
    client = manager.create_client(server_name)

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
