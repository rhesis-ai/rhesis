"""Observability utilities for Rhesis backend."""

import os
from contextvars import ContextVar
from typing import Dict, Optional

from rhesis.backend.app import crud
from rhesis.backend.app.database import SessionLocal, _set_session_variables
from rhesis.backend.logging import logger
from rhesis.sdk import RhesisClient

# Global RhesisClient instance (initialized at module import time)
rhesis_client: Optional[RhesisClient] = None


def initialize_rhesis_client() -> Optional[RhesisClient]:
    """
    Initialize RhesisClient for observability.

    Returns:
        Initialized RhesisClient instance, or None if initialization fails
    """
    global rhesis_client

    if rhesis_client is not None:
        return rhesis_client

    try:
        rhesis_client = RhesisClient(
            project_id=os.environ["RHESIS_PROJECT_ID"],
            api_key=os.environ["RHESIS_API_KEY"],
            environment=os.getenv("RHESIS_ENVIRONMENT", "development"),
            base_url=os.getenv("RHESIS_BASE_URL", "http://localhost:8080"),
        )
        logger.info("✅ RhesisClient initialized successfully for observability")
        return rhesis_client
    except Exception as e:
        logger.warning(f"Failed to initialize RhesisClient: {e}")
        rhesis_client = None
        return None


def _get_context():
    """Get fresh context values."""
    org_id = os.getenv("RHESIS_ORGANIZATION_ID")
    user_id = os.getenv("RHESIS_USER_ID")
    db = SessionLocal()
    user = crud.get_user_by_id(db, user_id)
    _set_session_variables(db, org_id, user_id)
    return {
        "db": db,
        "user": user,
        "organization_id": org_id,
        "user_id": user_id,
    }


# Context variable to store context per async task/invocation
_context_var: ContextVar[Optional[Dict[str, any]]] = ContextVar("test_context", default=None)

# Initialize RhesisClient at module import time (required for @endpoint decorators)
# This happens before decorators are evaluated, so the client is available when needed
try:
    initialize_rhesis_client()
except Exception as e:
    # If initialization fails at import time, it will be retried in lifespan
    logger.debug(f"RhesisClient initialization deferred (will retry in lifespan): {e}")


def get_test_context() -> Dict[str, any]:
    """
    Get test context bindings for endpoint decorator.

    Returns a dictionary with a mix of static values and callables:
    - Static values (organization_id, user_id): From environment variables
    - Callables (db, user): Fresh database session and user object per invocation

    The context is created once per invocation (per async task) and shared
    across all bind parameters, ensuring efficiency while maintaining freshness.

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
        - db: Callable returning fresh database session
        - user: Callable returning User object from database
    """
    # Static values from environment
    org_id = os.getenv("RHESIS_ORGANIZATION_ID")
    user_id = os.getenv("RHESIS_USER_ID")

    def _get_shared_context():
        """Get or create shared context for this invocation (per async task)."""
        context = _context_var.get()
        if context is None:
            context = _get_context()
            _context_var.set(context)
        return context

    return {
        "organization_id": org_id,
        "user_id": user_id,
        "db": lambda: _get_shared_context()["db"],
        "user": lambda: _get_shared_context()["user"],
    }
