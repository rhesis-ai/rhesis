"""Annotations list — flattened human reviews across test results and traces."""

from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.auth.principal import resolve_principal_from_request
from rhesis.backend.app.auth.rbac import authorize, project_id_from_scope
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.schemas.annotation import AnnotationListItem
from rhesis.backend.app.services.annotations import list_annotations

router = RhesisRouter(
    prefix="/annotations",
    tags=["annotations"],
    responses={404: {"description": "Not found"}},
)

TEST_RESULT_READ = Permission.TestResult.READ
TELEMETRY_READ = "telemetry:read"


@router.get(
    "/",
    response_model=List[AnnotationListItem],
)
def read_annotations(
    request: Request,
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    source: Optional[Literal["test_result", "trace"]] = Query(
        None, description="Filter to one parent entity type"
    ),
    search: Optional[str] = Query(
        None, description="Search comments, annotator, target, or rating"
    ),
    resolved: Optional[bool] = Query(None, description="Filter by open (false) or resolved (true)"),
    rating: Optional[Literal["Pass", "Fail"]] = Query(
        None, description="Filter by Pass/Fail rating"
    ),
    target_type: Optional[Literal["test_result", "trace", "metric", "turn"]] = Query(
        None, description="Filter by review target type"
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
) -> List[AnnotationListItem]:
    """List human annotations (reviews) across test results and traces.

    Dual-gated: callers need ``test_result:read`` and/or ``telemetry:read``.
    Each source branch is included only when the matching permission is present.
    """
    organization_id, _user_id = tenant_context
    principal = resolve_principal_from_request(current_user, request)
    project_id = project_id_from_scope(db)
    project_id_str = str(project_id) if project_id else None

    can_read_test_results = authorize(principal, TEST_RESULT_READ, project_id=project_id, db=db)
    can_read_traces = authorize(principal, TELEMETRY_READ, project_id=project_id, db=db)

    if not can_read_test_results and not can_read_traces:
        raise HTTPException(
            status_code=403,
            detail=(f"Permission denied: requires {TEST_RESULT_READ} or {TELEMETRY_READ}"),
            headers={"X-Accepted-Permissions": f"{TEST_RESULT_READ}, {TELEMETRY_READ}"},
        )

    if source == "test_result" and not can_read_test_results:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: {TEST_RESULT_READ}",
            headers={"X-Accepted-Permissions": str(TEST_RESULT_READ)},
        )
    if source == "trace" and not can_read_traces:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: {TELEMETRY_READ}",
            headers={"X-Accepted-Permissions": str(TELEMETRY_READ)},
        )

    include_test_results = can_read_test_results and source in (None, "test_result")
    include_traces = can_read_traces and source in (None, "trace")

    items, total_count = list_annotations(
        db,
        organization_id=organization_id,
        project_id=project_id_str,
        include_test_results=include_test_results,
        include_traces=include_traces,
        source=source,
        search=search,
        resolved=resolved,
        rating=rating,
        target_type=target_type,
        skip=skip,
        limit=limit,
    )
    response.headers["X-Total-Count"] = str(total_count)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return items
