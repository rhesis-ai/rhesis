"""Observability utilities for Rhesis backend."""

import os
from typing import Dict

from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.logging import logger
from rhesis.sdk.clients import RhesisClient
from rhesis.sdk.decorators import bind_context

# Initialize RhesisClient at module import time (required for @endpoint decorators)
try:
    rhesis_client = RhesisClient.from_environment()
except Exception as e:
    logger.debug(f"RhesisClient initialization deferred (will retry in lifespan): {e}")
    rhesis_client = None


def get_test_context() -> Dict[str, any]:
    """
    Get test context bindings for endpoint decorator with proper resource management.

    **DEVELOPMENT USE ONLY**: This function is used by Rhesis developers during
    development to enable remote testing of @endpoint decorated functions. It is
    automatically disabled in production environments (returns empty dict when
    RHESIS_ORGANIZATION_ID or RHESIS_USER_ID are not set).

    Uses bind_context and generator functions to provide dependencies that need cleanup.
    The @endpoint decorator will automatically handle them as context managers,
    just like FastAPI does. Database sessions are properly closed after use.

    The dictionary can be unpacked directly in @endpoint bind parameter:
        @endpoint(
            bind={
                **get_test_context(),
                "tool_id": os.environ["TEST_TOOL_ID"],
            }
        )

    Returns:
        Dictionary with bindings suitable for @endpoint bind parameter:
        - organization_id: Static organization ID from environment
        - user_id: Static user ID from environment
        - db: Context manager for database session (auto-cleanup via bind_context)

        Returns empty dict in production (when env vars are not set).

        Note: Endpoints should fetch the user object themselves using:
        `user = crud.get_user_by_id(db, user_id)` to avoid extra DB connections.
    """
    # Static values from environment
    org_id = os.getenv("RHESIS_ORGANIZATION_ID")
    user_id = os.getenv("RHESIS_USER_ID")

    # Return empty dict if environment variables are not set
    if not org_id or not user_id:
        logger.warning(
            "RHESIS_ORGANIZATION_ID or RHESIS_USER_ID not set, defaulting to empty dict"
        )
        return {}

    return {
        "organization_id": org_id,  # Static value
        "user_id": user_id,  # Static value
        # Use bind_context to create fresh context manager per call
        "db": bind_context(get_db_with_tenant_variables, org_id, user_id),
    }
