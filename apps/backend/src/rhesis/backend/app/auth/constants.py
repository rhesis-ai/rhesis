import os
from enum import Enum


class AuthProviderType(str, Enum):
    """Authentication provider types for user accounts."""

    EMAIL = "email"
    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"
    OIDC = "oidc"
    UNKNOWN = "unknown"


# Refresh token configuration
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7))  # fallback to 7 days

# Absolute session lifetime cap (days). Even an actively-used session must
# re-authenticate once its refresh-token family is this old, regardless of the
# sliding inactivity window. Bounds how long a single login can live.
AUTH_ABSOLUTE_SESSION_MAX_DAYS = int(os.getenv("AUTH_ABSOLUTE_SESSION_MAX_DAYS", 30))

# Auth Messages
UNAUTHORIZED_MESSAGE = "Authentication required"


class AuthenticationMethod:
    SESSION = "session"
    BEARER = "bearer"
    JWT = "jwt"
