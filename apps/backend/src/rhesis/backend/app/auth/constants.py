import os

# JWT Configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 7 * 24 * 60  # set to 7 days

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