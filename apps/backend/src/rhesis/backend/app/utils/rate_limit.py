"""
Rate limiting utilities for the application.
"""

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "1"))


def get_real_ip(request: Request) -> str:
    """Extract the real client IP, respecting trusted proxy depth.

    If TRUSTED_PROXY_COUNT=1 (default, single load balancer), use the
    last entry in X-Forwarded-For. If 0, use the socket address directly.
    """
    if TRUSTED_PROXY_COUNT == 0:
        return request.client.host if request.client else "unknown"

    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        ips = [ip.strip() for ip in xff.split(",")]
        idx = max(0, len(ips) - TRUSTED_PROXY_COUNT)
        return ips[idx]

    return request.client.host if request.client else "unknown"


# Create limiter instance with trusted-proxy-aware IP extraction
limiter = Limiter(key_func=get_real_ip, default_limits=["1000/day", "100/hour"])


def get_user_identifier(request: Request) -> str:
    """
    Get a unique identifier for rate limiting.
    Uses user ID if available, otherwise falls back to IP address.
    """
    # Try to get user ID from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    # Fall back to IP address
    return get_remote_address(request)


# Create user-aware limiter
user_limiter = Limiter(key_func=get_user_identifier, default_limits=["1000/day", "100/hour"])

# Rate limits for different operations
INVITATION_RATE_LIMIT = "10/hour"  # Max 10 invitations per hour per user
BULK_INVITATION_RATE_LIMIT = "3/hour"  # Max 3 bulk invitations per hour per user

# Feedback endpoint rate limits (per IP, public endpoint)
FEEDBACK_RATE_LIMIT = "5/hour"  # Max 5 feedback submissions per hour per IP

# Auth endpoint rate limits (per IP, no auth yet)
AUTH_FORGOT_PASSWORD_LIMIT = "5/hour"
AUTH_RESEND_VERIFICATION_LIMIT = "5/hour"
AUTH_MAGIC_LINK_LIMIT = "5/hour"
AUTH_LOGIN_EMAIL_LIMIT = "20/hour"
AUTH_REGISTER_LIMIT = "10/hour"

# SSO endpoint rate limits (per IP, pre-auth)
SSO_LOGIN_RATE_LIMIT = "10/minute"
SSO_CALLBACK_RATE_LIMIT = "10/minute"
SSO_TEST_CONNECTION_RATE_LIMIT = "5/minute"
SSO_ADMIN_RATE_LIMIT = "20/minute"
