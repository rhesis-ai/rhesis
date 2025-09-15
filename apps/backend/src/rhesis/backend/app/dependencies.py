"""
Dependency injection functions for FastAPI.
"""

from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.services.endpoint import EndpointService
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_org_aware_db
from rhesis.backend.app.models.user import User


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
        raise HTTPException(
            status_code=403, 
            detail="User must be associated with an organization"
        )
    
    return organization_id, user_id


# Backward compatibility alias for behavior endpoints
def get_behavior_context(current_user: User = Depends(require_current_user_or_token)):
    """
    DEPRECATED: Use get_tenant_context instead.
    Kept for backward compatibility with behavior endpoints.
    """
    return get_tenant_context(current_user) 