import os
from enum import Enum


class AuthProviderType(str, Enum):
    """Authentication provider types for user accounts."""

    EMAIL = "email"
    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"
    UNKNOWN = "unknown"


# JWT Configuration
ALGORITHM = "HS256"
# Short-lived access token (refreshed via refresh token rotation)
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 15)
)  # fallback to 15 minutes

# Refresh token configuration
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7))  # fallback to 7 days

# Auth Messages
UNAUTHORIZED_MESSAGE = "Authentication required"

# Frontend Configuration
FRONTEND_DOMAINS = [
    "app.rhesis.ai",
    "dev-app.rhesis.ai",  # development environment
    "localhost:3000",  # development
]


class AuthenticationMethod:
    SESSION = "session"
    BEARER = "bearer"
    JWT = "jwt"
