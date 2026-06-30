"""
Dependency injection functions for FastAPI.
"""

import uuid
from functools import lru_cache
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.principal import REQUEST_STATE_API_TOKEN_PROJECT_ID
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


def assert_project_access(
    request: Request,
    current_user: User,
    project_id_str: str,
    db: Session | None = None,
    *,
    invalid_uuid_detail: str = "Invalid project_id format",
) -> str:
    """Validate that *current_user* may access *project_id_str*.

    Raises HTTPException(400) for invalid UUIDs, HTTPException(403) when the
    project does not exist, is soft-deleted, or the caller lacks membership
    (including org-ceiling role bypass via member:manage).

    When *db* is omitted a short-lived tenant-scoped session is opened so
    ``get_project_context`` can validate before the route session exists.
    """
    try:
        project_id = uuid.UUID(project_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=invalid_uuid_detail)

    token_project_id_str = getattr(request.state, REQUEST_STATE_API_TOKEN_PROJECT_ID, None)
    if token_project_id_str and str(project_id) != token_project_id_str:
        raise HTTPException(
            status_code=403,
            detail="Token is scoped to a different project",
        )

    if not current_user.organization_id:
        raise HTTPException(status_code=403, detail="User must be associated with an organization")

    from rhesis.backend.app.models.project import Project
    from rhesis.backend.app.models.project_membership import ProjectMembership

    def _check(session: Session) -> None:
        membership = (
            session.query(ProjectMembership)
            .filter_by(
                project_id=project_id,
                user_id=current_user.id,
                organization_id=current_user.organization_id,
            )
            .first()
        )
        project = session.query(Project).filter_by(id=project_id).first()

        if project is None:
            raise HTTPException(
                status_code=403,
                detail=f"User is not a member of project {project_id}",
            )

        if membership is None:
            from rhesis.backend.app.auth.capabilities import Permission
            from rhesis.backend.app.auth.principal import resolve_principal_from_request
            from rhesis.backend.app.auth.rbac import authorize

            principal = resolve_principal_from_request(current_user, request)
            if not authorize(principal, Permission.Member.MANAGE, project_id=None, db=session):
                raise HTTPException(
                    status_code=403,
                    detail=f"User is not a member of project {project_id}",
                )

    if db is not None:
        _check(db)
    else:
        org_id = str(current_user.organization_id)
        user_id_str = str(current_user.id) if current_user.id else ""
        with get_db_with_tenant_variables(org_id, user_id_str, "") as session:
            _check(session)

    return str(project_id)


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
            "If neither is present the request runs without a project scope and sees only "
            "org-level rows (project_id = NULL); project-scoped rows are NOT returned "
            "(fail-closed)."
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

    When both an explicit header and a project-scoped token are present, the
    values must match — a project-scoped token cannot be used to access a
    different project (403).

    When a project_id is resolved the dependency validates that the authenticated
    user is a member of that project.  Non-members receive **403**.

    Returns:
        The project UUID as a string, or None if no project scope was requested.
        When None, the request is fail-closed to org-level rows (project_id = NULL)
        only -- project-scoped rows are not visible.
    """
    # 1. Prefer explicit header (FastAPI already parsed it via the Header() annotation)
    explicit_project_id = x_project_id or request.headers.get("X-Project-Id")
    token_project_id = getattr(request.state, "api_token_project_id", None)

    # 2. Fall back to the project bound to the API token
    project_id_str = explicit_project_id or token_project_id

    if not project_id_str:
        return None

    return assert_project_access(
        request, current_user, project_id_str, invalid_uuid_detail="Invalid X-Project-Id format"
    )


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

    Sets PostgreSQL RLS session variables AND stores a RequestScope on
    ``session.info['_scope']`` so the auto-filter / auto-stamp listeners are
    active for the lifetime of the request.  The ContextVar is NOT bound here;
    Session.info is the authoritative source for all DB-bound work.

    Returns:
        Session: The database session with full tenant context set
    """
    organization_id, user_id = tenant_context

    with get_db_with_tenant_variables(organization_id, user_id, project_id or "") as db:
        yield db


async def bind_affordance_context(
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Bind the per-request context for server-driven object-level affordances.

    Injected post-registration by ``main.apply_affordance_backstop`` on every route
    whose ``response_model`` carries
    :class:`~rhesis.backend.app.schemas.affordances.WithPermittedActions`. The
    mixin's validator fills ``permitted_actions`` during response serialization by
    reading the context bound here, so no router needs an explicit call.

    Deliberately ``async``: a sync (threadpool) dependency would set the ContextVar
    in a worker thread's context, invisible to response serialization on the event
    loop. As an async ``yield`` dependency it runs in the request's event-loop
    context, and FastAPI serializes the response *inside* the dependency exit stack
    — so the value is live during serialization and reset immediately after. The
    ``db``/``current_user`` dependencies are the same callables the affordance
    routers already declare, so FastAPI deduplicates them (no second session).
    """
    from rhesis.backend.app.auth.affordances import (
        current_affordance_context,
        reset_affordance_context,
        set_affordance_context,
    )

    token = set_affordance_context(current_user, request, db)
    try:
        # Eagerly resolve effective caps here (inside the async dependency) so the
        # synchronous DB/Redis I/O for effective_permissions() does not happen lazily
        # during response serialization, where it would block the event loop.
        ctx = current_affordance_context()
        if ctx is not None:
            ctx.precompute()
        yield
    finally:
        reset_affordance_context(token)


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
