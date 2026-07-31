from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from rhesis.backend.app import schemas
from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.insights import InsightsValidationError, run_batch, run_query

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/", response_model=schemas.InsightsResponse, **capability(Permission.Insights.READ))
def get_insights(
    entity: str = Query(..., description="Registry entity: test_result, metric, test_run, or test"),
    group_by: List[str] = Query(default=[], description="Dimensions to group by"),
    measures: List[str] = Query(default=["count"], description="Measures to compute"),
    months: int = Query(6, description="Months of historical data to include (default: 6)"),
    start_date: Optional[str] = Query(
        None, description="Start date (ISO format, overrides months)"
    ),
    end_date: Optional[str] = Query(None, description="End date (ISO format, overrides months)"),
    test_run_ids: Optional[List[UUID]] = Query(None, description="Filter by test run IDs"),
    behavior_ids: Optional[List[UUID]] = Query(None, description="Filter by behavior IDs"),
    category_ids: Optional[List[UUID]] = Query(None, description="Filter by category IDs"),
    topic_ids: Optional[List[UUID]] = Query(None, description="Filter by topic IDs"),
    status_ids: Optional[List[UUID]] = Query(None, description="Filter by test status IDs"),
    test_ids: Optional[List[UUID]] = Query(None, description="Filter by test IDs"),
    test_type_ids: Optional[List[UUID]] = Query(None, description="Filter by test type IDs"),
    user_ids: Optional[List[UUID]] = Query(None, description="Filter by test creator user IDs"),
    assignee_ids: Optional[List[UUID]] = Query(None, description="Filter by assignee user IDs"),
    owner_ids: Optional[List[UUID]] = Query(None, description="Filter by test owner user IDs"),
    prompt_ids: Optional[List[UUID]] = Query(None, description="Filter by prompt IDs"),
    test_set_ids: Optional[List[UUID]] = Query(None, description="Filter by test set IDs"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    metric_names: Optional[List[str]] = Query(None, description="Filter by metric names"),
    endpoint_ids: Optional[List[UUID]] = Query(None, description="Filter by endpoint IDs"),
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Generic aggregation endpoint, validated against services/insights/registry.py.

    Every param is checked against the registry entry for `entity` before it
    reaches SQL -- an unknown group_by/measure/filter returns 400, not a query.

    Example: `GET /insights?entity=test_result&group_by=behavior&measures=count,pass_rate`
    """
    filters = {
        "test_run_ids": test_run_ids,
        "behavior_ids": behavior_ids,
        "category_ids": category_ids,
        "topic_ids": topic_ids,
        "status_ids": status_ids,
        "test_ids": test_ids,
        "test_type_ids": test_type_ids,
        "user_ids": user_ids,
        "assignee_ids": assignee_ids,
        "owner_ids": owner_ids,
        "prompt_ids": prompt_ids,
        "test_set_ids": test_set_ids,
        "tags": tags,
        "metric_names": metric_names,
        "endpoint_ids": endpoint_ids,
    }
    filters = {key: value for key, value in filters.items() if value}

    try:
        return run_query(
            db,
            entity=entity,
            group_by=group_by,
            measures=measures,
            filters=filters,
            months=months,
            start_date=start_date,
            end_date=end_date,
            organization_id=current_user.organization_id,
        )
    except InsightsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/batch",
    response_model=schemas.InsightsBatchResponse,
    **capability(Permission.Insights.READ),
)
def get_insights_batch(
    request: schemas.InsightsBatchRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Run several named registry queries in one call.

    Each entry in `queries` is validated and executed independently against
    services/insights/registry.py, same as GET /insights. This only batches
    the round trips -- results from different entities are never merged into
    one row set (see services/insights/query_builder.py:run_batch), so the
    caller still assembles per-entity results into whatever shape it needs.

    Example:
        POST /insights/batch
        {"queries": {
            "topics": {"entity": "test_result", "group_by": ["behavior", "topic"],
                       "measures": ["count", "pass_rate"]},
            "metrics": {"entity": "metric", "group_by": ["behavior_id", "metric_name"],
                        "measures": ["count", "passed", "pass_rate"]}
        }}
    """
    try:
        results = run_batch(db, request.queries, organization_id=current_user.organization_id)
    except InsightsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return schemas.InsightsBatchResponse(results=results)
