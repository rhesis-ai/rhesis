"""Data retrieval utilities for test execution."""

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.test import Test
from rhesis.backend.logging.rhesis_logger import logger


def get_test_and_prompt(
    db: Session, test_id: str, organization_id: Optional[str] = None
) -> Tuple[Test, str, str]:
    """
    Retrieve test and its associated prompt data.

    For single-turn tests, validates that a prompt exists.
    For multi-turn tests, validates that test_configuration has a goal defined.

    Returns:
        Tuple of (test, prompt_content, expected_response)
        For multi-turn tests, prompt_content is empty string and expected_response is empty

    Raises:
        ValueError: If test is not found or validation fails
    """
    # Import here to avoid circular dependency
    from rhesis.backend.tasks.enums import TestType
    from rhesis.backend.tasks.execution.modes import get_test_type

    # Get the test
    test = crud.get_test(db, UUID(test_id), organization_id=organization_id)
    if not test:
        # Fallback query with organization filter
        test_query = db.query(Test).filter(Test.id == UUID(test_id))
        if organization_id:
            test_query = test_query.filter(Test.organization_id == UUID(organization_id))
        test = test_query.first()

        if not test:
            raise ValueError(f"Test with ID {test_id} not found")

    # Determine test type
    test_type = get_test_type(test)

    # Validate based on test type
    if test_type == TestType.MULTI_TURN:
        # Multi-turn tests don't have prompts - they have test_configuration with goal
        test_config = test.test_configuration or {}
        goal = test_config.get("goal")

        if not goal:
            raise ValueError(
                f"Multi-turn test {test_id} has no goal defined in test_configuration. "
                "Multi-turn tests require a 'goal' field in test_configuration."
            )

        # Return empty strings for prompt fields (not used in multi-turn)
        return test, "", ""
    else:
        # Single-turn tests require a prompt
        prompt = test.prompt
        if not prompt:
            raise ValueError(
                f"Single-turn test {test_id} has no associated prompt. "
                "Single-turn tests require a prompt."
            )

        return test, prompt.content, prompt.expected_response or ""


def get_test_metrics(
    test: Test,
    db: Session,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> List:
    """
    Retrieve and validate metrics for a test from its associated behavior.

    Args:
        test: Test model instance
        db: Database session (needed for RLS context)
        organization_id: Organization ID for RLS policies
        user_id: User ID for RLS policies

    Returns:
        List of valid Metric models
    """
    metrics = []
    behavior = test.behavior

    # CRITICAL: Set RLS session variables before accessing relationships
    # Without this, the behavior.metrics query will fail or return empty due to RLS policies
    from rhesis.backend.app.database import set_session_variables

    if organization_id or user_id:
        try:
            set_session_variables(db, organization_id or "", user_id or "")
        except Exception as e:
            logger.error(f"Failed to set RLS session variables: {e}")

    if behavior and behavior.metrics:
        # Return Metric models directly - evaluator accepts them
        metrics = [metric for metric in behavior.metrics if metric.class_name]

        invalid_count = len(behavior.metrics) - len(metrics)
        if invalid_count > 0:
            logger.warning(
                f"Filtered out {invalid_count} metrics without class_name for test {test.id}"
            )

    # Return empty list if no valid metrics found (no defaults in SDK)
    if not metrics:
        logger.warning(f"No valid metrics found for test {test.id}, returning empty list")
        return []

    return metrics
