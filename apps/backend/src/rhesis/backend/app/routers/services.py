import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.schemas.services import (
    GenerateContentRequest,
    GenerateEmbeddingRequest,
    GenerateMultiTurnTestsRequest,
    GenerateMultiTurnTestsResponse,
    GenerateTestsRequest,
    GenerateTestsResponse,
    QueryMCPRequest,
    QueryMCPResponse,
    RecentActivitiesResponse,
    TestConfigRequest,
    TestConfigResponse,
    TestPipelineRequest,
)
from rhesis.backend.app.services.activities import RecentActivitiesService
from rhesis.backend.app.services.generation import (
    generate_multiturn_tests,
    generate_tests,
)
from rhesis.backend.app.services.github import read_repo_contents
from rhesis.backend.app.services.test_config_generator import TestConfigGeneratorService
from rhesis.backend.app.services.test_generation_pipeline import (
    test_generation_pipeline_stream,
)
from rhesis.backend.app.services.tool.mcp import (
    handle_mcp_exception,
    query_mcp,
)
from rhesis.backend.app.utils.execution_validation import validate_generation_model
from rhesis.sdk.context import EndpointContext

logger = logging.getLogger(__name__)

router = RhesisRouter(
    prefix="/services",
    tags=["services"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
    resource="service",
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
def get_github_contents(repo_url: str):
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


@router.post("/generate/content")
async def generate_content_endpoint(
    request: GenerateContentRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
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
        from rhesis.backend.app.utils.user_model_utils import get_generation_model_with_override
        from rhesis.sdk.models.factory import get_model

        model = get_generation_model_with_override(db, current_user)
        if isinstance(model, str):
            model = get_model(model, model_type="language")
        response = await model.a_generate(request.prompt, schema=request.schema_)
        return response
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error"
        logger.error(f"Failed to generate content: {error_msg}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to generate content: {error_msg}")


@router.post("/generate/embedding")
def generate_embedding_endpoint(
    request: GenerateEmbeddingRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Generate an embedding for a given text using the user's configured embedding model.

    Args:
        request: The request containing the text to embed
        db: The database session
        current_user: The current authenticated user
    """
    try:
        from rhesis.backend.app.utils.user_model_utils import get_user_embedding_model
        from rhesis.sdk.models.factory import get_model

        embedder = get_user_embedding_model(db, current_user)
        if isinstance(embedder, str):
            embedder = get_model(embedder, model_type="embedding")
        embedding = embedder.generate(text=request.text)
        return embedding
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error"
        logger.error(f"Failed to generate embedding: {error_msg}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to generate embedding: {error_msg}")


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

        # Validate per-request model override exists and belongs to user's org
        model_id_str = str(request.model_id) if request.model_id else None
        if model_id_str:
            from rhesis.backend.app import crud as model_crud

            model_obj = model_crud.get_model(
                db=db,
                model_id=model_id_str,
                organization_id=str(current_user.organization_id),
            )
            if not model_obj:
                raise HTTPException(
                    status_code=400,
                    detail=f"Model {model_id_str} not found or not accessible",
                )

        # Generate tests synchronously
        tests = await generate_tests(
            db=db,
            user=current_user,
            config=request.config,
            num_tests=request.num_tests,
            sources=request.sources,
            model_id=model_id_str,
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
        # Validate per-request model override exists and belongs to user's org
        model_id_str = str(request.model_id) if request.model_id else None
        if model_id_str:
            from rhesis.backend.app import crud as model_crud

            model_obj = model_crud.get_model(
                db=db,
                model_id=model_id_str,
                organization_id=str(current_user.organization_id),
            )
            if not model_obj:
                raise HTTPException(
                    status_code=400,
                    detail=f"Model {model_id_str} not found or not accessible",
                )

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
            model_id=model_id_str,
        )
        # test_cases is a TestSet dict with a "tests" key containing the array
        return {"tests": test_cases.get("tests", [])}
    except HTTPException:
        raise
    except Exception as e:
        _handle_generation_error(e)


@router.post("/generate/test_pipeline")
def test_pipeline_endpoint(
    request: TestPipelineRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Stream config and test generation as NDJSON events."""
    organization_id, _ = tenant_context
    model_id_str = str(request.model_id) if request.model_id else None

    async def _stream():
        async for chunk in test_generation_pipeline_stream(
            db=db,
            user=current_user,
            prompt=request.prompt,
            organization_id=organization_id,
            project_id=(str(request.project_id) if request.project_id else None),
            previous_messages=request.previous_messages,
            test_type=request.test_type,
            num_tests=request.num_tests,
            sources=request.sources,
            model_id=model_id_str,
            config=request.config,
        ):
            yield chunk

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


@router.post("/generate/test_config", response_model=TestConfigResponse)
async def generate_test_config(
    request: TestConfigRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
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
        result = await service.generate_config(
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


@router.post("/mcp/query", response_model=QueryMCPResponse)
async def query_mcp_server(
    request: QueryMCPRequest,
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
        ctx = EndpointContext(
            organization_id=organization_id,
            user_id=user_id,
            _db_factory=get_db_with_tenant_variables,
        )
        result = await query_mcp(
            query=request.query,
            tool_id=request.tool_id,
            ctx=ctx,
            system_prompt=request.system_prompt,
            max_iterations=request.max_iterations,
        )
        return result
    except Exception as e:
        raise handle_mcp_exception(e, "query")


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
