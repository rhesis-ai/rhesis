"""MCP search, extract, and query operations.

Plain backend helpers reachable via ``/mcp/*`` HTTP routes (see
``app/routers/services.py``).  Not SDK endpoints -- the platform does
not expose them over the SDK connector and they are not invoked as test
targets in this codebase.
"""

import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.config.settings import get_model_settings
from rhesis.backend.app.utils import observability as _observability  # noqa: F401
from rhesis.sdk.agents.mcp import MCPAgent

from .agents import get_agent_event_handlers
from .config import _get_mcp_tool_config
from .templates import jinja_env

logger = logging.getLogger(__name__)


async def search_mcp(
    query: str,
    tool_id: str,
    db: Session,
    organization_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Search MCP server for items matching ``query`` via an AI agent.

    Returns the agent result as a dict (``model_dump()`` of
    :class:`rhesis.sdk.agents.schemas.AgentResult`).  Callers that need
    the parsed item list (e.g. the ``/mcp/search`` HTTP route) should
    ``json.loads(result["final_answer"])``.

    Raises:
        ValueError: If search fails or returns invalid JSON.
    """
    if not user_id:
        raise ValueError("user_id is required")

    client, provider, repository_context = _get_mcp_tool_config(
        db, tool_id, organization_id, user_id
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


async def extract_mcp(
    db: Session,
    organization_id: str,
    user_id: str,
    item_id: Optional[str] = None,
    item_url: Optional[str] = None,
    tool_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract full content from an MCP item as markdown.

    Returns the agent result as a dict.  Callers that need only the
    markdown body should read ``result["final_answer"]``.

    Raises:
        ValueError: If extraction fails, item not found, or neither id
            nor url provided.
    """
    if not item_id and not item_url:
        raise ValueError("Either 'item_id' or 'item_url' must be provided")

    if not user_id:
        raise ValueError("user_id is required")

    client, provider, _ = _get_mcp_tool_config(db, tool_id, organization_id, user_id)

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


async def query_mcp(
    query: str,
    tool_id: str,
    db: Session,
    organization_id: str,
    user_id: str,
    system_prompt: Optional[str] = None,
    max_iterations: int = 10,
) -> Dict[str, Any]:
    """Execute arbitrary tasks on an MCP server with an AI agent.

    Full flexibility for any MCP task with custom prompts and detailed
    execution traces.  Use for complex operations like creating,
    updating, or analyzing content.

    Raises:
        ValueError: If task execution fails.
    """
    if not user_id:
        raise ValueError("user_id is required")

    client, provider, repository_context = _get_mcp_tool_config(
        db, tool_id, organization_id, user_id
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
