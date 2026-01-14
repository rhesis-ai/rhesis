"""MCP service for generic integration using MCPAgent."""

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import jinja2
from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException
from rhesis.backend.app.utils.llm_utils import get_user_generation_model
from rhesis.backend.app.utils.observability import get_test_context
from rhesis.backend.logging import logger
from rhesis.sdk.decorators import endpoint
from rhesis.sdk.services.mcp import MCPAgent, MCPClientFactory
from rhesis.sdk.services.mcp.exceptions import (
    MCPApplicationError,
    MCPConfigurationError,
    MCPError,
)
from rhesis.sdk.services.mcp.observable_agent import ObservableMCPAgent

# Initialize Jinja2 environment for loading prompt templates
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=jinja2.select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


def handle_mcp_exception(e: Exception, operation: str) -> HTTPException:
    """
    Map MCP exceptions to HTTP responses using their status codes.

    Args:
        e: The caught exception
        operation: Description of operation (e.g., "search", "extract", "query")

    Returns:
        HTTPException with appropriate status code and message
    """
    if isinstance(e, MCPError):
        # All MCP errors have status_code set by their __init__
        status_code = e.status_code if e.status_code else 500

        # For MCPApplicationError, use the detail attribute directly to avoid redundant prefixes
        # For other errors, use the string representation
        if isinstance(e, MCPApplicationError):
            message = e.detail
        else:
            message = str(e)

        # Map MCP authentication errors (401, 403) to 502 Bad Gateway
        # These are external service auth issues, not user session issues
        # This prevents the frontend from logging users out when MCP tools have auth problems
        if status_code in {401, 403} and e.category == "application":
            status_code = 502
            message = f"MCP tool authentication failed: {message}"

        # Log based on severity (client errors vs server errors)
        original_error_name = type(e.original_error).__name__ if e.original_error else None
        if status_code >= 500:
            logger.error(
                f"MCP {operation} error [{e.category}] ({status_code}): {message}",
                exc_info=True,
                extra={"category": e.category, "original_error": original_error_name},
            )
        else:
            logger.warning(
                f"MCP {operation} error [{e.category}] ({status_code}): {message}",
                extra={"category": e.category, "original_error": original_error_name},
            )

        return HTTPException(status_code=status_code, detail=message)

    # Non-MCP errors
    logger.error(f"Unexpected error in MCP {operation}: {str(e)}", exc_info=True)
    return HTTPException(
        status_code=500,
        detail=f"An unexpected error occurred during {operation}. Please try again.",
    )


def _get_agent_class():
    """
    Determine which agent class to use based on RhesisClient availability.

    Returns:
        ObservableMCPAgent if RhesisClient is available and not disabled, otherwise MCPAgent
    """
    from rhesis.backend.app.utils.observability import rhesis_client

    if rhesis_client is not None and not getattr(rhesis_client, "is_disabled", False):
        logger.info("Using ObservableMCPAgent for MCP operations (observability enabled)")
        return ObservableMCPAgent
    else:
        logger.info("Using standard MCPAgent for MCP operations (observability disabled)")
        return MCPAgent


def _get_mcp_tool_config(db: Session, tool_id: str, organization_id: str, user_id: str = None):
    """
    Get MCP client and provider configuration from database by tool ID.

    Args:
        db: Database session
        tool_id: Tool instance ID
        organization_id: Organization ID (for authorization check)
        user_id: User ID (for authorization check)

    Returns:
        Tuple of (MCPClient, provider_name) ready to use

    Raises:
        MCPConfigurationError: If tool not found, deleted, not an MCP integration,
            or invalid credentials
    """
    try:
        tool = crud.get_tool(db, uuid.UUID(tool_id), organization_id, user_id)
    except ItemDeletedException:
        raise MCPConfigurationError(
            f"Tool '{tool_id}' has been deleted. Please re-import the source."
        )

    if not tool:
        raise MCPConfigurationError(
            f"Tool '{tool_id}' not found. Please add it in /integrations/tools"
        )

    # Verify tool type is MCP
    if tool.tool_type.type_value != "mcp":
        raise MCPConfigurationError(f"Tool '{tool.name}' is not an MCP integration")

    # Get provider name for the client
    provider = tool.tool_provider_type.type_value

    # Parse credentials JSON
    try:
        credentials_dict = json.loads(tool.credentials)
    except (json.JSONDecodeError, TypeError) as e:
        raise MCPConfigurationError(f"Invalid credentials format for tool '{tool_id}': {e}")

    # Check if tool uses custom provider (requires manual JSON config) or standard provider
    if provider == "custom":
        # Custom provider: requires tool_metadata with full JSON config
        if not tool.tool_metadata:
            raise MCPConfigurationError("Custom provider tools require tool_metadata configuration")

        factory = MCPClientFactory.from_tool_config(
            tool_name=f"{provider}Api",
            tool_config=tool.tool_metadata,
            credentials=credentials_dict,
        )
    else:
        # Standard provider: SDK constructs config from YAML templates
        factory = MCPClientFactory.from_provider(
            provider=provider,
            credentials=credentials_dict,
        )

    client = factory.create_client(f"{provider}Api")
    return client, provider


def _get_mcp_client_from_params(
    provider_type_id: uuid.UUID,
    credentials: Dict[str, str],
    tool_metadata: Optional[Dict[str, Any]],
    db: Session,
    organization_id: str,
    user_id: str = None,
):
    """
    Get MCP client from parameters without requiring a tool in the database.

    Args:
        provider_type_id: UUID of the provider type (TypeLookup)
        credentials: Dictionary of credential key-value pairs
        tool_metadata: Optional tool metadata (required for custom providers)
        db: Database session
        organization_id: Organization ID (for authorization check)
        user_id: User ID (for authorization check)

    Returns:
        MCPClient ready to use

    Raises:
        ValueError: If provider not found, invalid configuration, or missing required fields
    """
    # Fetch provider type from database
    provider_type = crud.get_type_lookup(db, provider_type_id, organization_id, user_id)

    if not provider_type:
        raise ValueError(
            f"Provider type '{provider_type_id}' not found. Please verify the provider_type_id."
        )

    # Get provider name for the client
    provider = provider_type.type_value

    # Check if provider uses custom provider (requires manual JSON config) or standard provider
    if provider == "custom":
        # Custom provider: requires tool_metadata with full JSON config
        if not tool_metadata:
            raise ValueError("Custom provider requires tool_metadata configuration")

        factory = MCPClientFactory.from_tool_config(
            tool_name=f"{provider}Api",
            tool_config=tool_metadata,
            credentials=credentials,
        )
    else:
        # Standard provider: SDK constructs config from YAML templates
        factory = MCPClientFactory.from_provider(
            provider=provider,
            credentials=credentials,
        )

    client = factory.create_client(f"{provider}Api")
    return client


@endpoint(
    name="search_mcp",
    bind={
        **get_test_context(),
        "tool_id": os.getenv("RHESIS_TOOL_ID"),
    },
    request_mapping={
        "query": "{{ input }}",
    },
    response_mapping={},
)
async def search_mcp(
    query: str, tool_id: str, db: Session, user: User, organization_id: str, user_id: str = None
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
        user: Current user (for retrieving default generation model)
        organization_id: Organization ID for loading tools from database

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
        ...     user,
        ...     org_id
        ... )
        >>> print(results[0]["title"])
    """
    model = get_user_generation_model(db, user)

    # Load MCP client from database tool configuration
    client, _ = _get_mcp_tool_config(db, tool_id, organization_id, user_id)

    search_prompt = jinja_env.get_template("mcp_search_prompt.jinja2").render()

    # Use dynamic agent class based on RhesisClient availability
    AgentClass = _get_agent_class()
    agent = AgentClass(
        model=model,
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
    user: User = None,
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
        user: Current user (for retrieving default generation model)
        organization_id: Organization ID for loading tools from database

    Returns:
        Full item content formatted as markdown string

    Raises:
        ValueError: If extraction fails, item not found, or neither id nor url provided

    Example:
        >>> content = await extract_mcp(
        ...     "page-id-123",
        ...     "tool-uuid-123",
        ...     db,
        ...     user,
        ...     org_id
        ... )
        >>> print(content[:100])  # First 100 chars
    """
    if not item_id and not item_url:
        raise ValueError("Either 'item_id' or 'item_url' must be provided")

    model = get_user_generation_model(db, user)

    # Load MCP client and provider from database tool configuration
    client, provider = _get_mcp_tool_config(db, tool_id, organization_id, user_id)

    extract_prompt = jinja_env.get_template("mcp_extract_prompt.jinja2").render(
        item_id=item_id, item_url=item_url, provider=provider
    )

    # Use dynamic agent class based on RhesisClient availability
    AgentClass = _get_agent_class()
    agent = AgentClass(
        model=model,
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
    user: User,
    organization_id: str,
    user_id: str = None,
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
        ...     "tool-uuid-123", db, user, org_id
        ... )
    """
    model = get_user_generation_model(db, user)

    # Load MCP client from database tool configuration
    client, _ = _get_mcp_tool_config(db, tool_id, organization_id, user_id)

    if not system_prompt:
        system_prompt = jinja_env.get_template("mcp_default_query_prompt.jinja2").render()

    # Use dynamic agent class based on RhesisClient availability
    AgentClass = _get_agent_class()
    agent = AgentClass(
        model=model,
        mcp_client=client,
        system_prompt=system_prompt,
        max_iterations=max_iterations,
        verbose=False,
    )

    result = await agent.run_async(query)

    # Agent now raises exceptions for errors, so if we get here, it succeeded
    return result.model_dump()


async def run_mcp_authentication_test(
    db: Session,
    user: User,
    organization_id: str,
    tool_id: Optional[str] = None,
    provider_type_id: Optional[uuid.UUID] = None,
    credentials: Optional[Dict[str, str]] = None,
    tool_metadata: Optional[Dict[str, Any]] = None,
    user_id: str = None,
) -> Dict[str, Any]:
    """
    Test MCP connection authentication by calling a tool that requires authentication.

    Uses an AI agent to call a tool requiring authentication. The LLM determines
    whether authentication is successful based on the tool call results.

    Args:
        db: Database session
        user: Current user (for retrieving default generation model)
        organization_id: Organization ID for loading tools from database
        tool_id: Optional ID of the configured tool instance (for existing tools)
        provider_type_id: Optional UUID of the provider type (for non-existent tools)
        credentials: Optional dictionary of credential key-value pairs (for non-existent tools)
        tool_metadata: Optional tool metadata (for non-existent tools that use custom providers)
        user_id: User ID for authorization check

    Returns:
        Dict with:
        - is_authenticated: str - "Yes" or "No" determined by the LLM based on tool call results
        - message: str - Message from the LLM explaining the authentication status

    Raises:
        ValueError: If authentication test fails due to connection issues
    """
    model = get_user_generation_model(db, user)

    # Load MCP client from either tool_id or parameters
    if tool_id is not None:
        client, _ = _get_mcp_tool_config(db, tool_id, organization_id, user_id)
    else:
        client = _get_mcp_client_from_params(
            provider_type_id=provider_type_id,
            credentials=credentials,
            tool_metadata=tool_metadata,
            db=db,
            organization_id=organization_id,
            user_id=user_id,
        )

    # Load the authentication test prompt
    auth_prompt = jinja_env.get_template("mcp_test_auth_prompt.jinja2").render()
    agent = MCPAgent(
        model=model,
        mcp_client=client,
        system_prompt=auth_prompt,
        max_iterations=5,  # Keep it short for authentication test
        verbose=False,
    )

    # Run agent with query to test authentication
    query = "Call a tool that requires authentication to verify your credentials"
    result = await agent.run_async(query)

    if not result.success:
        raise ValueError(f"Authentication test failed: {result.error}")

    return json.loads(result.final_answer)
