"""Observability utilities for Rhesis backend."""

import os
from functools import partial
from typing import Dict, Optional

from rhesis.backend.app import crud
from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.logging import logger
from rhesis.sdk import RhesisClient

# Global RhesisClient instance (initialized at module import time)
rhesis_client: Optional[RhesisClient] = None


def initialize_rhesis_client() -> Optional[RhesisClient]:
    """
    Initialize RhesisClient for observability.

    When RHESIS_CONNECTOR_DISABLE=true, this will return a DisabledClient that
    performs no operations but maintains the same interface.

    Returns:
        Initialized RhesisClient instance (or DisabledClient), or None if initialization fails
    """
    global rhesis_client

    if rhesis_client is not None:
        return rhesis_client

    try:
        # Note: When RHESIS_CONNECTOR_DISABLE=true, RhesisClient() returns a DisabledClient
        # that accepts any parameters and performs no operations
        rhesis_client = RhesisClient(
            project_id=os.getenv("RHESIS_PROJECT_ID"),
            api_key=os.getenv("RHESIS_API_KEY"),
            environment=os.getenv("RHESIS_ENVIRONMENT", "development"),
            base_url=os.getenv("RHESIS_BASE_URL", "http://localhost:8080"),
        )
        if not getattr(rhesis_client, "is_disabled", False):
            logger.info("✅ RhesisClient initialized successfully for observability")
        return rhesis_client
    except Exception as e:
        logger.warning(f"Failed to initialize RhesisClient: {e}")
        rhesis_client = None
        return None


# Initialize RhesisClient at module import time (required for @endpoint decorators)
# This happens before decorators are evaluated, so the client is available when needed
try:
    initialize_rhesis_client()
except Exception as e:
    # If initialization fails at import time, it will be retried in lifespan
    logger.debug(f"RhesisClient initialization deferred (will retry in lifespan): {e}")


def get_test_context() -> Dict[str, any]:
    """
    Get test context bindings for endpoint decorator with proper resource management.

    Uses generator functions (yield) to provide dependencies that need cleanup.
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
        - db: Generator-based dependency for database session (auto-cleanup)
        - user: Generator-based dependency for User object (auto-cleanup)
    """
    # Static values from environment
    org_id = os.getenv("RHESIS_ORGANIZATION_ID")
    user_id = os.getenv("RHESIS_USER_ID")

    # Return empty dict if environment variables are not set
    if not org_id or not user_id:
        return {}

    def user_dependency():
        """
        Generator-based dependency for user object.

        Creates a fresh database session to fetch the user, then
        automatically closes it to prevent connection leaks.
        """
        with get_db_with_tenant_variables(org_id, user_id) as db:
            user = crud.get_user_by_id(db, user_id)
            yield user

    return {
        "organization_id": org_id,  # Static value
        "user_id": user_id,  # Static value
        # Use partial to bind parameters - decorator handles context manager cleanup
        "db": partial(get_db_with_tenant_variables, org_id, user_id),
        "user": user_dependency,  # Generator-based dependency
    }
