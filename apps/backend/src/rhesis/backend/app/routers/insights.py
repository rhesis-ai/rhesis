from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from rhesis.backend.app import schemas
from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.insights import (
    InsightsValidationError,
    run_ids,
    run_queries,
    run_query,
)

router = APIRouter(prefix="/insights", tags=["insights"])


def insights_filters(
    test_run_ids: Optional[List[UUID]] = Query(None, description="Filter by test run IDs"),
    requirement_ids: Optional[List[UUID]] = Query(None, description="Filter by requirement IDs"),
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
    status_names: Optional[List[str]] = Query(
        None, description="Filter by status names (e.g. test_run status)"
    ),
) -> dict:
    """Shared registry filter query params for GET /insights and GET /insights/ids."""
    filters = {
        "test_run_ids": test_run_ids,
        "requirement_ids": requirement_ids,
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
        "status_names": status_names,
    }
    return {key: value for key, value in filters.items() if value}


def insights_date_range(
    months: Optional[int] = Query(None, description="Last N months (not with start/end)"),
    start_date: Optional[str] = Query(None, description="From this ISO date onwards"),
    end_date: Optional[str] = Query(None, description="Up to this ISO date"),
) -> dict:
    """Optional date window. Omit all for all time; start/end are independent bounds."""
    return {"months": months, "start_date": start_date, "end_date": end_date}


@router.get("/", response_model=schemas.InsightsResponse, **capability(Permission.Insights.READ))
def get_insights(
    entity: str = Query(..., description="Registry entity: test_result, metric, test_run, or test"),
    group_by: List[str] = Query(default=[], description="Dimensions to group by"),
    measures: List[str] = Query(default=["count"], description="Measures to compute"),
    filters: dict = Depends(insights_filters),
    dates: dict = Depends(insights_date_range),
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Generic aggregation endpoint, validated against services/insights/registry.py.

    Every param is checked against the registry entry for `entity` before it
    reaches SQL -- an unknown group_by/measure/filter returns 400, not a query.

    Example: `GET /insights/?entity=test_result&group_by=requirement&measures=count&measures=pass_rate`
    """
    try:
        return run_query(
            db,
            entity=entity,
            group_by=group_by,
            measures=measures,
            filters=filters,
            organization_id=current_user.organization_id,
            **dates,
        )
    except InsightsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/ids",
    response_model=schemas.InsightsIdsResponse,
    **capability(Permission.Insights.READ),
)
def get_insights_ids(
    entity: str = Query(..., description="Registry entity: test_result, metric, test_run, or test"),
    outcome: str = Query(
        "all",
        description="Match pass/fail/all. Only for entities that declare apply_outcome "
        "in the registry (test_result, metric).",
    ),
    filters: dict = Depends(insights_filters),
    dates: dict = Depends(insights_date_range),
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Resolve distinct entity IDs under the same filter universe as GET /insights.

    Returns a flat ID list (not the aggregation envelope). Use this for drill-down
    from a chart slice to a test list -- e.g. failed tests for a requirement/metric/topic.

    Example: `GET /insights/ids?entity=test_result&outcome=fail&test_run_ids=...&requirement_ids=...`
    """
    try:
        return run_ids(
            db,
            entity=entity,
            filters=filters,
            outcome=outcome,
            organization_id=current_user.organization_id,
            **dates,
        )
    except InsightsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/query",
    response_model=Dict[str, schemas.InsightsResponse],
    **capability(Permission.Insights.READ),
)
def query_insights(
    queries: Dict[str, schemas.InsightsQuery],
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Run several named registry queries in one call.

    The body is the map of label -> query directly (no wrapping `queries` key).
    Each entry is validated and executed independently against
    services/insights/registry.py, same as GET /insights. This only batches
    the round trips -- results from different entities are never merged into
    one row set (see services/insights/query_builder.py:run_queries), so the
    caller still assembles per-entity results into whatever shape it needs.

    Example:
        POST /insights/query
        {"topics": {"entity": "test_result", "group_by": ["requirement", "topic"],
                    "measures": ["count", "pass_rate"]},
         "metrics": {"entity": "metric", "group_by": ["requirement_id", "metric_name"],
                     "measures": ["count", "passed", "pass_rate"]}}
    """
    try:
        return run_queries(db, queries, organization_id=current_user.organization_id)
    except InsightsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
