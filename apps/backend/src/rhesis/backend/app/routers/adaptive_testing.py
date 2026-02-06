"""Router for adaptive testing tree endpoints.

Provides views over test set data as adaptive testing trees:
- List all adaptive testing test sets
- Full tree (all nodes including topic markers)
- Tests only (excludes topic markers)
- Topics only (hierarchical topic structure)
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.adaptive_testing import (
    get_adaptive_test_sets,
    get_tree_nodes,
    get_tree_tests,
    get_tree_topics,
)
from rhesis.sdk.adaptive_testing.schemas import TestTreeNode, TopicNode

router = APIRouter(
    prefix="/adaptive_testing",
    tags=["adaptive_testing"],
    responses={404: {"description": "Not found"}},
)


def _resolve_test_set_or_raise(identifier: str, db: Session, organization_id: str):
    """Resolve a test set by identifier (UUID, nano_id, or slug)."""
    db_test_set = crud.resolve_test_set(identifier, db, organization_id)
    if db_test_set is None:
        raise HTTPException(
            status_code=404,
            detail="Test set not found with provided identifier",
        )
    return db_test_set


@router.get(
    "",
    response_model=List[schemas.TestSet],
)
def list_adaptive_test_sets(
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """List all test sets configured for adaptive testing.

    Returns test sets whose behavior includes Adaptive Testing.
    """
    organization_id, _user_id = tenant_context
    return get_adaptive_test_sets(
        db=db,
        organization_id=str(organization_id),
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get(
    "/{test_set_identifier}/tree",
    response_model=List[TestTreeNode],
)
def get_adaptive_tree(
    test_set_identifier: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get the full adaptive testing tree for a test set.

    Returns all nodes including both test nodes and topic markers.
    """
    organization_id, user_id = tenant_context
    db_test_set = _resolve_test_set_or_raise(test_set_identifier, db, str(organization_id))

    return get_tree_nodes(
        db=db,
        test_set_id=db_test_set.id,
        organization_id=str(organization_id),
        user_id=str(user_id),
    )


@router.get(
    "/{test_set_identifier}/tests",
    response_model=List[TestTreeNode],
)
def get_adaptive_tests(
    test_set_identifier: str,
    topic: Optional[str] = Query(
        None,
        description="Filter tests by topic path (e.g. 'Safety/Violence')",
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get only test nodes from the adaptive testing tree.

    Excludes topic marker nodes. Optionally filter by topic path.
    """
    organization_id, user_id = tenant_context
    db_test_set = _resolve_test_set_or_raise(test_set_identifier, db, str(organization_id))

    return get_tree_tests(
        db=db,
        test_set_id=db_test_set.id,
        organization_id=str(organization_id),
        user_id=str(user_id),
        topic=topic,
    )


@router.get(
    "/{test_set_identifier}/topics",
    response_model=List[TopicNode],
)
def get_adaptive_topics(
    test_set_identifier: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get the topic hierarchy from the adaptive testing tree.

    Returns TopicNode objects with path, name, parent_path, and depth.
    """
    organization_id, user_id = tenant_context
    db_test_set = _resolve_test_set_or_raise(test_set_identifier, db, str(organization_id))

    return get_tree_topics(
        db=db,
        test_set_id=db_test_set.id,
        organization_id=str(organization_id),
        user_id=str(user_id),
    )
