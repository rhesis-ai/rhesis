"""MCP service for generic integration using MCPAgent."""

import json
from pathlib import Path
from typing import Dict, List, Union

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

    Args:
        query: Search query string
        server_name: Name of the MCP server (e.g., "notionApi", "github")
        db: Database session
        user: Current user (for retrieving default generation model)

    Returns:
        List of dicts with 'id', 'url', and 'title' keys
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
    Extract content from MCP server item as markdown.

    Args:
        id: ID of the item to extract
        server_name: Name of the MCP server (e.g., "notionApi", "github")
        db: Database session
        user: Current user (for retrieving default generation model)

    Returns:
        Markdown content as string
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
    system_prompt: str = None,
    max_iterations: int = 10,
) -> Dict[str, any]:
    """
    General-purpose MCP query endpoint for arbitrary tasks.

    This is a flexible endpoint that can handle any MCP task without
    assumptions about the query or response format. Use this when you
    need the agent to perform tasks beyond the specialized search/extract
    endpoints.

    Args:
        query: User's query or task description
        server_name: Name of the MCP server (e.g., "notionApi", "github")
        db: Database session
        user: Current user (for retrieving default generation model)
        system_prompt: Custom system prompt (optional, uses default if None)
        max_iterations: Maximum reasoning iterations (default: 10)

    Returns:
        Dict with full agent execution details including:
        - final_answer: The agent's final response
        - success: Whether the task completed successfully
        - iterations_used: Number of iterations taken
        - execution_history: Full trace of agent reasoning and actions
        - error: Error message if task failed

    Example:
        >>> result = await query_mcp(
        ...     "Create a new page in Notion titled 'Meeting Notes'",
        ...     "notionApi",
        ...     db,
        ...     user
        ... )
        >>> print(result["final_answer"])
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

    return {
        "final_answer": result.final_answer,
        "success": result.success,
        "iterations_used": result.iterations_used,
        "max_iterations_reached": result.max_iterations_reached,
        "error": result.error,
        "execution_history": [
            {
                "iteration": step.iteration,
                "reasoning": step.reasoning,
                "action": step.action,
                "tool_calls": [
                    {"tool_name": tc.tool_name, "arguments": tc.arguments} for tc in step.tool_calls
                ],
                "tool_results": [
                    {
                        "tool_name": tr.tool_name,
                        "success": tr.success,
                        # Truncate long content
                        "content": tr.content[:500] if tr.success else None,
                        "error": tr.error,
                    }
                    for tr in step.tool_results
                ],
            }
            for step in result.execution_history
        ],
    }
