import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import UUID4
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.auth.token_utils import generate_api_token
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.token import TokenCreate, TokenRead, TokenUpdate
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions

router = APIRouter(
    prefix="/tokens",
    tags=["tokens"],
    responses={404: {"description": "Not found"}},
)


@router.post("/")
async def create_api_token(
    request: Request,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    name = data.get("name")
    expires_in_days = data.get("expires_in_days")

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    token_value = generate_api_token()
    token_data = {
        "name": name,
        "token": token_value,
        "token_type": "bearer",
        "token_obfuscated": token_value[:3] + "..." + token_value[-4:],
        "expires_at": (
            datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            if expires_in_days is not None
            else None
        ),
        "user_id": current_user.id,
        "organization_id": current_user.organization_id,
    }

    token_create = TokenCreate(**token_data)
    token = crud.create_token(db=db, token=token_create)

    return JSONResponse(
        content={
            "access_token": token.token,
            "token_type": token.token_type,
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        }
    )


@router.get("/", response_model=List[TokenRead])
@with_count_header(model=models.Token)
async def read_tokens(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """List all active API tokens for the current user"""
    return crud.get_user_tokens(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
    )


@router.get("/{token_id}", response_model=TokenRead)
async def read_token(
    token_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a specific token's details"""
    token = crud.get_token(db=db, token_id=token_id)
    if not token or str(token.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Token not found")
    return token


@router.delete("/{token_id}", status_code=200)
async def delete_token(
    token_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a specific API token. Only the token owner can delete it."""
    # Get the token and verify ownership
    token = crud.get_token(db=db, token_id=token_id)
    if not token or str(token.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Token not found")

    # Delete the token
    crud.revoke_token(db=db, token_id=token_id)
    return {"message": "Token deleted successfully"}


@router.post("/{token_id}/refresh")
async def refresh_token(
    token_id: UUID4,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    print("\n=== Token Refresh Debug ===")
    print(f"1. Original request data: {data}")

    token = crud.get_token(db=db, token_id=token_id)
    print(f"2. Current token expires_at: {token.expires_at}")

    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    if token.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to refresh this token")

    new_token_value = generate_api_token()
    expires_in_days = data.get("expires_in_days")
    print(f"3. Requested expires_in_days: {expires_in_days}")

    expires_at = None
    if expires_in_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=int(expires_in_days))
    print(f"4. Calculated new expires_at: {expires_at}")

    token_update = TokenUpdate(
        token=new_token_value,
        token_obfuscated=new_token_value[:3] + "..." + new_token_value[-4:],
        last_refreshed_at=datetime.now(timezone.utc),
        expires_at=expires_at,
    )
    print(f"5. Token update data: {token_update.dict()}")

    updated_token = crud.update_token(db=db, token_id=token.id, token=token_update)
    print(f"6. Updated token expires_at: {updated_token.expires_at}")

    response = {
        "access_token": updated_token.token,
        "token_type": updated_token.token_type,
        "token_obfuscated": updated_token.token_obfuscated,
        "expires_at": updated_token.expires_at.isoformat() if updated_token.expires_at else None,
        "name": updated_token.name,
    }
    print(f"7. Final response: {response}")
    print("=== End Debug ===\n")

    return JSONResponse(content=response)
