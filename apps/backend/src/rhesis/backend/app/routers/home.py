from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import get_current_user, require_current_user
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User

router = APIRouter(prefix="/home", tags=["home"])


@router.get("/")
async def home(request: Request, current_user: Optional[User] = Depends(get_current_user)):
    # Public endpoint, user is optional
    base_url = str(request.base_url).rstrip("/")
    if current_user:
        return {"message": f"Welcome, {current_user.display_name}!"}

    return {"message": "Welcome! Please log in.", "login_url": f"{base_url}/auth/login"}


@router.get("/protected")
async def protected(current_user: User = Depends(require_current_user)):
    return {"message": f"Welcome, {current_user.display_name}!"}
