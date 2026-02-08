from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.services import (
    ChatRequest,
    CreateJiraTicketFromTaskRequest,
    CreateJiraTicketFromTaskResponse,
    ExtractMCPRequest,
    ExtractMCPResponse,
    GenerateContentRequest,
    GenerateMultiTurnTestsRequest,
    GenerateMultiTurnTestsResponse,
    GenerateTestsRequest,
    GenerateTestsResponse,
    ItemResult,
    PromptRequest,
    QueryMCPRequest,
    QueryMCPResponse,
    RecentActivitiesResponse,
    SearchMCPRequest,
    TestConfigRequest,
    TestConfigResponse,
    TestMCPConnectionRequest,
    TestMCPConnectionResponse,
    TextResponse,
)
from rhesis.backend.app.services.activities import RecentActivitiesService
from rhesis.backend.app.services.gemini_client import (
    create_chat_completion,
    get_chat_response,
    get_json_response,
)
from rhesis.backend.app.services.generation import (
    generate_multiturn_tests,
    generate_tests,
)
from rhesis.backend.app.services.github import read_repo_contents
from rhesis.backend.app.services.mcp_service import (
    create_jira_ticket_from_task,
    extract_mcp,
    handle_mcp_exception,
    query_mcp,
    run_mcp_authentication_test,
    search_mcp,
)
from rhesis.backend.app.services.test_config_generator import TestConfigGeneratorService
from rhesis.backend.app.utils.execution_validation import validate_generation_model
from rhesis.backend.logging import logger

router = APIRouter(
    prefix="/services",
    tags=["services"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


def _handle_generation_error(error: Exception) -> None:
    """
    Handle errors during test generation with appropriate HTTP responses.

    Centralizes error handling for generation endpoints.

    Args:
        error: The exception that occurred

    Raises:
        HTTPException: With appropriate status code and message
    """
    from rhesis.backend.app.utils.execution_validation import handle_execution_error

    # Convert the error to HTTPException and raise it
    http_exception = handle_execution_error(error, operation="generate tests")
    raise http_exception


@router.get("/github/contents")
async def get_github_contents(repo_url: str):
    """
    Get the contents of a GitHub repository.

    Args:
        repo_url: The URL of the GitHub repository to read

    Returns:
        str: The contents of the repository
    """
    logger.info(f"Getting GitHub contents for {repo_url}")
    try:
        contents = read_repo_contents(repo_url)
        return contents
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error"
        logger.error(f"Failed to get GitHub contents for {repo_url}: {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=400, detail=f"Failed to retrieve repository contents: {error_msg}"
        )


@router.post("/openai/json")
async def get_ai_json_response(prompt_request: PromptRequest):
    """
    Get a JSON response from OpenAI API.

    Args:
        prompt_request: The request containing the prompt to send to OpenAI

    Returns:
        dict: The JSON response from OpenAI
    """
    try:
        if prompt_request.stream:

            async def generate():
                async for chunk in get_json_response(prompt_request.prompt, stream=True):
                    yield f"data: {chunk}\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream")

        return get_json_response(prompt_request.prompt)
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error"
        logger.error(f"Failed to get JSON response: {error_msg}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to get AI response: {error_msg}")


@router.post("/openai/chat")
async def get_ai_chat_response(chat_request: ChatRequest):
    """
    Get a response from OpenAI API using a chat messages array.

    Args:
        chat_request: The request containing the messages array and response format

    Returns:
        dict: The response from OpenAI (JSON or text based on response_format)
    """
    try:
        if chat_request.stream:
            return StreamingResponse(
                get_chat_response(
                    messages=[msg.model_dump() for msg in chat_request.messages],
                    response_format=chat_request.response_format,
                    stream=True,
                ),
                media_type="text/event-stream",
            )

        return get_chat_response(
            messages=[msg.model_dump() for msg in chat_request.messages],
            response_format=chat_request.response_format,
        )
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error"
        logger.error(f"Failed to get chat response: {error_msg}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to get chat response: {error_msg}")


@router.post("/chat/completions")
async def create_chat_completion_endpoint(request: dict):
    """
    OpenAI-compatible chat completions endpoint.
    Accepts requests in the standard OpenAI chat completion format.

    Args:
        request: The complete chat completion request body matching OpenAI's format

    Returns:
        dict: The unmodified OpenAI API response
    """
    try:
        response = create_chat_completion(request)

        if request.get("stream", False):
            return StreamingResponse(response, media_type="text/event-stream")

        return response
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error"
        logger.error(f"Failed to create chat completion: {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=400, detail=f"Failed to create chat completion: {error_msg}"
        )


@router.post("/generate/content")
async def generate_content_endpoint(request: GenerateContentRequest):
    """
    Generate text using LLM with optional OpenAI-wrapped JSON schema for structured output.

    The schema parameter MUST be in OpenAI-wrapped format. This format is compatible
    with multiple LLM providers (OpenAI, Vertex AI, etc.) and enables type-safe
    structured generation without requiring Pydantic model definitions.

    Args:
        request: Contains prompt and optional OpenAI-wrapped JSON schema for structured output.

    Returns:
        str or dict: Raw text if no schema provided, validated dict if schema is provided

    Schema Format (Required):
        The schema must be wrapped in OpenAI's structured output format:
        ```python
        {
            "prompt": "Generate a person's info",
            "schema": {
                "type": "json_schema",
                "json_schema": {
                    "name": "PersonInfo",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "number"}
                        },
                        "required": ["name", "age"],
                        "additionalProperties": false
                    },
                    "strict": true
                }
            }
        }
        ```

    Note: Plain JSON schemas are not supported. The schema must include the
    "type": "json_schema" wrapper with name, schema, and strict fields.
    """
    try:
        from rhesis.backend.app.constants import DEFAULT_GENERATION_MODEL, DEFAULT_MODEL_NAME
        from rhesis.sdk.models.factory import get_model

        prompt = request.prompt
        schema = request.schema_

        # Use the default generation model from constants
        # This respects the global configuration (currently vertex_ai)
        model = get_model(provider=DEFAULT_GENERATION_MODEL, model_name=DEFAULT_MODEL_NAME)

        # Pass schema directly to the model - SDK handles provider-specific conversion
        response = model.generate(prompt, schema=schema)

        return response
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error"
        logger.error(f"Failed to generate content: {error_msg}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to generate content: {error_msg}")


@router.post("/generate/tests", response_model=GenerateTestsResponse)
async def generate_tests_endpoint(
    request: GenerateTestsRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    _validate_model=Depends(validate_generation_model),
):
    """
    Generate test cases using the prompt synthesizer.

    Args:
        request: The request containing the prompt, number of tests, and optional sources
            - sources contains SourceData with id
            (name, description, content will be fetched from DB)
        db: Database session
        tenant_context: Tenant context containing organization_id and user_id
        current_user: Current authenticated user

    Returns:
        GenerateTestsResponse: The generated test cases
    """
    try:
        # Validate config
        if not request.config.behaviors:
            raise HTTPException(status_code=400, detail="At least one behavior must be specified")

        # Generate tests synchronously
        tests = await generate_tests(
            db=db,
            user=current_user,
            config=request.config,
            num_tests=request.num_tests,
            sources=request.sources,
        )

        # Return Pydantic model - FastAPI handles serialization
        return GenerateTestsResponse(tests=tests)
    except HTTPException:
        raise
    except Exception as e:
        _handle_generation_error(e)


@router.post("/generate/multiturn-tests", response_model=GenerateMultiTurnTestsResponse)
async def generate_multiturn_tests_endpoint(
    request: GenerateMultiTurnTestsRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    _validate_model=Depends(validate_generation_model),
):
    """
    Generate multi-turn test cases using the MultiTurnSynthesizer.

    Multi-turn tests include structured prompts with goals, instructions, and restrictions
    for testing LLM agents across multiple conversation turns.

    Args:
        request: The request containing the generation prompt and optional parameters
            - generation_prompt: Description of what to test
            - behavior: Optional behavior type (e.g., "Compliance", "Reliability")
            - category: Optional category (e.g., "Harmful", "Harmless")
            - topic: Optional specific topic
            - num_tests: Number of tests to generate (default: 5)
        db: Database session
        tenant_context: Tenant context containing organization_id and user_id
        current_user: Current authenticated user

    Returns:
        GenerateMultiTurnTestsResponse: The generated multi-turn test cases
    """
    try:
        # Prepare config dict from request
        config = {
            "generation_prompt": request.generation_prompt,
            "behavior": request.behavior,
            "category": request.category,
            "topic": request.topic,
        }

        test_cases = await generate_multiturn_tests(
            db=db,
            user=current_user,
            config=config,
            num_tests=request.num_tests,
        )
        # test_cases is a TestSet dict with a "tests" key containing the array
        return {"tests": test_cases.get("tests", [])}
    except HTTPException:
        raise
    except Exception as e:
        _handle_generation_error(e)


@router.post("/generate/text", response_model=TextResponse)
async def generate_text(prompt_request: PromptRequest):
    """
    Generate raw text from an arbitrary prompt.

    Args:
        prompt_request: The request containing the prompt and stream flag

    Returns:
        TextResponse: The raw text response from the model
    """
    try:
        # Create a simple message array with the prompt
        messages = [{"role": "user", "content": prompt_request.prompt}]

        if prompt_request.stream:
            # Handle streaming response
            async def generate():
                response_stream = get_chat_response(
                    messages=messages,
                    response_format="text",  # Explicitly request text format
                    stream=True,
                )

                async for chunk in response_stream:
                    if chunk["choices"][0]["delta"]["content"]:
                        yield f"data: {chunk['choices'][0]['delta']['content']}\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream")

        # Non-streaming response
        response = get_chat_response(
            messages=messages,
            response_format="text",  # Explicitly request text format
            stream=False,
        )

        return TextResponse(text=response)
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error"
        logger.error(f"Failed to generate text: {error_msg}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to generate text: {error_msg}")


@router.post("/generate/test_config", response_model=TestConfigResponse)
async def generate_test_config(
    request: TestConfigRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    _validate_model=Depends(validate_generation_model),
):
    """
    Generate test configuration JSON based on user description.

    This endpoint:
    1. Fetches all behaviors from the database (filtered by organization)
    2. Optionally fetches project details if project_id is provided
    3. Sends the behaviors and project context to the LLM and asks it to select
       relevant ones based on the prompt
    4. LLM generates topics and test categories

    Args:
        request: Contains prompt (description) for test configuration generation,
            and optional project_id to include project context
        db: Database session (injected)
        tenant_context: Organization and user context (injected)
        current_user: Current authenticated user (injected)

    Returns:
        TestConfigResponse: JSON containing LLM-selected behaviors (from database), and
            LLM-generated topics and test categories, each with name and description fields
    """
    try:
        organization_id, user_id = tenant_context

        logger.info(
            f"Test config generation request for prompt: {request.prompt[:100]}... "
            f"for organization: {organization_id}"
        )

        service = TestConfigGeneratorService(db=db, user=current_user)
        result = service.generate_config(
            request.prompt,
            organization_id=organization_id,
            project_id=str(request.project_id) if request.project_id else None,
            previous_messages=request.previous_messages,
        )

        logger.info("Test config generation successful")
        return result
    except ValueError as e:
        from rhesis.backend.app.utils.execution_validation import (
            handle_execution_error,
        )

        logger.warning(f"Invalid request for test config generation: {str(e)}")
        http_exception = handle_execution_error(e, operation="generate test configuration")
        raise http_exception
    except RuntimeError as e:
        logger.error(f"Test config generation failed: {str(e)}", exc_info=True)
        detail = str(e) if e.args else "Failed to generate test configuration"
        raise HTTPException(status_code=500, detail=detail)
    except Exception as e:
        logger.error(
            f"Unexpected error in test config generation: {str(e)}",
            exc_info=True,
        )
        error_detail = (
            str(e)
            if str(e)
            else "An unexpected error occurred during test configuration generation"
        )
        raise HTTPException(status_code=500, detail=error_detail)


@router.post("/mcp/search", response_model=List[ItemResult])
async def search_mcp_server(
    request: SearchMCPRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    _validate_model=Depends(validate_generation_model),
):
    """
    Search MCP server for items matching a natural language query.

    Uses an AI agent to intelligently search the connected MCP server and
    return structured results. The agent automatically selects the appropriate
    search tools and formats results consistently.

    Args:
        request: SearchMCPRequest with query and server_name

    Returns:
        List of items, each containing:
        - id: Item identifier
        - url: Direct link to view the item
        - title: Human-readable item title

    Raises:
        HTTPException: 500 error if search fails

    Example:
        POST /mcp/search
        {
            "query": "Find pages about authentication",
            "server_name": "notion"
        }
    """
    try:
        organization_id, user_id = tenant_context
        return await search_mcp(request.query, request.tool_id, db, organization_id, user_id)
    except Exception as e:
        raise handle_mcp_exception(e, "search")


@router.post("/mcp/extract", response_model=ExtractMCPResponse)
async def extract_mcp_item(
    request: ExtractMCPRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    _validate_model=Depends(validate_generation_model),
):
    """
    Extract full content from an MCP item as markdown.

    Uses an AI agent to retrieve and convert item content to markdown format.
    The agent navigates the item structure and extracts all relevant content
    including text, headings, lists, and nested blocks.

    Args:
        request: ExtractMCPRequest with either item id or url (or both) and tool_id

    Returns:
        ExtractMCPResponse containing markdown-formatted content

    Raises:
        HTTPException: 500 error if extraction fails or item not found

    Example:
        POST /mcp/extract
        {
            "url": "https://notion.so/page-id-from-search",
            "tool_id": "tool-uuid-123"
        }
        OR
        {
            "id": "page-id-123",
            "tool_id": "tool-uuid-123"
        }
    """
    try:
        organization_id, user_id = tenant_context
        content = await extract_mcp(
            item_id=request.id,
            item_url=request.url,
            tool_id=request.tool_id,
            db=db,
            organization_id=organization_id,
            user_id=user_id,
        )
        return {"content": content}
    except Exception as e:
        raise handle_mcp_exception(e, "extract")


@router.post("/mcp/query", response_model=QueryMCPResponse)
async def query_mcp_server(
    request: QueryMCPRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    _validate_model=Depends(validate_generation_model),
):
    """
    Execute arbitrary tasks on an MCP server with full flexibility.

    Unlike /search and /extract, this endpoint handles any MCP task with
    custom prompts and returns detailed execution traces. Use this for
    complex operations like creating, updating, or analyzing content.

    Args:
        request: QueryMCPRequest with query, server_name, optional system_prompt and max_iterations

    Returns:
        QueryMCPResponse with result and execution history

    Raises:
        HTTPException: 500 error if task execution fails

    Examples:
        # Create content
        {"query": "Create a page titled 'Q1 Planning'", "server_name": "notion"}

        # Custom agent behavior
        {
            "query": "Analyze authentication issues",
            "server_name": "github",
            "system_prompt": "You are a security analyst...",
            "max_iterations": 15
        }
    """
    try:
        organization_id, user_id = tenant_context
        result = await query_mcp(
            query=request.query,
            tool_id=request.tool_id,
            db=db,
            organization_id=organization_id,
            user_id=user_id,
            system_prompt=request.system_prompt,
            max_iterations=request.max_iterations,
        )
        return result
    except Exception as e:
        raise handle_mcp_exception(e, "query")


@router.post("/mcp/test-connection", response_model=TestMCPConnectionResponse)
async def test_mcp_connection(
    request: TestMCPConnectionRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    _validate_model=Depends(validate_generation_model),
):
    """
    Test MCP connection authentication by calling a tool that requires authentication.

    This endpoint verifies that the MCP connection is properly authenticated by
    instructing an agent to call a tool that requires authentication. If the
    connection is not authenticated, a 401 unauthorized error will be detected.

    Args:
        request: TestMCPConnectionRequest with either:
            - tool_id: For testing existing tools
            - provider_type_id + credentials + optional tool_metadata:
              For testing non-existent tools

    Returns:
        TestMCPConnectionResponse with:
        - is_authenticated: str - "Yes" if authentication is valid, "No" otherwise
        - message: str - Explanation of the authentication status

    Raises:
        HTTPException: 400 error if validation fails,
            500 error if test fails due to connection issues

    Examples:
        # Test existing tool
        POST /mcp/test-connection
        {
            "tool_id": "tool-uuid-123"
        }

        # Test non-existent tool (standard provider)
        POST /mcp/test-connection
        {
            "provider_type_id": "provider-uuid-123",
            "credentials": {"NOTION_TOKEN": "ntn_abc123..."}
        }

        # Test non-existent tool (custom provider)
        POST /mcp/test-connection
        {
            "provider_type_id": "provider-uuid-123",
            "credentials": {"TOKEN": "token123"},
            "tool_metadata": {
                "command": "npx",
                "args": ["@notionhq/notion-mcp-server"],
                "env": {"NOTION_TOKEN": "{{ TOKEN }}"}
            }
        }
    """
    try:
        organization_id, user_id = tenant_context
        result = await run_mcp_authentication_test(
            db=db,
            user=current_user,
            organization_id=organization_id,
            tool_id=request.tool_id,
            provider_type_id=request.provider_type_id,
            credentials=request.credentials,
            tool_metadata=request.tool_metadata,
            user_id=user_id,
        )
        return result
    except ValueError as e:
        logger.warning(f"Invalid request for MCP connection test: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Use handle_mcp_exception to properly handle MCP errors (401, 403, etc.)
        # This ensures authentication errors are properly mapped and don't log users out
        raise handle_mcp_exception(e, "test-connection")


@router.post("/mcp/jira/create-ticket-from-task", response_model=CreateJiraTicketFromTaskResponse)
async def create_jira_ticket_from_task_endpoint(
    request: CreateJiraTicketFromTaskRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    _validate_model=Depends(validate_generation_model),
):
    """
    Create a Jira ticket from a task.

    This endpoint creates a Jira issue using the MCP Jira integration,
    mapping task fields to Jira issue fields.

    Args:
        request: CreateJiraTicketFromTaskRequest with task_id and tool_id

    Returns:
        CreateJiraTicketFromTaskResponse with issue key, URL, and message

    Raises:
        HTTPException: 400 if validation fails, 500 if creation fails

    Example:
        POST /mcp/jira/create-ticket-from-task
        {
            "task_id": "task-uuid-123",
            "tool_id": "tool-uuid-456"
        }
    """
    try:
        organization_id, user_id = tenant_context
        result = await create_jira_ticket_from_task(
            task_id=request.task_id,
            tool_id=request.tool_id,
            db=db,
            organization_id=organization_id,
            user_id=user_id,
        )
        return result
    except ValueError as e:
        logger.warning(f"Invalid request for Jira ticket creation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise handle_mcp_exception(e, "create-jira-ticket")


@router.get("/recent-activities", response_model=RecentActivitiesResponse)
def get_recent_activities(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get recent activities across all trackable entities.

    Returns a unified timeline of CREATE/UPDATE/DELETE operations
    with complete entity details and user information for entities
    that inherit ActivityTrackableMixin.

    Args:
        limit: Maximum number of activities to return (default 50, max 200)
        db: Database session (injected)
        tenant_context: Organization and user context (injected)
        current_user: Current authenticated user (injected)

    Returns:
        RecentActivitiesResponse containing list of activities and total count
    """
    try:
        organization_id, user_id = tenant_context
        service = RecentActivitiesService()
        result = service.get_recent_activities(db=db, organization_id=organization_id, limit=limit)
        return RecentActivitiesResponse(**result)
    except Exception as e:
        logger.error(f"Failed to get recent activities: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve recent activities")
