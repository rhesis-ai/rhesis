"""Router for adaptive testing CRUD operations.

Provides REST endpoints for managing test tree data within a TestSet,
including operations on topics and tests.

Endpoints:
    Topics:
        GET    /adaptive-testing/{test_set_id}/topics          - List all topics
        GET    /adaptive-testing/{test_set_id}/topics/{path}   - Get topic by path
        POST   /adaptive-testing/{test_set_id}/topics          - Create topic
        PUT    /adaptive-testing/{test_set_id}/topics/{path}   - Update topic
        DELETE /adaptive-testing/{test_set_id}/topics/{path}   - Delete topic

    Tests:
        GET    /adaptive-testing/{test_set_id}/tests           - List all tests
        GET    /adaptive-testing/{test_set_id}/tests/{id}      - Get test by ID
        POST   /adaptive-testing/{test_set_id}/tests           - Create test
        PUT    /adaptive-testing/{test_set_id}/tests/{id}      - Update test
        DELETE /adaptive-testing/{test_set_id}/tests/{id}      - Delete test

    Tree:
        GET    /adaptive-testing/{test_set_id}/validate        - Validate tree
        GET    /adaptive-testing/{test_set_id}/stats           - Get tree stats
"""

from functools import lru_cache
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas import adaptive_testing as schemas
from rhesis.backend.app.services.adaptive_testing import AdaptiveTestingService
from rhesis.backend.logging import logger

router = APIRouter(
    prefix="/adaptive-testing",
    tags=["adaptive-testing"],
    responses={404: {"description": "Not found"}},
)


@lru_cache()
def get_adaptive_testing_service() -> AdaptiveTestingService:
    """Get singleton instance of AdaptiveTestingService."""
    return AdaptiveTestingService()


# =============================================================================
# Topic Endpoints
# =============================================================================


@router.get("/{test_set_id}/topics", response_model=List[schemas.Topic])
async def list_topics(
    test_set_id: UUID,
    parent: Optional[str] = Query(None, description="Parent topic path to get children of"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    service: AdaptiveTestingService = Depends(get_adaptive_testing_service),
):
    """Get all topics or children of a parent topic.

    Args:
        test_set_id: The test set identifier
        parent: Optional parent path to filter children
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of topics
    """
    organization_id, user_id = tenant_context
    try:
        return service.get_topics(
            db=db,
            test_set_id=test_set_id,
            organization_id=organization_id,
            parent=parent,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{test_set_id}/topics/{topic_path:path}", response_model=schemas.Topic)
async def get_topic(
    test_set_id: UUID,
    topic_path: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    service: AdaptiveTestingService = Depends(get_adaptive_testing_service),
):
    """Get a specific topic by path.

    Args:
        test_set_id: The test set identifier
        topic_path: The topic path (URL-encoded)
        db: Database session
        current_user: Current authenticated user

    Returns:
        The topic
    """
    organization_id, user_id = tenant_context
    try:
        topic = service.get_topic(
            db=db,
            test_set_id=test_set_id,
            topic_path=topic_path,
            organization_id=organization_id,
        )
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic '{topic_path}' not found")
        return topic
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{test_set_id}/topics", response_model=schemas.Topic, status_code=201)
async def create_topic(
    test_set_id: UUID,
    topic: schemas.TopicCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    service: AdaptiveTestingService = Depends(get_adaptive_testing_service),
):
    """Create a new topic.

    Args:
        test_set_id: The test set identifier
        topic: Topic data to create
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created topic
    """
    organization_id, user_id = tenant_context
    try:
        return service.create_topic(
            db=db,
            test_set_id=test_set_id,
            topic=topic,
            organization_id=organization_id,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create topic: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create topic: {str(e)}")


@router.put("/{test_set_id}/topics/{topic_path:path}", response_model=schemas.Topic)
async def update_topic(
    test_set_id: UUID,
    topic_path: str,
    update: schemas.TopicUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    service: AdaptiveTestingService = Depends(get_adaptive_testing_service),
):
    """Update a topic (rename or move).

    Args:
        test_set_id: The test set identifier
        topic_path: The topic path to update
        update: Update data (new_name for rename, new_path for move)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated topic
    """
    organization_id, user_id = tenant_context
    try:
        topic = service.update_topic(
            db=db,
            test_set_id=test_set_id,
            topic_path=topic_path,
            update=update,
            organization_id=organization_id,
            user_id=user_id,
        )
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic '{topic_path}' not found")
        return topic
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update topic: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update topic: {str(e)}")


@router.delete("/{test_set_id}/topics/{topic_path:path}")
async def delete_topic(
    test_set_id: UUID,
    topic_path: str,
    move_tests_to_parent: bool = Query(
        True,
        description=(
            "If True, move tests to parent and lift subtopics. "
            "If False, delete everything under this topic."
        ),
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    service: AdaptiveTestingService = Depends(get_adaptive_testing_service),
):
    """Delete a topic.

    Args:
        test_set_id: The test set identifier
        topic_path: The topic path to delete
        move_tests_to_parent: Whether to move tests to parent
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of deleted node IDs
    """
    organization_id, user_id = tenant_context
    try:
        options = schemas.TopicDelete(move_tests_to_parent=move_tests_to_parent)
        deleted_ids = service.delete_topic(
            db=db,
            test_set_id=test_set_id,
            topic_path=topic_path,
            options=options,
            organization_id=organization_id,
            user_id=user_id,
        )
        return {"deleted_ids": deleted_ids, "count": len(deleted_ids)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete topic: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete topic: {str(e)}")


# =============================================================================
# Test Endpoints
# =============================================================================


@router.get("/{test_set_id}/tests", response_model=List[schemas.TestNode])
async def list_tests(
    test_set_id: UUID,
    topic: Optional[str] = Query(None, description="Filter by topic path"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    service: AdaptiveTestingService = Depends(get_adaptive_testing_service),
):
    """Get all tests in the test tree.

    Args:
        test_set_id: The test set identifier
        topic: Optional topic to filter by
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of test nodes
    """
    organization_id, user_id = tenant_context
    try:
        return service.get_tests(
            db=db,
            test_set_id=test_set_id,
            organization_id=organization_id,
            topic=topic,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{test_set_id}/tests/{test_id}", response_model=schemas.TestNode)
async def get_test(
    test_set_id: UUID,
    test_id: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    service: AdaptiveTestingService = Depends(get_adaptive_testing_service),
):
    """Get a specific test by ID.

    Args:
        test_set_id: The test set identifier
        test_id: The test node ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        The test node
    """
    organization_id, user_id = tenant_context
    try:
        test = service.get_test(
            db=db,
            test_set_id=test_set_id,
            test_id=test_id,
            organization_id=organization_id,
        )
        if not test:
            raise HTTPException(status_code=404, detail=f"Test '{test_id}' not found")
        return test
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{test_set_id}/tests", response_model=schemas.TestNode, status_code=201)
async def create_test(
    test_set_id: UUID,
    test: schemas.TestNodeCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    service: AdaptiveTestingService = Depends(get_adaptive_testing_service),
):
    """Create a new test node.

    Args:
        test_set_id: The test set identifier
        test: Test data to create
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created test node
    """
    organization_id, user_id = tenant_context
    try:
        return service.create_test(
            db=db,
            test_set_id=test_set_id,
            test=test,
            organization_id=organization_id,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create test: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create test: {str(e)}")


@router.put("/{test_set_id}/tests/{test_id}", response_model=schemas.TestNode)
async def update_test(
    test_set_id: UUID,
    test_id: str,
    test: schemas.TestNodeUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    service: AdaptiveTestingService = Depends(get_adaptive_testing_service),
):
    """Update a test node.

    Args:
        test_set_id: The test set identifier
        test_id: The test node ID
        test: Update data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated test node
    """
    organization_id, user_id = tenant_context
    try:
        updated = service.update_test(
            db=db,
            test_set_id=test_set_id,
            test_id=test_id,
            test=test,
            organization_id=organization_id,
            user_id=user_id,
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"Test '{test_id}' not found")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update test: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update test: {str(e)}")


@router.delete("/{test_set_id}/tests/{test_id}")
async def delete_test(
    test_set_id: UUID,
    test_id: str,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    service: AdaptiveTestingService = Depends(get_adaptive_testing_service),
):
    """Delete a test node.

    Args:
        test_set_id: The test set identifier
        test_id: The test node ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Success status
    """
    organization_id, user_id = tenant_context
    try:
        deleted = service.delete_test(
            db=db,
            test_set_id=test_set_id,
            test_id=test_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Test '{test_id}' not found")
        return {"deleted": True, "test_id": test_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete test: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete test: {str(e)}")


# =============================================================================
# Tree Endpoints
# =============================================================================


@router.get("/{test_set_id}/validate", response_model=schemas.TreeValidation)
async def validate_tree(
    test_set_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    service: AdaptiveTestingService = Depends(get_adaptive_testing_service),
):
    """Validate the test tree structure.

    Checks that all topics used by tests have corresponding topic markers.

    Args:
        test_set_id: The test set identifier
        db: Database session
        current_user: Current authenticated user

    Returns:
        Validation results
    """
    organization_id, user_id = tenant_context
    try:
        return service.validate_tree(
            db=db,
            test_set_id=test_set_id,
            organization_id=organization_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{test_set_id}/stats", response_model=schemas.TreeStats)
async def get_tree_stats(
    test_set_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
    service: AdaptiveTestingService = Depends(get_adaptive_testing_service),
):
    """Get statistics about the test tree.

    Args:
        test_set_id: The test set identifier
        db: Database session
        current_user: Current authenticated user

    Returns:
        Tree statistics including total tests, topics, and tests per topic
    """
    organization_id, user_id = tenant_context
    try:
        return service.get_tree_stats(
            db=db,
            test_set_id=test_set_id,
            organization_id=organization_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
