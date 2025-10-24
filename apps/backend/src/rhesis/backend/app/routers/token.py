import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.auth.token_utils import generate_api_token
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.token import (
    TokenCreate,
    TokenCreateResponse,
    TokenRead,
    TokenUpdate,
)
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.encryption import hash_token

router = APIRouter(prefix="/tokens", tags=["tokens"], responses={404: {"description": "Not found"}})


@router.post("/", response_model=TokenCreateResponse)
@handle_database_exceptions(
    entity_name="token", custom_unique_message="Token with this name already exists"
)
def create_token(
    request: Request,
    data: dict = Body(...),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Create token with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during entity creation
    - Direct tenant context injection
    """
    name = data.get("name")
    expires_in_days = data.get("expires_in_days")

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    organization_id, user_id = tenant_context
    token_value = generate_api_token()
    token_data = {
        "name": name,
        "token": token_value,
        "token_hash": hash_token(token_value),
        "token_type": "bearer",
        "token_obfuscated": token_value[:3] + "..." + token_value[-4:],
        "expires_at": (
            datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            if expires_in_days is not None
            else None
        ),
        "user_id": user_id,
        "organization_id": organization_id,
    }

    token_create = TokenCreate(**token_data)
    created_token = crud.create_token(
        db=db, token=token_create, organization_id=organization_id, user_id=user_id
    )

    # Return the special response that includes the actual token value
    return TokenCreateResponse(
        id=created_token.id,
        access_token=created_token.token,
        token_obfuscated=created_token.token_obfuscated,
        token_type=created_token.token_type,
        expires_at=created_token.expires_at,
        name=created_token.name,
    )


@router.get("/", response_model=List[TokenRead])
async def read_tokens(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """List all active API tokens for the current user"""
    organization_id, user_id = tenant_context

    # Set the count header with user-specific token count
    count = crud.count_user_tokens(
        db=db, user_id=current_user.id, filter=filter, organization_id=organization_id
    )
    response.headers["X-Total-Count"] = str(count)

    return crud.get_user_tokens(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
    )


@router.get("/{token_id}", response_model=TokenRead)
def read_token(
    token_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Get token with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during retrieval
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_token = crud.get_token(
        db, token_id=token_id, organization_id=organization_id, user_id=user_id
    )
    if db_token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    return db_token


@router.delete("/{token_id}", response_model=TokenRead)
def delete_token(
    token_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Delete token with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during deletion
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_token = crud.revoke_token(
        db, token_id=token_id, organization_id=organization_id, user_id=user_id
    )
    if db_token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    return db_token


@router.put("/{token_id}", response_model=TokenRead)
def update_token(
    token_id: uuid.UUID,
    token: TokenUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update token with optimized approach - no session variables needed.

    Performance improvements:
    - Completely bypasses database session variables
    - No SET LOCAL commands needed
    - No SHOW queries during update
    - Direct tenant context injection
    """
    organization_id, user_id = tenant_context
    db_token = crud.update_token(
        db, token_id=token_id, token=token, organization_id=organization_id, user_id=user_id
    )
    if db_token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    return db_token


@router.post("/{token_id}/refresh", response_model=TokenCreateResponse)
def refresh_token(
    token_id: uuid.UUID,
    data: dict = Body(...),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Refresh token with new value and expiration"""
    organization_id, user_id = tenant_context

    token = crud.get_token(
        db=db, token_id=token_id, organization_id=organization_id, user_id=user_id
    )
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    new_token_value = generate_api_token()
    expires_in_days = data.get("expires_in_days")

    expires_at = None
    if expires_in_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=int(expires_in_days))

    token_update = TokenUpdate(
        token=new_token_value,
        token_hash=hash_token(new_token_value),
        token_obfuscated=new_token_value[:3] + "..." + new_token_value[-4:],
        last_refreshed_at=datetime.now(timezone.utc),
        expires_at=expires_at,
    )

    updated_token = crud.update_token(
        db=db,
        token_id=token.id,
        token=token_update,
        organization_id=organization_id,
        user_id=user_id,
    )
    if updated_token is None:
        raise HTTPException(status_code=404, detail="Token not found")

    # Return the special response that includes the actual token value
    return TokenCreateResponse(
        id=updated_token.id,
        access_token=updated_token.token,
        token_obfuscated=updated_token.token_obfuscated,
        token_type=updated_token.token_type,
        expires_at=updated_token.expires_at,
        name=updated_token.name,
        last_refreshed_at=updated_token.last_refreshed_at,
    )
