import logging
from typing import Any, Dict, Optional

from rhesis.backend.app.config.settings import get_model_settings
from rhesis.sdk.agents.mcp import MCPAgent
from rhesis.sdk.context import EndpointContext

from .agents import get_agent_event_handlers
from .config import _get_mcp_tool_config
from .templates import jinja_env

logger = logging.getLogger(__name__)


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
        client, provider = _get_mcp_tool_config(db, tool_id, ctx.organization_id, ctx.user_id)

    if not system_prompt:
        system_prompt = jinja_env.get_template("mcp_default_query_prompt.jinja2").render(
            provider=provider
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
