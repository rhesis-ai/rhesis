import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from rhesis.backend.app import crud
from rhesis.backend.app.config.settings import get_model_settings
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
from rhesis.backend.app.services.tool.rest.schemas import FetchedSource
from rhesis.sdk.agents.mcp import MCPAgent
from rhesis.sdk.context import EndpointContext

from .agents import get_agent_event_handlers
from .config import _get_mcp_client_from_params, _get_mcp_tool_config
from .templates import jinja_env

logger = logging.getLogger(__name__)


def _mcp_template_scope_kwargs(
    provider: str, scope_context: Optional[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, str]]]:
    return {
        "project_context": scope_context if provider == "gitlab" else None,
        "workspace_context": scope_context if provider == "asana" else None,
    }


def _parse_mcp_auth_response(result: Dict[str, Any]) -> Dict[str, str]:
    """Map an MCP auth-check agent result to a connection-test response."""
    if not result.get("success"):
        return {"is_authenticated": "No", "message": "Authentication check did not complete."}

    raw = (result.get("final_answer") or "").strip()
    if not raw:
        return {"is_authenticated": "No", "message": "Authentication check returned no answer."}

    try:
        parsed = json.loads(_strip_code_fence(raw))
    except (json.JSONDecodeError, TypeError):
        return {
            "is_authenticated": "No",
            "message": "Authentication check did not return valid JSON.",
        }

    if not isinstance(parsed, dict) or "authenticated" not in parsed:
        return {
            "is_authenticated": "No",
            "message": "Authentication check JSON must include an authenticated field.",
        }

    if parsed.get("authenticated") is True:
        identity = parsed.get("identity")
        if isinstance(identity, str) and identity.strip():
            message = f"Connected as {identity.strip()}"
        else:
            message = "Connected"
        return {"is_authenticated": "Yes", "message": message[:200]}

    failure_message = parsed.get("message") or parsed.get("identity") or "Authentication failed."
    return {"is_authenticated": "No", "message": str(failure_message).strip()[:200]}


async def _run_agent(
    client: Any,
    query: str,
    system_prompt: str,
    max_iterations: int,
    agent_name: str,
) -> Dict[str, Any]:
    """Run an MCP agent turn and return its serialized result."""
    model = get_model_settings().generation_model
    agent = MCPAgent(
        model=model,
        mcp_client=client,
        system_prompt=system_prompt,
        max_iterations=max_iterations,
        verbose=False,
        event_handlers=get_agent_event_handlers(
            model_name=getattr(model, "model_name", None) or str(model),
            agent_name=agent_name,
        ),
    )
    result = await agent.run_async(query)
    return result.model_dump()


def _resolve_tool_client(
    organization_id: str,
    user_id: str,
    tool_id: str,
    tool_metadata: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
) -> Tuple[Any, str, Optional[Dict[str, str]]]:
    """Build an MCP client, provider name, and optional scope context for a saved tool."""
    with get_db_with_tenant_variables(organization_id, user_id, project_id or "") as db:
        return _get_mcp_tool_config(
            db, tool_id, organization_id, user_id, tool_metadata_override=tool_metadata
        )


def _resolve_params_client(
    organization_id: str,
    user_id: str,
    provider_type_id: Any,
    credentials: Dict[str, str],
    tool_metadata: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
) -> Tuple[Any, str, Optional[Dict[str, str]]]:
    """Build an MCP client from unsaved credentials."""
    with get_db_with_tenant_variables(organization_id, user_id, project_id or "") as db:
        return _get_mcp_client_from_params(
            provider_type_id,
            credentials,
            db,
            organization_id,
            user_id,
            tool_metadata=tool_metadata,
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
        client, provider, scope_context = _get_mcp_tool_config(
            db, tool_id, ctx.organization_id, ctx.user_id
        )

    if not system_prompt:
        system_prompt = jinja_env.get_template("mcp_default_query_prompt.jinja2").render(
            provider=provider,
            **_mcp_template_scope_kwargs(provider, scope_context),
        )

    return await _run_agent(client, query, system_prompt, max_iterations, "mcp-query")


def _strip_code_fence(text: str) -> str:
    """Strip a leading/trailing markdown code fence and an optional ``json`` tag."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[0].strip() == "json":
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_fetched_sources(answer: str) -> List[FetchedSource]:
    """Parse an agent's JSON answer into typed sources.

    Expects a JSON array of ``{id, title, content, url}`` objects — the same shape
    the REST extract path produces — so the router maps either path identically.

    Raises:
        ValueError: If the answer is not a JSON array of objects.
    """
    data = json.loads(_strip_code_fence(answer))
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of sources.")
    sources: List[FetchedSource] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Each source must be a JSON object.")
        raw_url = item.get("url")
        sources.append(
            FetchedSource(
                id=str(item.get("id", "")),
                title=str(item.get("title") or ""),
                content=str(item.get("content") or ""),
                url=str(raw_url) if raw_url is not None else None,
            )
        )
    return sources


async def mcp_extract(
    tool_id: str,
    identifier: str,
    organization_id: str,
    user_id: str,
    include_children: bool = False,
    max_iterations: int = 10,
    project_id: Optional[str] = None,
) -> List[FetchedSource]:
    """Extract content from an MCP-backed tool as structured sources.

    Drives the MCP agent with the ``mcp_extract_prompt`` template, which requires a
    JSON array reply, then parses it into ``FetchedSource`` objects. On a malformed
    reply, retries once with the template's repair variant before giving up.

    Raises:
        ValueError: If user_id is missing or the agent never returns valid JSON.
    """
    if not user_id:
        raise ValueError("user_id is required")

    client, provider, scope_context = _resolve_tool_client(
        organization_id, user_id, tool_id, project_id=project_id
    )
    query = f"Extract the full content of: {identifier}"
    template = jinja_env.get_template("mcp_extract_prompt.jinja2")

    last_error: Optional[Exception] = None
    for repair in (False, True):
        system_prompt = template.render(
            provider=provider,
            include_children=include_children,
            repair=repair,
            **_mcp_template_scope_kwargs(provider, scope_context),
        )
        result = await _run_agent(client, query, system_prompt, max_iterations, "mcp-extract")
        try:
            return _parse_fetched_sources(result.get("final_answer", ""))
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            last_error = e
            if not repair:
                logger.warning("MCP extract returned non-JSON; retrying with repair prompt.")

    raise ValueError(f"MCP extract did not return valid JSON: {last_error}")


async def mcp_health_check(
    organization_id: str,
    user_id: str,
    tool_id: Optional[str] = None,
    provider_type_id: Optional[Any] = None,
    credentials: Optional[Dict[str, str]] = None,
    tool_metadata: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Test MCP credentials via a minimal read-only agent auth ping.

    Accepts either a saved ``tool_id`` or, for connections not yet saved,
    ``provider_type_id`` + ``credentials``.

    Raises:
        ToolConfigurationError: If neither a tool_id nor provider_type_id+credentials
            is provided.
    """
    if not user_id:
        raise ValueError("user_id is required")

    if tool_id:
        client, provider, scope_context = _resolve_tool_client(
            organization_id,
            user_id,
            tool_id,
            tool_metadata=tool_metadata,
            project_id=project_id,
        )
    elif provider_type_id is not None and credentials is not None:
        client, provider, scope_context = _resolve_params_client(
            organization_id,
            user_id,
            provider_type_id,
            credentials,
            tool_metadata=tool_metadata,
            project_id=project_id,
        )
    else:
        raise ToolConfigurationError(
            "A saved tool_id or provider_type_id + credentials is required to test the connection."
        )

    system_prompt = jinja_env.get_template("mcp_test_auth_prompt.jinja2").render(
        provider=provider,
        **_mcp_template_scope_kwargs(provider, scope_context),
    )
    result = await _run_agent(
        client, "Verify authentication and report the result.", system_prompt, 3, "mcp-health"
    )
    return _parse_mcp_auth_response(result)
