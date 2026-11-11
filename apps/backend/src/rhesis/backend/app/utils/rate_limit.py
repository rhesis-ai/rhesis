"""
Rate limiting utilities for the application.
"""

import ipaddress
import logging
import os
from typing import Optional
from urllib.parse import urlparse, urlunparse

from fastapi import HTTPException, Request, status
from limits import RateLimitItem, parse_many
from slowapi import Limiter
from slowapi.middleware import _find_route_handler, _should_exempt, async_check_limits
from starlette.types import ASGIApp, Receive, Scope, Send

from rhesis.backend.app.config.settings import get_redis_settings
from rhesis.backend.app.services.redis_constants import RedisDatabase

logger = logging.getLogger(__name__)

TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "1"))

#: The browser's IP, passed on by in-cluster callers (the Next.js server, the MCP server).
CLIENT_IP_HEADER = "X-Rhesis-Client-IP"


def _in_cluster_client_ip(request: Request) -> Optional[str]:
    """The IP an in-cluster caller passed on for the browser it is serving.

    The UI's server reaches the backend inside the cluster, not through the
    ingress, so the peer is the frontend pod. The header is trusted only from a
    private or loopback peer, and only when there is no X-Forwarded-For: the
    ingress always adds that, so a public caller cannot use the header.
    """
    claimed = request.headers.get(CLIENT_IP_HEADER)
    if not claimed or "x-forwarded-for" in request.headers or not request.client:
        return None
    try:
        peer = ipaddress.ip_address(request.client.host)
        client_ip = ipaddress.ip_address(claimed.strip())
    except ValueError:
        return None
    if not (peer.is_private or peer.is_loopback):
        return None
    return str(client_ip)


def get_real_ip(request: Request) -> str:
    """Extract the real client IP, respecting trusted proxy depth.

    X-Forwarded-For format: client, proxy1, proxy2 (leftmost = original client).
    With TRUSTED_PROXY_COUNT=1 (single load balancer) we strip the rightmost
    entry (added by our proxy) and return the entry just before it.
    If TRUSTED_PROXY_COUNT=0, use the socket address directly.
    An in-cluster caller's ``X-Rhesis-Client-IP`` comes first.
    """
    in_cluster = _in_cluster_client_ip(request)
    if in_cluster:
        return in_cluster

    if TRUSTED_PROXY_COUNT == 0:
        return request.client.host if request.client else "unknown"

    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        ips = [ip.strip() for ip in xff.split(",")]
        # Subtract proxies + 1 so we land on the last untrusted entry.
        idx = max(0, len(ips) - TRUSTED_PROXY_COUNT - 1)
        return ips[idx]

    return request.client.host if request.client else "unknown"


def rate_limit_ip_key(request: Request) -> str:
    """The client IP as a rate-limit key, with IPv6 collapsed to its /64.

    One IPv6 subscriber usually holds a whole /64, so keying on the full
    address would hand them a fresh bucket per address. ``get_real_ip`` keeps
    the full address for the audit log.
    """
    ip = get_real_ip(request)
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if address.version == 4:
        return ip
    if address.ipv4_mapped:
        return str(address.ipv4_mapped)
    return str(ipaddress.ip_network(f"{address}/64", strict=False))


#: Applied by DefaultRateLimitMiddleware, per client IP and per route, to every route
#: without its own limit. A flood guard sized well above polling, SDK and NAT
#: traffic; costly routes carry tighter per-user limits.
DEFAULT_RATE_LIMIT = "1200/minute"

#: The middleware calls Redis on the event loop, so a stalled Redis must fail
#: fast and drop to the memory fallback rather than hold up the whole worker.
_REDIS_TIMEOUT_SECONDS = 0.5


def rate_limit_storage_uri() -> str:
    """Counters live in Redis, so every worker and pod shares one count."""
    parsed = urlparse(get_redis_settings().broker_url)
    return urlunparse(parsed._replace(path=f"/{RedisDatabase.RATE_LIMITS}"))


def build_limiter(storage_uri: Optional[str] = None) -> Limiter:
    """A limiter on shared storage.

    If Redis is unreachable it falls back to per-process memory with a warning
    and probes Redis again with backoff (fail open, but still bounded per
    process). Failing closed would make Redis an outage for login and every
    other route; the monthly quotas stay enforced either way.

    slowapi itself reads ``RATELIMIT_ENABLED`` from the environment (or ``.env``)
    here, so ``RATELIMIT_ENABLED=false`` turns every limit off.
    """
    uri = storage_uri or rate_limit_storage_uri()
    options = {}
    if uri.startswith(("redis://", "rediss://")):
        options = {
            "socket_connect_timeout": _REDIS_TIMEOUT_SECONDS,
            "socket_timeout": _REDIS_TIMEOUT_SECONDS,
        }
    return Limiter(
        key_func=rate_limit_ip_key,
        default_limits=[DEFAULT_RATE_LIMIT],
        storage_uri=uri,
        storage_options=options,
        in_memory_fallback_enabled=True,
        # One bucket per route function, so path ids cannot spread the count.
        key_style="endpoint",
    )


limiter = build_limiter()


class DefaultRateLimitMiddleware:
    """Apply the limiter's default limit to every route without its own.

    Used instead of slowapi's ``SlowAPIASGIMiddleware``, which re-sends
    ``http.response.start`` before each body chunk and so breaks streamed
    responses. This one checks the limit and leaves ``send`` alone (rate limit
    headers are off, so there is nothing to inject).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        app = scope.get("app")
        active = getattr(getattr(app, "state", None), "limiter", None)
        if scope["type"] == "http" and active is not None and active.enabled:
            handler = _find_route_handler(app.routes, scope)
            if not _should_exempt(active, handler):
                request = Request(scope, receive=receive, send=send)
                error_response, _ = await async_check_limits(active, request, handler, app)
                if error_response is not None:
                    await error_response(scope, receive, send)
                    return
        await self.app(scope, receive, send)


def get_user_identifier(request: Request) -> str:
    """Key on the signed-in account, else on the client IP.

    Use with ``@limiter.limit(..., key_func=get_user_identifier)``: the
    decorator runs after the route's auth dependency has set ``request.state.user``.
    """
    user = getattr(request.state, "user", None)
    user_id = getattr(user, "id", None)
    if user_id:
        return f"user:{user_id}"
    return rate_limit_ip_key(request)


# Rate limits for different operations
INVITATION_RATE_LIMIT = "10/hour"  # Max 10 invitations per hour per user
BULK_INVITATION_RATE_LIMIT = "3/hour"  # Max 3 bulk invitations per hour per user

# Per-user limits for routes that call an LLM, call a user's endpoint, or
# start a job (applied with ``dependencies.per_user_rate_limit``).
GENERATION_RATE_LIMIT = "20/minute;300/hour"
EXECUTION_RATE_LIMIT = "30/minute;500/hour"
PROBE_RATE_LIMIT = "60/minute;1000/hour"
# Hosted-model calls (the SDK's default model and self-host relays use these);
# token quotas meter the cost, this only stops one account fanning out over IPs.
INFERENCE_RATE_LIMIT = "1200/minute"

# Feedback endpoint rate limits (per IP, public endpoint)
FEEDBACK_RATE_LIMIT = "5/hour"  # Max 5 feedback submissions per hour per IP

# Auth endpoint rate limits (per IP, no auth yet)
AUTH_FORGOT_PASSWORD_LIMIT = "5/hour"
AUTH_RESEND_VERIFICATION_LIMIT = "5/hour"
AUTH_MAGIC_LINK_LIMIT = "5/hour"
AUTH_LOGIN_EMAIL_LIMIT = "20/hour"
AUTH_REGISTER_LIMIT = "10/hour"
AUTH_TERMS_STATUS_LIMIT = "30/hour"
AUTH_CHANGE_PASSWORD_LIMIT = "5/hour"
AUTH_RESET_PASSWORD_LIMIT = "10/hour"
AUTH_MAGIC_LINK_VERIFY_LIMIT = "30/hour"
AUTH_LOCAL_LOGIN_LIMIT = "60/hour"
# Every signed-in browser refreshes a few times an hour; sized for an office NAT.
AUTH_REFRESH_LIMIT = "600/hour"

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
        ``limits`` rate string (e.g. ``"60/minute"`` or
        ``"20/minute;300/hour"``). Parsed
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

    Does nothing while the limiter is disabled (``RATELIMIT_ENABLED=false``).

    Raises
    ------
    fastapi.HTTPException
        429 on rate-limit exceeded. The detail is intentionally
        generic so the response cannot serve as an oracle for whether
        the keying value (e.g. a specific ``client_id``) exists.

    Notes
    -----
    Reaches into slowapi-private limiter state (``limiter.limiter`` and
    ``_storage_dead``). We accept that coupling because the
    alternative (a parallel redis-keyed counter) doubles the
    infrastructure surface for one feature; the calls we make
    (``RateLimiter.hit``) are the very stable ``limits`` library API.
    """
    if not limiter.enabled:
        return
    full_key = f"{namespace}:{key}"
    # ``hit`` returns True when the request is permitted (counter
    # incremented) and False when the limit was already exceeded.
    if not all(_hit(item, full_key) for item in parse_many(rate_string)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
        )


def _hit(item: RateLimitItem, key: str) -> bool:
    """Count one hit, moving to the in-memory fallback if Redis is down."""
    try:
        return limiter.limiter.hit(item, key)
    except Exception:
        if limiter._storage_dead:
            raise
        logger.warning("Rate limit storage unreachable, using per-process memory")
        # slowapi probes Redis again on its next request check and switches back.
        limiter._storage_dead = True
        return limiter.limiter.hit(item, key)
