import uuid
from dataclasses import asdict
from enum import Enum
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.decorators import check_resource_permission
from rhesis.backend.app.auth.permissions import ResourceAction
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.constants import TestType
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.test_set import TestSet
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.documents import Document
from rhesis.backend.app.schemas.services import SourceData
from rhesis.backend.app.services.generation import process_sources_to_documents
from rhesis.backend.app.services.prompt import get_prompts_for_test_set, prompts_to_csv
from rhesis.backend.app.services.test import (
    create_test_set_associations,
    remove_test_set_associations,
)
from rhesis.backend.app.services.test_set import (
    bulk_create_test_set,
    execute_test_set_on_endpoint,
    get_test_set_stats,
    get_test_set_test_stats,
    update_test_set_attributes,
)
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema
from rhesis.backend.logging import logger
from rhesis.backend.tasks import task_launcher
from rhesis.backend.tasks.test_set import generate_and_save_test_set

# Create the detailed schema for TestSet and Test
TestSetDetailSchema = create_detailed_schema(schemas.TestSet, models.TestSet)
TestDetailSchema = create_detailed_schema(schemas.Test, models.Test)

router = APIRouter(
    prefix="/test_sets", tags=["test_sets"], responses={404: {"description": "Not found"}}
)


class StatsMode(str, Enum):
    ENTITY = "entity"
    RELATED_ENTITY = "related_entity"


# Schemas for test set generation
class GenerationSample(BaseModel):
    text: str
    behavior: str
    topic: str
    rating: Optional[int] = None
    feedback: Optional[str] = ""


class TestSetGenerationConfig(BaseModel):
    project_name: Optional[str] = None
    behaviors: List[str] = []
    purposes: List[str] = []
    test_type: str = "single_turn"
    response_generation: str = "prompt_only"
    test_coverage: str = "standard"
    tags: List[str] = []
    description: str = ""


class TestSetGenerationRequest(BaseModel):
    config: TestSetGenerationConfig
    samples: List[GenerationSample] = []
    synthesizer_type: str = "prompt"
    num_tests: Optional[int] = None
    batch_size: int = 20
    documents: Optional[List[Document]] = None
    sources: Optional[List[SourceData]] = None
    name: Optional[str] = None


class TestSetGenerationResponse(BaseModel):
    task_id: str
    message: str
    estimated_tests: int


def resolve_test_set_or_raise(identifier: str, db: Session, organization_id: str = None) -> TestSet:
    """
    Helper function to resolve a test set by identifier and raise 404 if not found.

    Args:
        identifier: The test set identifier (UUID, nano_id, or slug)
        db: The database session
        organization_id: Organization ID for filtering

    Returns:
        The resolved TestSet

    Raises:
        HTTPException: 404 error if test set is not found
    """
    db_test_set = crud.resolve_test_set(identifier, db, organization_id)
    if db_test_set is None:
        raise HTTPException(status_code=404, detail="Test Set not found with provided identifier")
    return db_test_set


def build_generation_prompt(
    config: TestSetGenerationConfig, samples: List[GenerationSample]
) -> str:
    """
    Build a comprehensive prompt for test generation including sample ratings and feedback.

    Args:
        config: The generation configuration
        samples: List of samples with ratings and feedback

    Returns:
        A formatted prompt string for the synthesizer
    """
    # Case-insensitive comparison using TestType enum
    test_type_enum = TestType.from_string(config.test_type)
    if test_type_enum == TestType.SINGLE_TURN:
        test_type_string = "Single interaction tests"
    elif test_type_enum == TestType.MULTI_TURN:
        test_type_string = "Multi-turn conversation tests"
    else:
        # Fallback for unknown test types
        test_type_string = f"{config.test_type} tests"

    if config.response_generation == "prompt_only":
        output_format_string = "Generate only user inputs"
    else:
        output_format_string = "Generate both user inputs and expected responses"
    prompt_parts = [
        "Generate comprehensive tests based on the following configuration:",
        "",
        "PROJECT CONTEXT:",
        f"- Project: {config.project_name or 'General'}",
        f"- Test Behaviors: {', '.join(config.behaviors)}",
        f"- Test Purposes: {', '.join(config.purposes)}",
        f"- Key Topics: {', '.join(config.tags)}",
        f"- Test Type: {test_type_string}",
        f"- Output Format: {output_format_string}",
        "",
        "SPECIFIC REQUIREMENTS:",
        f"{config.description}",
        "",
    ]

    if samples:
        prompt_parts.extend(
            [
                "SAMPLE EVALUATION FEEDBACK:",
                "The following samples were generated and rated by the user. "
                "Use this feedback to improve the quality of new tests:",
                "",
            ]
        )

        for i, sample in enumerate(samples, 1):
            rating_text = f"{sample.rating}/5 stars" if sample.rating is not None else "Not rated"
            prompt_parts.extend(
                [
                    f"Sample {i}:",
                    f'  Text: "{sample.text}"',
                    f"  Behavior: {sample.behavior}",
                    f"  Topic: {sample.topic}",
                    f"  User Rating: {rating_text}",
                ]
            )

            if sample.feedback and sample.feedback.strip():
                prompt_parts.append(f'  User Feedback: "{sample.feedback}"')

            prompt_parts.append("")

        # Add guidance based on ratings
        rated_samples = [s for s in samples if s.rating is not None]
        if rated_samples:
            avg_rating = sum(s.rating for s in rated_samples) / len(rated_samples)
            prompt_parts.extend(
                [
                    "QUALITY GUIDANCE:",
                    f"- Average sample rating: {avg_rating:.1f}/5.0",
                ]
            )

            if avg_rating < 3.0:
                prompt_parts.append(
                    "- Focus on significant improvements based on the feedback provided"
                )
            elif avg_rating < 4.0:
                prompt_parts.append(
                    "- Make moderate improvements based on the feedback "
                    "while maintaining good aspects"
                )
            else:
                prompt_parts.append(
                    "- Maintain the high quality demonstrated in the samples while adding variety"
                )

            prompt_parts.append("")

    prompt_parts.extend(
        [
            "GENERATION INSTRUCTIONS:",
            "Generate tests that:",
            "1. Follow the same format and structure as the samples",
            "2. Address the specific behaviors and purposes listed",
            "3. Incorporate the feedback provided for similar quality improvements",
            "4. Cover the key topics mentioned in the configuration",
            "5. Maintain variety while staying focused on the requirements",
        ]
    )

    return "\n".join(prompt_parts)


def determine_test_count(config: TestSetGenerationConfig, requested_count: Optional[int]) -> int:
    """
    Determine the number of tests to generate based on coverage level and user request.

    Args:
        config: The generation configuration
        requested_count: User-requested test count (if any)

    Returns:
        Number of tests to generate
    """
    if requested_count is not None and requested_count > 0:
        return requested_count

    # Default counts based on coverage level
    coverage_mapping = {
        "focused": 100,
        "standard": 1000,
        "comprehensive": 5000,
    }

    return coverage_mapping.get(config.test_coverage, 1000)


@router.post("/generate", response_model=TestSetGenerationResponse)
async def generate_test_set(
    request: TestSetGenerationRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Generate a test set using AI synthesizers with user configuration and sample feedback.

    This endpoint creates a comprehensive prompt from the user's configuration and sample
    ratings, then launches a Celery task to generate the full test set.

    Args:
        request: The generation request containing config, samples, and parameters
            - sources contains SourceData with id
            (name, description, content will be fetched from DB)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Task information including task ID and estimated test count
    """
    try:
        # Validate request
        if not request.config.behaviors:
            raise HTTPException(status_code=400, detail="At least one behavior must be specified")

        if not request.config.description.strip():
            raise HTTPException(status_code=400, detail="Description is required")

        # Prepare documents from sources if provided
        # Fetch full source data from database if only IDs are provided
        documents_to_use = []
        source_ids_to_documents = {}  # Map document name to source_id
        source_ids_list = []  # List of source_ids in the same order as documents
        if request.documents:
            documents_to_use = request.documents
        elif request.sources:
            organization_id, user_id = tenant_context
            documents_to_use, source_ids_list, source_ids_to_documents = (
                process_sources_to_documents(
                    sources=request.sources,
                    db=db,
                    organization_id=organization_id,
                    user_id=user_id,
                )
            )

        # Build the generation prompt from config and samples
        generation_prompt = build_generation_prompt(request.config, request.samples)

        # Determine test count
        test_count = determine_test_count(request.config, request.num_tests)

        # Launch the generation task
        # Note: The task will fetch the user's configured model itself
        # using get_user_generation_model. This avoids trying to serialize
        # BaseLLM objects which are not JSON serializable
        task_result = task_launcher(
            generate_and_save_test_set,
            request.synthesizer_type,  # First positional argument
            current_user=current_user,
            num_tests=test_count,
            batch_size=request.batch_size,
            prompt=generation_prompt,
            documents=[asdict(doc) for doc in documents_to_use] if documents_to_use else None,
            source_ids=source_ids_list,  # Pass actual source_ids list
            source_ids_to_documents=source_ids_to_documents,  # Pass mapping for debugging
            name=request.name,  # Pass optional test set name
        )

        logger.info(
            "Test set generation task launched",
            extra={
                "task_id": task_result.id,
                "user_id": current_user.id,
                "organization_id": current_user.organization_id,
                "synthesizer_type": request.synthesizer_type,
                "test_count": test_count,
                "sample_count": len(request.samples),
            },
        )

        return TestSetGenerationResponse(
            task_id=task_result.id,
            message="Test set generation started. "
            f"You will be notified when {test_count} tests are ready.",
            estimated_tests=test_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start test set generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to start test set generation: {str(e)}"
        )


@router.post("/bulk", response_model=schemas.TestSetBulkResponse)
async def create_test_set_bulk(
    test_set_data: schemas.TestSetBulkCreate,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create a test set with multiple tests in a single operation.

    The input format should be:
    {
        "name": "Test Set Name",
        "description": "Optional description",
        "short_description": "Optional short description",
        "tests": [
            {
                "prompt": {
                    "content": "Prompt text",
                    "language_code": "en",
                    "demographic": "Optional demographic (e.g., 'Caucasian')",
                    "dimension": "Optional dimension (e.g., 'Ethnicity')",
                    "expected_response": "Optional expected response text"
                },
                "behavior": "Behavior name",
                "category": "Category name",
                "topic": "Topic name",
                "test_configuration": {}  # Optional test configuration,
                "metadata": {
                    "sources": [
                        {
                            "source": "doc1.pdf",
                            "name": "Document Name",
                            "description": "Document description",
                            "content": "Document content used for this test"
                        }
                    ],
                    "generated_by": "DocumentSynthesizer",
                    "context_index": 0,
                    "context_length": 1500
                }
            }
        ]
    }

    Notes:
    - demographic and dimension are optional fields that work together
    - If both demographic and dimension are provided, they will be properly associated
    - The dimension will be created first, then the demographic will be linked to it
    - expected_response is an optional field to specify the expected model response
    """
    try:
        test_set = bulk_create_test_set(
            db=db,
            test_set_data=test_set_data,
            organization_id=str(current_user.organization_id),
            user_id=str(current_user.id),
        )
        return test_set
    except Exception as e:
        logger.error(f"Failed to create test set: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create test set: {str(e)}")


@router.post("/", response_model=schemas.TestSet)
@handle_database_exceptions(
    entity_name="test set", custom_unique_message="Test set with this name already exists"
)
async def create_test_set(
    test_set: schemas.TestSetCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create test set with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    return crud.create_test_set(
        db=db, test_set=test_set, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=list[TestSetDetailSchema])
@with_count_header(model=models.TestSet)
async def read_test_sets(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    has_runs: bool | None = Query(
        None, description="Filter test sets by whether they have test runs"
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get test sets with flexible filtering.

    Args:
        skip: Number of items to skip
        limit: Maximum number of items to return
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        filter: OData filter string (use $filter in the query)
        has_runs: Filter test sets by whether they have test runs.
                 If True, only return test sets that have associated test runs.
                 If False, only return test sets that don't have test runs.
                 If None/omitted, return all test sets.
        db: Database session
        current_user: Current user
    """
    from rhesis.backend.logging import logger

    logger.info(f"test_sets endpoint called with has_runs={has_runs}")

    organization_id, user_id = tenant_context
    return crud.get_test_sets(
        db=db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        has_runs=has_runs,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/stats", response_model=schemas.EntityStats)
def generate_test_set_stats(
    top: Optional[int] = None,
    months: Optional[int] = 6,
    mode: StatsMode = StatsMode.ENTITY,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get statistics about test sets and their tests

    Args:
        top: Optional number of top items to show per dimension
        months: Number of months to include in historical stats (default: 6)
        mode: Stats mode to use - either 'entity' (default) or 'related_entity'
        db: Database session
        current_user: Current user
    """
    if mode == StatsMode.ENTITY:
        return get_test_set_stats(
            db=db, current_user_organization_id=current_user.organization_id, top=top, months=months
        )
    else:
        return get_test_set_test_stats(
            db=db,
            test_set_id=None,  # No test set ID means get stats for all tests
            current_user_organization_id=current_user.organization_id,
            top=top,
            months=months,
        )


@router.get("/{test_set_identifier}", response_model=TestSetDetailSchema)
@check_resource_permission(TestSet, ResourceAction.READ)
async def read_test_set(
    test_set_identifier: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    return resolve_test_set_or_raise(test_set_identifier, db, organization_id)


@router.delete("/{test_set_id}", response_model=schemas.TestSet)
@check_resource_permission(TestSet, ResourceAction.DELETE)
async def delete_test_set(
    test_set_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context
    db_test_set = crud.delete_test_set(
        db, test_set_id=test_set_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_set is None:
        raise HTTPException(status_code=404, detail="Test Set not found")
    return db_test_set


@router.put("/{test_set_id}", response_model=schemas.TestSet)
@check_resource_permission(TestSet, ResourceAction.UPDATE)
@handle_database_exceptions(
    entity_name="test set", custom_unique_message="Test set with this name already exists"
)
async def update_test_set(
    test_set_id: uuid.UUID,
    test_set: schemas.TestSetUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update test_set with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_test_set = crud.update_test_set(
        db,
        test_set_id=test_set_id,
        test_set=test_set,
        organization_id=organization_id,
        user_id=user_id,
    )
    if db_test_set is None:
        raise HTTPException(status_code=404, detail="Test Set not found")

    try:
        update_test_set_attributes(db=db, test_set_id=str(test_set_id))
    except Exception as e:
        logger.warning(f"Failed to regenerate test set attributes for {test_set_id}: {e}")

    return db_test_set


@router.get("/{test_set_identifier}/download", response_class=StreamingResponse)
def download_test_set_prompts(
    test_set_identifier: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),  # SECURITY: Extract tenant context
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        # Resolve test set
        organization_id, user_id = tenant_context  # SECURITY: Get tenant context
        db_test_set = resolve_test_set_or_raise(test_set_identifier, db, organization_id)

        # Get prompts with organization filtering (SECURITY CRITICAL)
        prompts = get_prompts_for_test_set(db, db_test_set.id, organization_id)

        # Check if prompts list is empty before trying to create CSV
        if not prompts:
            raise HTTPException(
                status_code=404, detail=f"No prompts found in test set: {test_set_identifier}"
            )

        csv_data = prompts_to_csv(prompts)

        response = StreamingResponse(iter([csv_data]), media_type="text/csv")
        response.headers["Content-Disposition"] = (
            f"attachment; filename=test_set_{test_set_identifier}.csv"
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download test set prompts for {test_set_identifier}: {str(e)}",
        )


@router.get("/{test_set_identifier}/prompts", response_model=list[schemas.PromptView])
def get_test_set_prompts(
    test_set_identifier: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),  # SECURITY: Extract tenant context
    current_user: User = Depends(require_current_user_or_token),
):
    organization_id, user_id = tenant_context  # SECURITY: Get tenant context
    db_test_set = resolve_test_set_or_raise(test_set_identifier, db, organization_id)
    return get_prompts_for_test_set(db, db_test_set.id, organization_id)


@router.get("/{test_set_identifier}/tests", response_model=list[TestDetailSchema])
async def get_test_set_tests(
    test_set_identifier: str,
    response: Response,
    skip: int = 0,
    limit: int = 10,
    order_by: str = "created_at",
    order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all tests associated with a test set."""
    db_test_set = resolve_test_set_or_raise(
        test_set_identifier, db, str(current_user.organization_id)
    )
    items, count = crud.get_test_set_tests(
        db=db,
        test_set_id=db_test_set.id,
        skip=skip,
        limit=limit,
        sort_by=order_by,
        sort_order=order,
        filter=filter,
    )

    response.headers["X-Total-Count"] = str(count)
    return items  # FastAPI handles serialization based on response_model


@router.post("/{test_set_identifier}/execute/{endpoint_id}")
async def execute_test_set(
    test_set_identifier: str,
    endpoint_id: uuid.UUID,
    test_configuration_attributes: schemas.TestSetExecutionRequest = None,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Submit a test set for execution against an endpoint."""
    try:
        # Extract test configuration attributes from request body, default to Parallel mode
        attributes = None
        if test_configuration_attributes and test_configuration_attributes.execution_options:
            attributes = test_configuration_attributes.execution_options

        organization_id, user_id = tenant_context
        result = execute_test_set_on_endpoint(
            db=db,
            test_set_identifier=test_set_identifier,
            endpoint_id=endpoint_id,
            current_user=current_user,
            test_configuration_attributes=attributes,
            organization_id=organization_id,
            user_id=user_id,
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in test set execution: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to submit test set execution: {str(e)}"
        )


@router.get("/{test_set_identifier}/stats", response_model=schemas.EntityStats)
def generate_test_set_test_stats(
    test_set_identifier: str,
    top: Optional[int] = None,
    months: Optional[int] = 6,
    mode: StatsMode = StatsMode.ENTITY,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get statistics about tests in a specific test set

    Args:
        test_set_identifier: The identifier of the test set
        top: Optional number of top items to show per dimension
        months: Number of months to include in historical stats (default: 6)
        mode: Stats mode to use - either 'entity' (default) or 'related_entity'
        db: Database session
        current_user: Current user
    """
    db_test_set = resolve_test_set_or_raise(
        test_set_identifier, db, str(current_user.organization_id)
    )

    if mode == StatsMode.ENTITY:
        return get_test_set_stats(
            db=db, current_user_organization_id=current_user.organization_id, top=top, months=months
        )
    else:
        return get_test_set_test_stats(
            db=db,
            test_set_id=str(db_test_set.id),
            current_user_organization_id=current_user.organization_id,
            top=top,
            months=months,
        )


@router.get("/{test_set_identifier}/prompts/download")
def download_test_set_prompts_csv(
    test_set_identifier: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),  # SECURITY: Extract tenant context
    current_user: User = Depends(require_current_user_or_token),
):
    try:
        # Resolve test set
        organization_id, user_id = tenant_context  # SECURITY: Get tenant context
        db_test_set = resolve_test_set_or_raise(test_set_identifier, db, organization_id)

        # Get prompts with organization filtering (SECURITY CRITICAL)
        prompts = get_prompts_for_test_set(db, db_test_set.id, organization_id)

        try:
            csv_data = prompts_to_csv(prompts)
        except ValueError:
            raise HTTPException(
                status_code=404, detail=f"No prompts found in test set: {test_set_identifier}"
            )

        # Return CSV file
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; "
                f'filename="test_set_{test_set_identifier}_prompts.csv"'
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to download test set prompts: {str(e)}"
        )


@router.post("/{test_set_id}/associate", response_model=schemas.TestSetBulkAssociateResponse)
async def associate_tests_with_test_set(
    test_set_id: uuid.UUID,
    request: schemas.TestSetBulkAssociateRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Associate multiple existing tests with a test set in a single operation.
    """
    result = create_test_set_associations(
        db=db,
        test_set_id=str(test_set_id),
        test_ids=[str(test_id) for test_id in request.test_ids],
        organization_id=str(current_user.organization_id),
        user_id=str(current_user.id),
    )

    if not result["success"]:
        error_detail = {"message": result["message"], "metadata": result["metadata"]}
        raise HTTPException(status_code=400, detail=error_detail)

    return result


@router.post("/{test_set_id}/disassociate", response_model=schemas.TestSetBulkDisassociateResponse)
async def disassociate_tests_from_test_set(
    test_set_id: uuid.UUID,
    request: schemas.TestSetBulkDisassociateRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Remove associations between tests and a test set in a single operation.

    The input format should be:
    {
        "test_ids": ["uuid1", "uuid2", "uuid3"]
    }

    Notes:
    - All tests must exist in the database
    - The test set must exist in the database
    - Test associations will be removed in a single operation
    - If a test is not associated, it will be ignored
    """
    # Use the service method to handle the disassociation
    result = remove_test_set_associations(
        db=db,
        test_set_id=str(test_set_id),
        test_ids=[str(test_id) for test_id in request.test_ids],
        organization_id=str(current_user.organization_id),
        user_id=str(current_user.id),
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return schemas.TestSetBulkDisassociateResponse(
        success=result["success"],
        total_tests=result["total_tests"],
        removed_associations=result["removed_associations"],
        message=result["message"],
    )
