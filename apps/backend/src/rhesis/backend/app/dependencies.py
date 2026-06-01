"""
Dependency injection functions for FastAPI.
"""

import uuid
from functools import lru_cache
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

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


def get_project_context(
    request: Request,
    current_user: User = Depends(require_current_user_or_token),
    x_project_id: Optional[str] = Header(
        default=None,
        alias="X-Project-Id",
        description=(
            "Optional project scope for the request. When supplied, all reads are filtered "
            "to the given project (plus org-wide rows with project_id = NULL) and all writes "
            "are stamped with this project_id. "
            "Value must be a valid UUID that matches an existing project the authenticated user "
            "is a member of; non-members receive **403**. "
            "If omitted, the project_id bound to the API token (if any) is used as a fallback. "
            "If neither is present the request runs without a project scope and sees all "
            "org-wide rows."
        ),
    ),
) -> Optional[str]:
    """
    FastAPI dependency that resolves the active project_id for the current request.

    Resolution order:
      1. ``X-Project-Id`` request header (explicit override)
      2. ``token.project_id`` from the API token used for authentication
         (stored on ``request.state.api_token_project_id`` by the auth layer)
      3. ``None`` — request is not scoped to a specific project

    When a project_id is resolved the dependency validates that the authenticated
    user is a member of that project.  Non-members receive **403**.

    Returns:
        The project UUID as a string, or None if no project scope was requested.
    """
    # 1. Prefer explicit header (FastAPI already parsed it via the Header() annotation)
    project_id_str = x_project_id or request.headers.get("X-Project-Id")

    # 2. Fall back to the project bound to the API token
    if not project_id_str:
        project_id_str = getattr(request.state, "api_token_project_id", None)

    if not project_id_str:
        return None

    # Validate UUID format
    try:
        project_id = uuid.UUID(project_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid X-Project-Id format")

    # Validate membership using a tenant-scoped session so RLS GUCs are set
    # before querying project_membership (which has tenant_isolation RLS).
    from rhesis.backend.app.models.project_membership import ProjectMembership

    org_id = str(current_user.organization_id) if current_user.organization_id else ""
    user_id_str = str(current_user.id) if current_user.id else ""

    with get_db_with_tenant_variables(org_id, user_id_str, "") as db:
        membership = (
            db.query(ProjectMembership)
            .filter_by(
                project_id=project_id,
                user_id=current_user.id,
                organization_id=current_user.organization_id,
            )
            .first()
        )
    if not membership:
        raise HTTPException(
            status_code=403,
            detail=f"User is not a member of project {project_id}",
        )

    return str(project_id)


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


def get_tenant_db_session(
    tenant_context: tuple = Depends(get_tenant_context),
    project_id: Optional[str] = Depends(get_project_context),
):
    """
    FastAPI dependency that provides a database session with automatic session variables.

    Sets PostgreSQL RLS session variables AND binds the RequestScope ContextVar
    (organization_id, user_id, project_id) so the auto-filter / auto-stamp
    listeners are active for the lifetime of the request.

    Returns:
        Session: The database session with full tenant context set
    """
    organization_id, user_id = tenant_context

    with get_db_with_tenant_variables(organization_id, user_id, project_id or "") as db:
        yield db


def get_db_with_tenant_context(
    tenant_context: tuple = Depends(get_tenant_context),
    project_id: Optional[str] = Depends(get_project_context),
):
    """
    FastAPI dependency that provides both a database session and tenant context.

    Automatically sets PostgreSQL session variables for RLS policies while
    also providing explicit tenant context parameters.

    Returns:
        tuple: (db_session, organization_id, user_id)
    """
    organization_id, user_id = tenant_context

    with get_db_with_tenant_variables(organization_id, user_id, project_id or "") as db:
        yield db, organization_id, user_id


# Backward compatibility alias for behavior endpoints
def get_behavior_context(current_user: User = Depends(require_current_user_or_token)):
    """
    DEPRECATED: Use get_tenant_context instead.
    Kept for backward compatibility with behavior endpoints.
    """
    return get_tenant_context(current_user)
