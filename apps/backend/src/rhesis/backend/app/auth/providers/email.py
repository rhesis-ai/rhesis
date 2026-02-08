"""
Email/Password Authentication Provider.

This provider handles traditional email/password authentication,
including user registration and login.
"""

import os
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.providers.base import AuthProvider, AuthUser
from rhesis.backend.app.utils.encryption import hash_password, verify_password
from rhesis.backend.app.utils.redact import redact_email
from rhesis.backend.logging import logger


class EmailProvider(AuthProvider):
    """
    Email/password authentication provider.

    This is the default authentication method that allows users to
    register and log in with an email address and password.

    Environment variables:
        AUTH_EMAIL_PASSWORD_ENABLED: Set to 'true' to enable (default: true)
        AUTH_REGISTRATION_ENABLED: Set to 'true' to allow new registrations (default: true)

    Features:
        - User registration with email/password
        - Login with email/password
        - Password hashing with bcrypt
        - Configurable registration (can be disabled for invite-only)
    """

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "email"

    @property
    def display_name(self) -> str:
        """Return the display name for UI."""
        return "Email"

    @property
    def is_enabled(self) -> bool:
        """
        Check if email/password authentication is enabled.

        Returns True by default unless explicitly disabled.
        """
        enabled = os.getenv("AUTH_EMAIL_PASSWORD_ENABLED", "true").lower()
        return enabled in ("true", "1", "yes")

    @property
    def is_oauth(self) -> bool:
        """Email provider is not OAuth-based."""
        return False

    @property
    def is_registration_enabled(self) -> bool:
        """
        Check if new user registration is enabled.

        Can be disabled for invite-only deployments.
        """
        enabled = os.getenv("AUTH_REGISTRATION_ENABLED", "true").lower()
        return enabled in ("true", "1", "yes")

    async def authenticate(
        self,
        request: Request,
        email: Optional[str] = None,
        password: Optional[str] = None,
        db: Optional[Session] = None,
        **kwargs,
    ) -> AuthUser:
        """
        Authenticate a user with email and password.

        Args:
            request: The FastAPI request object
            email: The user's email address
            password: The user's password
            db: Database session for user lookup
            **kwargs: Additional arguments (ignored)

        Returns:
            AuthUser with the authenticated user's information

        Raises:
            HTTPException: If credentials are invalid or missing
        """
        if not email or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email and password are required",
            )

        if not db:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database session required for email authentication",
            )

        # Import here to avoid circular imports
        from rhesis.backend.app import crud

        # Look up user by email
        user = crud.get_user_by_email(db, email)

        if not user:
            logger.warning(
                "Login attempt for non-existent email: %s",
                redact_email(email),
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Check if user has a password set
        if not user.password_hash:
            logger.warning(
                "Login attempt for user without password: %s. "
                "User may need to set a password or use OAuth.",
                redact_email(email),
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Verify password
        if not verify_password(password, user.password_hash):
            logger.warning("Invalid password attempt for: %s", redact_email(email))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        logger.info("Successful email/password login for: %s", redact_email(email))

        return AuthUser(
            provider_type="email",
            external_id=f"email|{user.id}",
            email=user.email,
            name=user.name,
            given_name=user.given_name,
            family_name=user.family_name,
            picture=user.picture,
            raw_data={"user_id": str(user.id)},
        )

    async def register(
        self,
        request: Request,
        email: str,
        password: str,
        name: Optional[str] = None,
        db: Optional[Session] = None,
        **kwargs,
    ) -> AuthUser:
        """
        Register a new user with email and password.

        Args:
            request: The FastAPI request object
            email: The user's email address
            password: The user's password
            name: Optional display name
            db: Database session for user creation
            **kwargs: Additional arguments (ignored)

        Returns:
            AuthUser with the new user's information

        Raises:
            HTTPException: If registration is disabled or email exists
        """
        if not self.is_registration_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User registration is disabled",
            )

        if not email or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email and password are required",
            )

        if len(password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters",
            )

        if not db:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database session required for registration",
            )

        # Import here to avoid circular imports
        from rhesis.backend.app import crud
        from rhesis.backend.app.schemas import UserCreate
        from rhesis.backend.app.utils.validation import validate_and_normalize_email

        # Validate and normalize email
        try:
            normalized_email = validate_and_normalize_email(email)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        # Check if user already exists
        existing_user = crud.get_user_by_email(db, normalized_email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists",
            )

        # Hash password
        password_hash = hash_password(password)

        # Create user
        user_data = UserCreate(
            email=normalized_email,
            name=name,
            password_hash=password_hash,
            provider_type="email",
            is_active=True,
            is_superuser=False,
        )

        user = crud.create_user(db, user_data)
        logger.info(
            "New user registered via email: %s",
            redact_email(normalized_email),
        )

        return AuthUser(
            provider_type="email",
            external_id=f"email|{user.id}",
            email=user.email,
            name=user.name,
            given_name=user.given_name,
            family_name=user.family_name,
            picture=user.picture,
            raw_data={"user_id": str(user.id)},
        )

    def get_provider_info(self):
        """Get provider information including registration status."""
        info = super().get_provider_info()
        info["registration_enabled"] = self.is_registration_enabled
        return info
