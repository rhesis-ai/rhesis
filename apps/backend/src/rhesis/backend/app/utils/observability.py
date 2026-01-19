"""Observability utilities for Rhesis backend."""

import os
from typing import Dict, Optional

from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.logging import logger
from rhesis.sdk import CONNECTOR_DISABLED, RhesisClient
from rhesis.sdk.decorators import bind_context

# Global RhesisClient instance (initialized at module import time)
rhesis_client: Optional[RhesisClient] = None


def initialize_rhesis_client() -> Optional[RhesisClient]:
    """
    Initialize RhesisClient for observability.

    The client behavior depends on environment configuration:
    - If RHESIS_CONNECTOR_DISABLE is enabled: Creates a DisabledClient (no-op but registers
      with decorators to prevent runtime errors)
    - If RHESIS_ORGANIZATION_ID/RHESIS_USER_ID are not set AND connector is not explicitly
      disabled: Returns None (production default - no client needed)
    - Otherwise: Creates a full RhesisClient for observability

    Returns:
        Initialized RhesisClient instance (or DisabledClient), or None if not needed
    """
    global rhesis_client

    if rhesis_client is not None:
        return rhesis_client

    # If connector is explicitly disabled, still create the client
    # (SDK will return DisabledClient which registers with decorators)
    if CONNECTOR_DISABLED:
        try:
            # Creates DisabledClient that registers itself with @endpoint decorator
            rhesis_client = RhesisClient()
            return rhesis_client
        except Exception as e:
            logger.warning(f"Failed to initialize DisabledClient: {e}")
            return None

    # If connector is NOT disabled, check for required dev environment variables
    # Skip initialization if not set (production default)
    org_id = os.getenv("RHESIS_ORGANIZATION_ID")
    user_id = os.getenv("RHESIS_USER_ID")
    if not org_id or not user_id:
        logger.info("⏭️  RhesisClient disabled (RHESIS_ORGANIZATION_ID/RHESIS_USER_ID not set)")
        return None

    try:
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
        return {}

    return {
        "organization_id": org_id,  # Static value
        "user_id": user_id,  # Static value
        # Use bind_context to create fresh context manager per call
        "db": bind_context(get_db_with_tenant_variables, org_id, user_id),
    }
