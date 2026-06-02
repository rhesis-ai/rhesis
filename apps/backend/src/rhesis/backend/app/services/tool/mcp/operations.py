"""MCP search, extract, and query operations.

Each function is decorated with ``@endpoint`` so the SDK connector
can register it for remote invocation (Playground / test runs).
The ``/mcp/*`` HTTP routes in ``app/routers/services.py`` call the
functions directly, constructing an :class:`EndpointContext` from
the DI-injected tenant info.
"""

import json
import logging
import uuid
from typing import Any, Dict, Optional

from rhesis.backend.app import crud
from rhesis.backend.app.config.settings import get_model_settings
from rhesis.backend.app.utils import observability as _observability  # noqa: F401
from rhesis.sdk.agents.mcp import MCPAgent
from rhesis.sdk.context import EndpointContext
from rhesis.sdk.decorators import endpoint

from .agents import get_agent_event_handlers
from ..rest.config import get_rest_source
from .config import _get_mcp_tool_config
from .templates import jinja_env

logger = logging.getLogger(__name__)


@endpoint(
    name="search_mcp",
    request_mapping={
        "query": "{{ input }}",
        "tool_id": "{{ tool_id }}",
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
    ctx: EndpointContext,
) -> Dict[str, Any]:
    """Search MCP server for items matching ``query`` via an AI agent.

    Returns the agent result as a dict (``model_dump()`` of
    :class:`rhesis.sdk.agents.schemas.AgentResult`).  Callers that need
    the parsed item list (e.g. the ``/mcp/search`` HTTP route) should
    ``json.loads(result["final_answer"])``.

    Raises:
        ValueError: If search fails or returns invalid JSON.
    """
    if not ctx.user_id:
        raise ValueError("user_id is required")

    with ctx.get_db() as db:
        client, provider, repository_context = _get_mcp_tool_config(
            db, tool_id, ctx.organization_id, ctx.user_id
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


@endpoint(
    name="extract_mcp",
    request_mapping={
        "item_url": "{{ input }}",
        "item_id": "{{ item_id }}",
        "tool_id": "{{ tool_id }}",
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
    ctx: EndpointContext,
    item_id: Optional[str] = None,
    item_url: Optional[str] = None,
    tool_id: Optional[str] = None,
    include_children: bool = False,
) -> Dict[str, Any]:
    """Extract full content from an MCP item as markdown.

    For hybrid tools (Notion, GitHub) this uses the REST API directly.
    When include_children=True each subpage / subdirectory file is returned
    as a separate entry in ``documents``.

    Returns the agent result as a dict.  Callers that need only the
    markdown body should read ``result["final_answer"]``.
    Callers that need all documents should read ``result["documents"]``.

    Raises:
        ValueError: If extraction fails, item not found, or neither id
            nor url provided.
    """
    if not item_id and not item_url:
        raise ValueError("Either 'item_id' or 'item_url' must be provided")

    if not ctx.user_id:
        raise ValueError("user_id is required")

    with ctx.get_db() as db:
        tool = crud.get_tool(db, uuid.UUID(tool_id), ctx.organization_id, ctx.user_id)
        if not tool:
            raise ValueError(f"Tool '{tool_id}' not found")

        REST_CAPABLE = {"notion", "github"}
        if tool.tool_provider_type.type_value in REST_CAPABLE:
            source = get_rest_source(db, tool_id, ctx.organization_id, ctx.user_id)
            identifier = item_id or item_url
            docs = await source.fetch_all(identifier, include_children=include_children)
            return {
                "final_answer": docs[0].content if docs else "",
                "documents": [
                    {"id": d.id, "title": d.title, "content": d.content, "url": d.url} for d in docs
                ],
                "execution_history": [],
                "iterations_used": 1,
                "max_iterations_reached": False,
                "success": True,
            }

        client, provider, _ = _get_mcp_tool_config(db, tool_id, ctx.organization_id, ctx.user_id)

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


@endpoint(
    name="query_mcp",
    request_mapping={
        "query": "{{ input }}",
        "tool_id": "{{ tool_id }}",
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
    ctx: EndpointContext,
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
    if not ctx.user_id:
        raise ValueError("user_id is required")

    with ctx.get_db() as db:
        client, provider, repository_context = _get_mcp_tool_config(
            db, tool_id, ctx.organization_id, ctx.user_id
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
