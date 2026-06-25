"""Response-cache hardening for token-issuing endpoints.

RFC 6749 §5.1 requires every response from a token endpoint -- success
*and* error -- to set ``Cache-Control: no-store`` and
``Pragma: no-cache``. We additionally stamp ``X-Content-Type-Options:
nosniff`` so a browser that ever sees one of these responses (it
shouldn't, but in case CORS misconfiguration ever opens that path)
cannot interpret the JSON body as a different content type.

Why a dedicated middleware rather than per-handler header writes
---------------------------------------------------------------
Per-handler writes are easy to forget on a new error path. A
``HTTPException`` raised before any handler-side code runs would skip
them entirely. Stamping the headers in middleware that runs on every
response (regardless of how the response was produced) is the only
way to make the guarantee universal.

Scoping
-------
The middleware applies only to the two paths that issue or rotate
tokens: ``/auth/token-exchange`` and ``/auth/refresh``. Other routes
keep whatever caching behaviour they already had; we deliberately do
not touch them to avoid surprising perf changes elsewhere.
"""

from __future__ import annotations

from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

#: Default set of paths the middleware hardens. Both endpoints are
#: token-issuing and must never be cached, per RFC 6749 §5.1.
DEFAULT_NO_STORE_PATHS: tuple[str, ...] = (
    "/auth/token-exchange",
    "/auth/refresh",
)


class TokenEndpointCacheHeadersMiddleware(BaseHTTPMiddleware):
    """Stamp no-store cache headers on every response from token endpoints.

    Implemented as a ``BaseHTTPMiddleware`` rather than a per-route
    dependency because we want the headers on responses produced by:

    - the handler itself (success and HTTPException paths),
    - FastAPI's RequestValidationError handler (422),
    - the rate-limit handler (429),
    - any other middleware-emitted response,
    - even 404 / 405 from the router.

    A dependency would only run inside a registered handler, which
    misses several of those paths.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        paths: Iterable[str] = DEFAULT_NO_STORE_PATHS,
    ) -> None:
        super().__init__(app)
        # Materialised as a frozenset so the per-request membership
        # check is O(1) and the path list is immutable post-construction.
        self._paths = frozenset(paths)

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path in self._paths:
            # ``no-store`` is the strict directive; ``no-cache`` alone
            # would still allow a cache to keep the response and revalidate.
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            # ``nosniff`` is a belt-and-braces against a browser ever
            # interpreting a token-bearing JSON body as anything else.
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response


__all__ = [
    "DEFAULT_NO_STORE_PATHS",
    "TokenEndpointCacheHeadersMiddleware",
]
