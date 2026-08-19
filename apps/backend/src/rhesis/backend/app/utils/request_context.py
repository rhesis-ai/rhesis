"""Per-request correlation ID.

The ID ties a generic error response back to the log line that holds the real
traceback: the client is told ``error_id``, the logs carry the same value.
"""

import re
import uuid
from contextvars import ContextVar, Token
from typing import Optional

REQUEST_ID_HEADER = b"x-request-id"

_request_id: ContextVar[str] = ContextVar("request_id", default="")

# An inbound ID is attacker-controlled and lands in log lines, so anything that
# could forge a newline or bloat the log is dropped rather than escaped.
_SAFE_INBOUND_ID = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def get_request_id() -> str:
    """Current request's ID, or "" outside a request (scripts, Celery)."""
    return _request_id.get()


def set_request_id(value: str) -> Token:
    return _request_id.set(value)


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)


class RequestIDMiddleware:
    """Assign every request an ID, and echo it as ``X-Request-ID``.

    Deliberately not a ``BaseHTTPMiddleware``: that one runs the downstream app
    in a new anyio task, and this ContextVar has to stay readable both
    downstream (log records) and back up in the exception handlers above it.
    Pure ASGI keeps everything in one task, so both directions see the value.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request_id = _inbound_id(scope) or new_request_id()
        token = set_request_id(request_id)
        # Also on the scope so handlers can read request.state.request_id.
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_header(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((REQUEST_ID_HEADER, request_id.encode("latin-1")))
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            reset_request_id(token)


def request_id_of(request) -> str:
    """The id for ``request``, preferring the scope over the ContextVar.

    Exception handlers run in Starlette's ServerErrorMiddleware, which sits
    *outside* this middleware -- by the time an exception surfaces there the
    ContextVar has already been reset on the way out. The scope is the same
    dict object throughout, so it still carries the id.
    """
    return getattr(request.state, "request_id", "") or get_request_id()


def _inbound_id(scope) -> Optional[str]:
    """Reuse the proxy's ID when it supplies a safe-looking one."""
    for name, value in scope.get("headers", []):
        if name.lower() == REQUEST_ID_HEADER:
            candidate = value.decode("latin-1", errors="replace")
            return candidate if _SAFE_INBOUND_ID.match(candidate) else None
    return None
