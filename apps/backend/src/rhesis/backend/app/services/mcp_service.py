"""MCP service for generic integration using MCPAgent."""

import json
import os
from typing import Dict, List

from rhesis.sdk.models import get_model
from rhesis.sdk.services.mcp import MCPAgent, MCPClientManager

SEARCH_PROMPT = """Search for items matching the query.
Return JSON array: [{"url": "item_url", "title": "Item Title"}]
Only include items actually found by API."""

EXTRACT_PROMPT = """Extract full content from the item as markdown.
Include all text, headings, and lists."""


async def search_mcp(query: str, server_name: str) -> List[Dict[str, str]]:
    """
    Search MCP server for items matching query.

    Args:
        query: Search query string
        server_name: Name of the MCP server (e.g., "notionApi", "github")

    Returns:
        List of dicts with 'url' and 'title' keys
    """
    llm = get_model(
        provider="gemini",
        model_name="gemini-2.0-flash-exp",
        api_key=os.getenv("GEMINI_API_KEY"),
    )

    manager = MCPClientManager()
    client = manager.create_client(server_name)

    agent = MCPAgent(
        llm=llm,
        mcp_client=client,
        system_prompt=SEARCH_PROMPT,
        max_iterations=10,
        verbose=False,
    )

    result = await agent.run_async(query)

    if not result.success:
        raise ValueError(f"Search failed: {result.error}")

    return json.loads(result.final_answer)


async def extract_mcp(item_id: str, server_name: str) -> str:
    """
    Extract content from MCP server item as markdown.

    Args:
        item_id: ID of the item to extract
        server_name: Name of the MCP server (e.g., "notionApi", "github")

    Returns:
        Markdown content as string
    """
    llm = get_model(
        provider="gemini",
        model_name="gemini-2.0-flash-exp",
        api_key=os.getenv("GEMINI_API_KEY"),
    )

    manager = MCPClientManager()
    client = manager.create_client(server_name)

    agent = MCPAgent(
        llm=llm,
        mcp_client=client,
        system_prompt=EXTRACT_PROMPT,
        max_iterations=15,
        verbose=False,
    )

    result = await agent.run_async(f"Extract content from item {item_id}")

    if not result.success:
        raise ValueError(f"Extraction failed: {result.error}")

    return result.final_answer
