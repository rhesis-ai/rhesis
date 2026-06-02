"""Higher-level MCP workflows (auth test, Jira ticket creation)."""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.config.settings import get_model_settings
from rhesis.backend.app.models.user import User
from rhesis.sdk.agents.mcp import MCPAgent

from .agents import get_agent_event_handlers
from .config import _get_mcp_client_from_params, _get_mcp_tool_config
from .templates import jinja_env


async def run_mcp_authentication_test(
    db: Session,
    user: User,
    organization_id: str,
    tool_id: Optional[str] = None,
    provider_type_id: Optional[uuid.UUID] = None,
    credentials: Optional[Dict[str, str]] = None,
    user_id: str = None,
) -> Dict[str, Any]:
    """
    Test MCP connection authentication by calling a tool that requires authentication.

    Uses an AI agent to call a tool requiring authentication. The LLM determines
    whether authentication is successful based on the tool call results.

    Args:
        db: Database session
        user: Current user (for authorization)
        organization_id: Organization ID for loading tools from database
        tool_id: Optional ID of the configured tool instance (for existing tools)
        provider_type_id: Optional UUID of the provider type (for non-existent tools)
        credentials: Optional dictionary of credential key-value pairs (for non-existent tools)
        user_id: User ID for authorization check

    Returns:
        Dict with:
        - is_authenticated: str - "Yes" or "No" determined by the LLM based on tool call results
        - message: str - Message from the LLM explaining the authentication status
        - additional_metadata: Optional[Dict[str, Any]] - Provider-specific metadata
          (e.g., spaces for Jira)

    Raises:
        ValueError: If authentication test fails due to connection issues
    """
    # Load MCP client from either tool_id or parameters and get provider name
    provider = None
    if tool_id is not None:
        client, provider, _ = _get_mcp_tool_config(db, tool_id, organization_id, user_id)
    else:
        # Get provider name from provider_type_id
        provider_type = crud.get_type_lookup(db, provider_type_id, organization_id, user_id)
        if provider_type:
            provider = provider_type.type_value

        client = _get_mcp_client_from_params(
            provider_type_id=provider_type_id,
            credentials=credentials,
            db=db,
            organization_id=organization_id,
            user_id=user_id,
        )

    # Load the authentication test prompt with provider context
    auth_prompt = jinja_env.get_template("mcp_test_auth_prompt.jinja2").render(provider=provider)
    model = get_model_settings().generation_model
    agent = MCPAgent(
        model=model,
        mcp_client=client,
        system_prompt=auth_prompt,
        max_iterations=5,  # Keep it short for authentication test
        verbose=False,
        event_handlers=get_agent_event_handlers(
            model_name=getattr(model, "model_name", None) or str(model),
            agent_name="mcp-auth-test",
        ),
    )

    # Run agent with query to test authentication
    query = "Call a tool that requires authentication to verify your credentials"
    result = await agent.run_async(query)

    if not result.success:
        raise ValueError(f"Authentication test failed: {result.error}")

    # Parse the response
    response = json.loads(result.final_answer)

    # Extract spaces if present (Jira-specific) and move to additional_metadata
    additional_metadata = None
    if "spaces" in response:
        additional_metadata = {"spaces": response.pop("spaces")}

    # Add additional_metadata to response
    if additional_metadata:
        response["additional_metadata"] = additional_metadata

    return response


async def create_jira_ticket_from_task(
    task_id: uuid.UUID,
    tool_id: str,
    db: Session,
    organization_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """
    Create a Jira ticket from a task.

    Args:
        task_id: ID of the task to create a ticket from
        tool_id: ID of the Jira MCP tool
        db: Database session
        organization_id: Organization ID
        user_id: User ID

    Returns:
        Dict with issue_key, issue_url, and message

    Raises:
        ValueError: If task not found, tool not found, or tool not configured for Jira
        MCPError: If ticket creation fails
    """
    # 1. Fetch task from database
    task = crud.get_task(db, task_id, organization_id, user_id)
    if not task:
        raise ValueError(f"Task '{task_id}' not found")

    # 2. Get MCP client and verify it's Jira
    client, provider, _ = _get_mcp_tool_config(db, tool_id, organization_id, user_id)
    if provider != "jira":
        raise ValueError(f"Tool must be a Jira integration, got '{provider}'")

    # 3. Extract space_key from tool metadata
    tool = crud.get_tool(db, uuid.UUID(tool_id), organization_id, user_id)
    if not tool.tool_metadata or "space_key" not in tool.tool_metadata:
        raise ValueError("Jira tool is not configured with a space_key")

    space_key = tool.tool_metadata["space_key"]

    # 4. Prepare prompt with task data
    create_issue_prompt = jinja_env.get_template("mcp_jira_create_issue_prompt.jinja2").render(
        space_key=space_key,
        summary=task.title,
        description=task.description or "",
    )

    # 5. Use agent to create issue
    model = get_model_settings().generation_model
    agent = MCPAgent(
        model=model,
        mcp_client=client,
        system_prompt=create_issue_prompt,
        max_iterations=5,
        verbose=False,
        event_handlers=get_agent_event_handlers(
            model_name=getattr(model, "model_name", None) or str(model),
            agent_name="mcp-jira-issue",
        ),
    )

    query = "Create the Jira issue as specified"
    result = await agent.run_async(query)

    if not result.success:
        raise ValueError(f"Failed to create Jira ticket: {result.error}")

    # 6. Parse response
    response_data = json.loads(result.final_answer)

    # 7. Update task_metadata with Jira issue information
    if not task.task_metadata:
        task.task_metadata = {}

    task.task_metadata["jira_issue"] = {
        "issue_key": response_data["issue_key"],
        "issue_url": response_data["issue_url"],
        "tool_id": tool_id,
        "created_at": datetime.utcnow().isoformat(),
    }

    # Save updated task
    crud.update_task(
        db=db,
        task_id=task_id,
        task=schemas.TaskUpdate(task_metadata=task.task_metadata),
        organization_id=organization_id,
        user_id=user_id,
    )

    # 8. Return response
    return response_data
