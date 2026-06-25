"""
Rate limiting utilities for the application.
"""

import os

from fastapi import HTTPException, Request, status
from limits import parse as parse_rate_limit
from slowapi import Limiter
from slowapi.util import get_remote_address

TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "1"))


def get_real_ip(request: Request) -> str:
    """Extract the real client IP, respecting trusted proxy depth.

    X-Forwarded-For format: client, proxy1, proxy2 (leftmost = original client).
    With TRUSTED_PROXY_COUNT=1 (single load balancer) we strip the rightmost
    entry (added by our proxy) and return the entry just before it.
    If TRUSTED_PROXY_COUNT=0, use the socket address directly.
    """
    if TRUSTED_PROXY_COUNT == 0:
        return request.client.host if request.client else "unknown"

    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        ips = [ip.strip() for ip in xff.split(",")]
        # Subtract proxies + 1 so we land on the last untrusted entry.
        idx = max(0, len(ips) - TRUSTED_PROXY_COUNT - 1)
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

# EE features that need their own rate-limit constants define them
# alongside their routers and decorate handlers with the shared
# ``limiter`` instance defined above. Core has no per-feature constants.


def hit_post_parse_limit(
    rate_string: str,
    *,
    namespace: str,
    key: str,
) -> None:
    """Apply a rate limit *after* the request body has been parsed.

    The ``@limiter.limit(...)`` decorator runs at routing time, before
    the handler reads the body. That is correct for per-IP limits
    (which need no parsed payload) but useless for any dimension keyed
    on a value the request carries inside the body or
    ``Authorization`` header (e.g. ``client_id`` for token exchange).
    This helper is the post-parse counterpart: call it from inside the
    handler after the keying value is known.

    The rate counter is stored in the same backend as the slowapi
    decorator's, so per-IP and per-key limits compose naturally without
    needing a second Redis connection / namespace.

    Parameters
    ----------
    rate_string:
        Standard ``limits`` rate string (e.g. ``"60/minute"``). Parsed
        on every call -- callers SHOULD treat *rate_string* as a
        constant and pass the same value each time so the parser
        result is cache-friendly.
    namespace:
        Prefix that disambiguates this limit from any other call site
        using the same key shape (e.g. ``"token-exchange:client"``
        vs ``"refresh:client"``). Without a namespace, two endpoints
        keying on ``client_id`` would share a single counter.
    key:
        The post-parse value being throttled (e.g. ``client_id``).

    Raises
    ------
    fastapi.HTTPException
        429 on rate-limit exceeded. The detail is intentionally
        generic so the response cannot serve as an oracle for whether
        the keying value (e.g. a specific ``client_id``) exists.

    Notes
    -----
    Reaches into ``limiter._limiter`` and ``limiter._storage``, which
    are slowapi-private. We accept that coupling because the
    alternative (a parallel redis-keyed counter) doubles the
    infrastructure surface for one feature; the slowapi internals
    we touch (``MovingWindowRateLimiter.hit``) are themselves
    re-exports of the very stable ``limits`` library API.
    """
    item = parse_rate_limit(rate_string)
    full_key = f"{namespace}:{key}"
    # ``hit`` returns True when the request is permitted (counter
    # incremented) and False when the limit was already exceeded.
    if not limiter._limiter.hit(item, full_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
        )
