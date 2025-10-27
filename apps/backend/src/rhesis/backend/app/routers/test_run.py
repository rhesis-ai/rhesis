from enum import Enum
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.stats.test_run import get_test_run_stats
from rhesis.backend.app.services.test_run import (
    get_test_results_for_test_run,
    test_run_results_to_csv,
)
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.schema_factory import create_detailed_schema

# Create the detailed schema for TestRun
TestRunDetailSchema = create_detailed_schema(
    schemas.TestRun,
    models.TestRun,
    include_nested_relationships={"test_configuration": {"endpoint": ["project"], "test_set": []}},
)


class TestRunStatsMode(str, Enum):
    ALL = "all"
    STATUS = "status"
    RESULTS = "results"
    TEST_SETS = "test_sets"
    EXECUTORS = "executors"
    TIMELINE = "timeline"
    SUMMARY = "summary"


router = APIRouter(
    prefix="/test_runs", tags=["test_runs"], responses={404: {"description": "Not found"}}
)


@router.post("/", response_model=schemas.TestRun)
@handle_database_exceptions(
    entity_name="test run", custom_unique_message="Test run with this configuration already exists"
)
def create_test_run(
    test_run: schemas.TestRunCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create test run with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    # Set the user_id to the current user if not provided
    if not test_run.user_id:
        test_run.user_id = current_user.id

    # Set the organization_id if not provided
    if not test_run.organization_id:
        test_run.organization_id = current_user.organization_id

    return crud.create_test_run(
        db=db, test_run=test_run, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=List[TestRunDetailSchema])
@with_count_header(model=models.TestRun)
def read_test_runs(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all test runs with their related objects"""
    test_runs = crud.get_test_runs(
        db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=str(current_user.organization_id),
        user_id=str(current_user.id),
    )
    return test_runs


@router.get("/stats", response_model=schemas.TestRunStatsResponse)
def generate_test_run_stats(
    mode: TestRunStatsMode = Query(
        TestRunStatsMode.ALL,
        description="Data mode: 'summary' (lightweight), 'status' (status distribution), "
        "'results' (result distribution), 'test_sets' (most run test sets), "
        "'executors' (top executors), 'timeline' (trends), 'all' (complete)",
    ),
    top: Optional[int] = Query(
        None, description="Max items per dimension (e.g., top 10 executors)"
    ),
    months: Optional[int] = Query(
        6, description="Months of historical data to include (default: 6)"
    ),
    # Test run filters
    test_run_ids: Optional[List[UUID]] = Query(None, description="Filter by specific test run IDs"),
    # User-related filters
    user_ids: Optional[List[UUID]] = Query(None, description="Filter by executor user IDs"),
    # Configuration filters
    endpoint_ids: Optional[List[UUID]] = Query(None, description="Filter by endpoint IDs"),
    test_set_ids: Optional[List[UUID]] = Query(None, description="Filter by test set IDs"),
    # Status filters
    status_list: Optional[List[str]] = Query(None, description="Filter by test run statuses"),
    # Date range filters
    start_date: Optional[str] = Query(
        None, description="Start date (ISO format, overrides months parameter)"
    ),
    end_date: Optional[str] = Query(
        None, description="End date (ISO format, overrides months parameter)"
    ),
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get test run statistics with configurable data modes for optimal performance

    ## Available Modes

    ### Performance-Optimized Modes (recommended for specific use cases):

    **`summary`** - Ultra-lightweight (~5% of full data size)
    - Returns: `overall_summary` + `metadata`
    - Use case: Dashboard widgets, quick overviews
    - Response time: ~50ms

    **`status`** - Test run status distribution (~15% of full data size)
    - Returns: `status_distribution` + `metadata`
    - Contains: Count and percentage of runs by status (pending, running, completed, failed)
    - Use case: Status monitoring dashboards, operational views

    **`results`** - Test run result distribution (~15% of full data size)
    - Returns: `result_distribution` + `metadata`
    - Contains: Pass/fail rates and counts for test runs
    - Use case: Success rate tracking, quality metrics

    **`test_sets`** - Most run test sets analysis (~20% of full data size)
    - Returns: `most_run_test_sets` + `metadata`
    - Contains: Test sets ranked by execution frequency
    - Use case: Popular test set identification, usage analytics

    **`executors`** - Top test executors (~20% of full data size)
    - Returns: `top_executors` + `metadata`
    - Contains: Users ranked by test run execution count
    - Use case: User activity tracking, workload distribution

    **`timeline`** - Trend analysis (~40% of full data size)
    - Returns: `timeline` + `metadata`
    - Contains: Monthly test run counts and status/result breakdowns
    - Use case: Trend charts, historical analysis, capacity planning

    ### Complete Dataset Mode:

    **`all`** - Complete dataset (default, full data size)
    - Returns: All sections above combined
    - Use case: Comprehensive dashboards, full analytics
    - Response time: ~200-500ms depending on data volume

    ## Response Structure Examples

    ### Summary Mode Response:
    ```json
    {
      "overall_summary": {
        "total_runs": 150,
        "unique_test_sets": 25,
        "unique_executors": 8,
        "most_common_status": "completed",
        "pass_rate": 85.5
      },
      "metadata": {
        "mode": "summary",
        "total_test_runs": 150,
        "available_statuses": ["completed", "failed", "running"],
        ...
      }
    }
    ```

    ### Status Mode Response:
    ```json
    {
      "status_distribution": [
        {
          "status": "completed",
          "count": 90,
          "percentage": 60.0
        },
        {
          "status": "failed",
          "count": 30,
          "percentage": 20.0
        }
      ],
      "metadata": { "mode": "status", ... }
    }
    ```

    ## Comprehensive Filtering System

    ### Test Run Filters
    - `test_run_ids`: Filter specific test runs - `?test_run_ids={uuid1}&test_run_ids={uuid2}`

    ### User-Related Filters
    - `user_ids`: Filter by executors - `?user_ids={uuid1}&user_ids={uuid2}`

    ### Configuration Filters
    - `endpoint_ids`: Filter by endpoints - `?endpoint_ids={uuid1}&endpoint_ids={uuid2}`
    - `test_set_ids`: Filter by test sets - `?test_set_ids={uuid1}&test_set_ids={uuid2}`

    ### Status Filters
    - `status_list`: Filter by statuses - `?status_list=completed&status_list=failed`

    ### Date Range Filters
    - `start_date/end_date`: Date range - `?start_date=2024-01-01&end_date=2024-12-31`

    ## Usage Examples

    ### Basic Usage
    - Dashboard widget: `?mode=summary`
    - Status monitoring: `?mode=status&months=1`
    - Timeline charts: `?mode=timeline&months=6`
    - Full analytics: `?mode=all` (or omit mode parameter)

    ### Filtered Analysis
    - User activity: `?mode=executors&user_ids={uuid}&months=3`
    - Test set popularity: `?mode=tests&test_set_ids={uuid1}&test_set_ids={uuid2}`
    - Endpoint performance: `?mode=results&endpoint_ids={uuid}`
    - Status trends: `?mode=timeline&status_list=failed&months=12`

    Args:
        mode: Data mode to retrieve (default: 'all'). See mode descriptions above.
        top: Optional number of top items to show per dimension
        months: Number of months to include in historical timeline
        (default: 6, overridden by date range)

        # Test run filters
        test_run_ids: Optional list of test run UUIDs to include

        # User-related filters
        user_ids: Optional list of user UUIDs (test run executors) to include

        # Configuration filters
        endpoint_ids: Optional list of endpoint UUIDs to include
        test_set_ids: Optional list of test set UUIDs to include

        # Status filters
        status_list: Optional list of test run statuses to include

        # Date range filters
        start_date: Optional start date (ISO format, overrides months parameter)
        end_date: Optional end date (ISO format, overrides months parameter)

        db: Database session
        current_user: Current authenticated user

    Returns:
        Dict: Response structure varies by mode (see examples above)
    """
    return get_test_run_stats(
        db=db,
        organization_id=str(current_user.organization_id) if current_user.organization_id else None,
        months=months,
        mode=mode.value,
        top=top,
        # Test run filters
        test_run_ids=[str(id) for id in test_run_ids] if test_run_ids else None,
        # User-related filters
        user_ids=[str(id) for id in user_ids] if user_ids else None,
        # Configuration filters
        endpoint_ids=[str(id) for id in endpoint_ids] if endpoint_ids else None,
        test_set_ids=[str(id) for id in test_set_ids] if test_set_ids else None,
        # Status filters
        status_list=status_list,
        # Date range filters
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/{test_run_id}", response_model=TestRunDetailSchema)
def read_test_run(
    test_run_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a specific test run by ID with its related objects"""
    organization_id, user_id = tenant_context
    db_test_run = crud.get_test_run(
        db, test_run_id=test_run_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    return db_test_run


@router.get("/{test_run_id}/behaviors", response_model=List[schemas.Behavior])
def get_test_run_behaviors(
    test_run_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),  # SECURITY: Extract tenant context
    current_user: User = Depends(require_current_user_or_token),
):
    """Get behaviors that have test results for this test run with organization filtering"""
    organization_id, user_id = tenant_context  # SECURITY: Get tenant context
    behaviors = crud.get_test_run_behaviors(
        db, test_run_id=test_run_id, organization_id=organization_id
    )
    return behaviors


@router.put("/{test_run_id}", response_model=schemas.TestRun)
@handle_database_exceptions(
    entity_name="test run", custom_unique_message="Test run with this configuration already exists"
)
def update_test_run(
    test_run_id: UUID,
    test_run: schemas.TestRunUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update test_run with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_test_run = crud.get_test_run(
        db, test_run_id=test_run_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    # Check if the user has permission to update this test run
    if db_test_run.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to update this test run")

    return crud.update_test_run(
        db=db,
        test_run_id=test_run_id,
        test_run=test_run,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.delete("/{test_run_id}", response_model=schemas.TestRun)
def delete_test_run(
    test_run_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a test run"""
    organization_id, user_id = tenant_context
    db_test_run = crud.get_test_run(
        db, test_run_id=test_run_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")

    # Check if the user has permission to delete this test run
    if db_test_run.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to delete this test run")

    return crud.delete_test_run(
        db=db, test_run_id=test_run_id, organization_id=organization_id, user_id=user_id
    )


@router.get("/{test_run_id}/download", response_class=StreamingResponse)
def download_test_run_results(
    test_run_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Download test run results as CSV"""
    try:
        organization_id, user_id = tenant_context
        # Check if test run exists and user has access
        db_test_run = crud.get_test_run(
            db, test_run_id=test_run_id, organization_id=organization_id, user_id=user_id
        )
        if db_test_run is None:
            raise HTTPException(status_code=404, detail="Test run not found")

        # Get test results data
        test_results_data = get_test_results_for_test_run(
            db, test_run_id, organization_id=str(current_user.organization_id)
        )

        # Convert to CSV
        csv_data = test_run_results_to_csv(test_results_data)

        # Create response
        response = StreamingResponse(iter([csv_data]), media_type="text/csv")
        response.headers["Content-Disposition"] = (
            f"attachment; filename=test_run_{test_run_id}_results.csv"
        )
        return response

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download test run results for {test_run_id}: {str(e)}",
        )
