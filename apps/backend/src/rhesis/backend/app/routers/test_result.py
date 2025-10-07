from rhesis.backend.app.models.user import User
from enum import Enum
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.dependencies import get_tenant_context, get_db_session, get_tenant_db_session
from rhesis.backend.app.services.stats import get_test_result_stats
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

TestResultDetailSchema = create_detailed_schema(schemas.TestResult, models.TestResult)


class TestResultStatsMode(str, Enum):
    ALL = "all"
    METRICS = "metrics"
    BEHAVIOR = "behavior"
    CATEGORY = "category"
    TOPIC = "topic"
    OVERALL = "overall"
    TIMELINE = "timeline"
    TEST_RUNS = "test_runs"
    SUMMARY = "summary"  # Overall + metadata only (lightweight)


router = APIRouter(
    prefix="/test_results",
    tags=["test_results"],
    responses={404: {"description": "Not found"}})


@router.post("/", response_model=schemas.TestResult)
@handle_database_exceptions(
    entity_name="test result", custom_unique_message="test result with this name already exists"
)
def create_test_result(
    test_result: schemas.TestResultCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token)):
    """
    Create test result with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context

    # Set the user_id to the current user if not provided
    if not test_result.user_id:
        test_result.user_id = current_user.id

    return crud.create_test_result(
        db=db, test_result=test_result, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=List[TestResultDetailSchema])
@with_count_header(model=models.TestResult)
def read_test_results(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token)):
    """Get all test results"""
    organization_id, user_id = tenant_context
    test_results = crud.get_test_results(
        db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, filter=filter, organization_id=organization_id, user_id=user_id
    )
    return test_results


@router.get("/stats", response_model=schemas.TestResultStatsResponse)
def generate_test_result_stats(
    mode: TestResultStatsMode = Query(
        TestResultStatsMode.ALL,
        description="Data mode: 'summary' (lightweight), 'metrics' (individual metrics), "
        "'behavior/category/topic' (dimensional), 'timeline' (trends), "
        "'test_runs' (by run), 'overall' (aggregate), 'all' (complete)"),
    top: Optional[int] = Query(
        None, description="Max items per dimension (e.g., top 10 behaviors)"
    ),
    months: Optional[int] = Query(
        6, description="Months of historical data to include (default: 6)"
    ),
    test_run_id: UUID | None = Query(
        None, description="Filter by specific test run UUID (legacy, use test_run_ids for multiple)"
    ),
    # Test-level filters
    test_set_ids: Optional[List[UUID]] = Query(None, description="Filter by test set IDs"),
    behavior_ids: Optional[List[UUID]] = Query(None, description="Filter by behavior IDs"),
    category_ids: Optional[List[UUID]] = Query(None, description="Filter by category IDs"),
    topic_ids: Optional[List[UUID]] = Query(None, description="Filter by topic IDs"),
    status_ids: Optional[List[UUID]] = Query(None, description="Filter by test status IDs"),
    test_ids: Optional[List[UUID]] = Query(None, description="Filter by specific test IDs"),
    test_type_ids: Optional[List[UUID]] = Query(None, description="Filter by test type IDs"),
    test_run_ids: Optional[List[UUID]] = Query(None, description="Filter by multiple test run IDs"),
    # User-related filters
    user_ids: Optional[List[UUID]] = Query(None, description="Filter by test creator user IDs"),
    assignee_ids: Optional[List[UUID]] = Query(None, description="Filter by assignee user IDs"),
    owner_ids: Optional[List[UUID]] = Query(None, description="Filter by test owner user IDs"),
    # Other filters
    prompt_ids: Optional[List[UUID]] = Query(None, description="Filter by prompt IDs"),
    priority_min: Optional[int] = Query(None, description="Minimum priority level (inclusive)"),
    priority_max: Optional[int] = Query(None, description="Maximum priority level (inclusive)"),
    tags: Optional[List[str]] = Query(
        None, description="Filter by tags (tests must have all specified tags)"
    ),
    # Date range filters
    start_date: Optional[str] = Query(
        None, description="Start date (ISO format, overrides months parameter)"
    ),
    end_date: Optional[str] = Query(
        None, description="End date (ISO format, overrides months parameter)"
    ),
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token)):
    """Get test result statistics with configurable data modes for optimal performance

    ## Available Modes

    ### Performance-Optimized Modes (recommended for specific use cases):

    **`summary`** - Ultra-lightweight (~5% of full data size)
    - Returns: `overall_pass_rates` + `metadata`
    - Use case: Dashboard widgets, quick overviews
    - Response time: ~50ms

    **`metrics`** - Individual metric analysis (~20% of full data size)
    - Returns: `metric_pass_rates` + `metadata`
    - Contains: Pass/fail rates for Answer Fluency, Answer Relevancy, Contextual Recall, etc.
    - Use case: Metric-focused charts, AI model performance analysis

    **`behavior`** - Test behavior analysis (~15% of full data size)
    - Returns: `behavior_pass_rates` + `metadata`
    - Contains: Pass/fail rates grouped by test behavior (Factual Accuracy, Reasoning, etc.)
    - Use case: Behavior performance charts, test strategy optimization

    **`category`** - Test category analysis (~15% of full data size)
    - Returns: `category_pass_rates` + `metadata`
    - Contains: Pass/fail rates grouped by test category (RAG Systems, Chatbots, etc.)
    - Use case: Category performance comparison, domain-specific analysis

    **`topic`** - Test topic analysis (~15% of full data size)
    - Returns: `topic_pass_rates` + `metadata`
    - Contains: Pass/fail rates grouped by topic (Healthcare, Finance, Technology, etc.)
    - Use case: Topic performance insights, domain expertise evaluation

    **`overall`** - High-level overview (~10% of full data size)
    - Returns: `overall_pass_rates` + `metadata`
    - Contains: Aggregate pass/fail rates (test passes only if ALL metrics pass)
    - Use case: Executive dashboards, KPI tracking

    **`timeline`** - Trend analysis (~40% of full data size)
    - Returns: `timeline` + `metadata`
    - Contains: Monthly pass/fail rates over time with metric breakdowns
    - Use case: Trend charts, historical analysis, progress tracking

    **`test_runs`** - Test run comparison (~30% of full data size)
    - Returns: `test_run_summary` + `metadata`
    - Contains: Pass/fail rates grouped by individual test runs
    - Use case: Test run comparison, execution analysis

    ### Complete Dataset Mode:

    **`all`** - Complete dataset (default, full data size)
    - Returns: All sections above combined
    - Use case: Comprehensive dashboards, full analytics
    - Response time: ~200-500ms depending on data volume

    ## Response Structure Examples

    ### Summary Mode Response:
    ```json
    {
      "overall_pass_rates": {
        "total": 150,
        "passed": 75,
        "failed": 75,
        "pass_rate": 50.0
      },
      "metadata": {
        "mode": "summary",
        "total_test_results": 150,
        "available_metrics": ["Answer Fluency", "Answer Relevancy"],
        ...
      }
    }
    ```

    ### Metrics Mode Response:
    ```json
    {
      "metric_pass_rates": {
        "Answer Fluency": {
          "total": 150,
          "passed": 90,
          "failed": 60,
          "pass_rate": 60.0
        },
        "Answer Relevancy": {
          "total": 150,
          "passed": 135,
          "failed": 15,
          "pass_rate": 90.0
        }
      },
      "metadata": { "mode": "metrics", ... }
    }
    ```

    ## Comprehensive Filtering System

    ### Test-Level Filters
    - `test_set_ids`: Filter by test sets - `?test_set_ids={uuid1}&test_set_ids={uuid2}`
    - `behavior_ids`: Filter by behaviors - `?behavior_ids={uuid1}&behavior_ids={uuid2}`
    - `category_ids`: Filter by categories - `?category_ids={uuid1}&category_ids={uuid2}`
    - `topic_ids`: Filter by topics - `?topic_ids={uuid1}&topic_ids={uuid2}`
    - `status_ids`: Filter by test statuses - `?status_ids={uuid1}&status_ids={uuid2}`
    - `test_ids`: Filter specific tests - `?test_ids={uuid1}&test_ids={uuid2}`
    - `test_type_ids`: Filter by test types - `?test_type_ids={uuid1}&test_type_ids={uuid2}`

    ### User-Related Filters
    - `user_ids`: Filter by test creators - `?user_ids={uuid1}&user_ids={uuid2}`
    - `assignee_ids`: Filter by assignees - `?assignee_ids={uuid1}&assignee_ids={uuid2}`
    - `owner_ids`: Filter by test owners - `?owner_ids={uuid1}&owner_ids={uuid2}`

    ### Other Filters
    - `prompt_ids`: Filter by prompts - `?prompt_ids={uuid1}&prompt_ids={uuid2}`
    - `priority_min/max`: Priority range - `?priority_min=1&priority_max=5`
    - `tags`: Filter by tags - `?tags=urgent&tags=regression`
    - `start_date/end_date`: Date range - `?start_date=2024-01-01&end_date=2024-12-31`

    ## Usage Examples

    ### Basic Usage
    - Dashboard widget: `?mode=summary`
    - Metric analysis: `?mode=metrics&months=12`
    - Timeline charts: `?mode=timeline&months=6`
    - Full analytics: `?mode=all` (or omit mode parameter)

    ### Filtered Analysis
    - Behavior performance for specific test run: `?mode=behavior&test_run_id={uuid}`
    - Category comparison for high-priority tests: `?mode=category&priority_min=3`
    - Metrics for specific test set: `?mode=metrics&test_set_ids={uuid}`
    - Timeline for specific user's tests: `?mode=timeline&user_ids={uuid}`

    ### Advanced Filtering Combinations
    - Urgent healthcare tests: `?behavior_ids={healthcare_uuid}&tags=urgent&priority_min=4`
    - Recent regression tests: `?tags=regression&start_date=2024-01-01&mode=summary`
    - Team performance: `?assignee_ids={user1}&assignee_ids={user2}&mode=test_runs`
    - Category trends by test set: `?mode=category&test_set_ids={uuid}&months=12`
    - Topic analysis for date range: `?mode=topic&start_date=2024-01-01&end_date=2024-06-30`

    ### Performance-Optimized Queries
    - Lightweight dashboard: `?mode=summary&months=1` (fastest)
    - Focused metric analysis: `?mode=metrics&test_ids={uuid1}&test_ids={uuid2}` (targeted)
    - Behavior comparison: `?mode=behavior&behavior_ids={uuid1}&behavior_ids={uuid2}` (specific)
    - Timeline trends: `?mode=timeline&category_ids={uuid}&months=6` (time-focused)

    Args:
        mode: Data mode to retrieve (default: 'all'). See mode descriptions above.
        top: Optional number of top items to show per dimension
        months: Number of months to include in historical timeline
        (default: 6, overridden by date range)
        test_run_id: Optional UUID to filter results to a specific test run

        # Test-level filters
        test_set_ids: Optional list of test set UUIDs to include
        behavior_ids: Optional list of behavior UUIDs to include
        category_ids: Optional list of category UUIDs to include
        topic_ids: Optional list of topic UUIDs to include
        status_ids: Optional list of test status UUIDs to include
        test_ids: Optional list of specific test UUIDs to include
        test_type_ids: Optional list of test type UUIDs to include

        # User-related filters
        user_ids: Optional list of user UUIDs (test creators) to include
        assignee_ids: Optional list of assignee UUIDs to include
        owner_ids: Optional list of test owner UUIDs to include

        # Other filters
        prompt_ids: Optional list of prompt UUIDs to include
        priority_min: Optional minimum priority level (inclusive)
        priority_max: Optional maximum priority level (inclusive)
        tags: Optional list of tags that tests must have (AND logic)

        # Date range filters
        start_date: Optional start date (ISO format, overrides months parameter)
        end_date: Optional end date (ISO format, overrides months parameter)

        db: Database session
        current_user: Current authenticated user

    Returns:
        Dict: Response structure varies by mode (see examples above)
    """
    return get_test_result_stats(
        db=db,
        organization_id=str(current_user.organization_id) if current_user.organization_id else None,
        months=months,
        test_run_id=str(test_run_id) if test_run_id else None,
        mode=mode.value,
        # Test-level filters
        test_set_ids=[str(id) for id in test_set_ids] if test_set_ids else None,
        behavior_ids=[str(id) for id in behavior_ids] if behavior_ids else None,
        category_ids=[str(id) for id in category_ids] if category_ids else None,
        topic_ids=[str(id) for id in topic_ids] if topic_ids else None,
        status_ids=[str(id) for id in status_ids] if status_ids else None,
        test_ids=[str(id) for id in test_ids] if test_ids else None,
        test_type_ids=[str(id) for id in test_type_ids] if test_type_ids else None,
        test_run_ids=[str(id) for id in test_run_ids] if test_run_ids else None,
        # User-related filters
        user_ids=[str(id) for id in user_ids] if user_ids else None,
        assignee_ids=[str(id) for id in assignee_ids] if assignee_ids else None,
        owner_ids=[str(id) for id in owner_ids] if owner_ids else None,
        # Other filters
        prompt_ids=[str(id) for id in prompt_ids] if prompt_ids else None,
        priority_min=priority_min,
        priority_max=priority_max,
        tags=tags,
        # Date range filters
        start_date=start_date,
        end_date=end_date)


@router.get("/{test_result_id}", response_model=TestResultDetailSchema)
def read_test_result(
    test_result_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token)):
    """Get a specific test result by ID"""
    organization_id, user_id = tenant_context
    db_test_result = crud.get_test_result(db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id)
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")
    return db_test_result


@router.put("/{test_result_id}", response_model=schemas.TestResult)
def update_test_result(
    test_result_id: UUID,
    test_result: schemas.TestResultUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token)):
    """
    Update test_result with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_test_result = crud.get_test_result(
        db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")

    # Check if the user has permission to update this test result
    if db_test_result.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to update this test result")

    return crud.update_test_result(
        db=db,
        test_result_id=test_result_id,
        test_result=test_result,
        organization_id=organization_id,
        user_id=user_id)


@router.delete("/{test_result_id}", response_model=schemas.TestResult)
def delete_test_result(
    test_result_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token)):
    """Delete a test result"""
    organization_id, user_id = tenant_context
    db_test_result = crud.get_test_result(db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id)
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")

    # Check if the user has permission to delete this test result
    if db_test_result.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to delete this test result")

    return crud.delete_test_result(db=db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id)
