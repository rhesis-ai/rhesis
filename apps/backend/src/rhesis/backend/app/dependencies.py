"""
Dependency injection functions for FastAPI.
"""

from functools import lru_cache

from fastapi import Depends, HTTPException

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db, get_db_with_tenant_variables
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.endpoint import EndpointService


@lru_cache()
def get_endpoint_service() -> EndpointService:
    """
    Get or create an EndpointService instance.
    Uses lru_cache to maintain a single instance per process while still allowing
    for proper dependency injection and testing.

    Returns:
        EndpointService: The endpoint service instance
    """
    return EndpointService()


def get_tenant_context(current_user: User = Depends(require_current_user_or_token)):
    """
    FastAPI dependency that provides tenant context for all entity endpoints.

    Returns a tuple of (organization_id, user_id) that can be passed directly
    to the super optimized CRUD functions, completely bypassing session variables.

    This is the core optimization that eliminates:
    - Complex session variable management
    - Redundant SHOW queries during entity creation
    - SET LOCAL commands and transaction complexity

    Performance improvement: Reduces entity creation from 3-4 seconds to ~100ms
    (remaining latency is Cloud SQL Proxy overhead, not application code).
    """
    organization_id = str(current_user.organization_id) if current_user.organization_id else None
    user_id = str(current_user.id) if current_user.id else None

    if not organization_id:
        raise HTTPException(status_code=403, detail="User must be associated with an organization")

    return organization_id, user_id


def get_db_session():
    """
    FastAPI dependency that provides a database session directly.

    This is for routes that need a Session object directly rather than a context manager.
    It properly handles the context manager from get_db() and yields the actual Session.

    Returns:
        Session: The database session
    """
    with get_db() as db:
        yield db


def get_tenant_db_session(tenant_context: tuple = Depends(get_tenant_context)):
    """
    FastAPI dependency that provides a database session with automatic session variables.

    This is a drop-in replacement for get_db_session that automatically sets
    PostgreSQL session variables for RLS policies.

    Returns:
        Session: The database session with session variables set
    """
    organization_id, user_id = tenant_context

    with get_db_with_tenant_variables(organization_id, user_id) as db:
        yield db


def get_db_with_tenant_context(tenant_context: tuple = Depends(get_tenant_context)):
    """
    FastAPI dependency that provides both a database session and tenant context.

    Automatically sets PostgreSQL session variables for RLS policies while
    also providing explicit tenant context parameters.

    Returns:
        tuple: (db_session, organization_id, user_id)
    """
    organization_id, user_id = tenant_context

    with get_db_with_tenant_variables(organization_id, user_id) as db:
        yield db, organization_id, user_id


# Backward compatibility alias for behavior endpoints
def get_behavior_context(current_user: User = Depends(require_current_user_or_token)):
    """
    DEPRECATED: Use get_tenant_context instead.
    Kept for backward compatibility with behavior endpoints.
    """
    return get_tenant_context(current_user)
