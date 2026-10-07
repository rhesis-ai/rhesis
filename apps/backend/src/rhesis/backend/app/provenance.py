"""Who made a change, and how the request reached us.

``provenance_of(session)`` answers that for any session: the actor and the
credential they used, the client channel, IP, user agent and request id. The
audit log reads it at flush time.

Request sessions get it from the request itself. ``ProvenanceMiddleware`` puts
the request in a ContextVar, ``get_db()`` attaches it to every session it opens,
and the actor is read when asked rather than when the session opens, because
some routes open their session before authentication has run. Celery jobs bind
a fixed provenance instead (``bind_job_provenance``).

The ``web`` and ``sdk`` channels are what the client says it is
(``X-Rhesis-Client``); they help people read the log but are not evidence. The
``mcp`` and ``architect`` channels can't be claimed from outside: ``architect``
comes from the Architect's signed delegation token, and either is accepted from
the header only on a call that carries this process's in-process secret. Actor
and credential are the authoritative fields.
"""

from __future__ import annotations

import hmac
import secrets
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from starlette.requests import HTTPConnection

from rhesis.backend.app.utils.rate_limit import CLIENT_IP_HEADER, get_real_ip
from rhesis.backend.app.utils.request_context import request_id_of

CLIENT_HEADER = "X-Rhesis-Client"
IN_PROCESS_HEADER = "X-Rhesis-In-Process"

# Proves a call came from inside this process (MCP, the Architect's tools). Never
# leaves the process, so nothing outside it can produce a matching header.
_IN_PROCESS_SECRET = secrets.token_urlsafe(32)

_REQUEST_KEY = "_provenance_request"
_PROVENANCE_KEY = "_provenance"

# request.state keys the authentication code fills in.
_STATE_ACTOR_TYPE = "provenance_actor_type"
_STATE_CREDENTIAL_ID = "provenance_credential_id"
_STATE_CREDENTIAL_HINT = "provenance_credential_hint"
_STATE_CHANNEL = "provenance_channel"

_current_request: ContextVar[Optional[HTTPConnection]] = ContextVar(
    "provenance_request", default=None
)


class ActorType(str, Enum):
    USER = "user"
    API_TOKEN = "api_token"
    API_CLIENT = "api_client"
    SYSTEM = "system"
    ANONYMOUS = "anonymous"

    def __str__(self) -> str:
        return self.value


class Channel(str, Enum):
    WEB = "web"
    SDK = "sdk"
    MCP = "mcp"
    ARCHITECT = "architect"
    API = "api"
    JOB = "job"

    def __str__(self) -> str:
        return self.value


# What any client may claim in X-Rhesis-Client; anything else counts as plain API.
_CLAIMABLE_CHANNELS = frozenset({Channel.WEB, Channel.SDK})
# Claimable only by an in-process call.
_IN_PROCESS_CHANNELS = frozenset({Channel.MCP, Channel.ARCHITECT})


@dataclass(frozen=True)
class RequestProvenance:
    actor_type: ActorType
    actor_id: Optional[str]
    credential_id: Optional[str]
    credential_hint: Optional[str]
    channel: Channel
    ip: Optional[str]
    user_agent: Optional[str]
    request_id: Optional[str]
    job_id: Optional[str] = None


def record_delegation(request: HTTPConnection, target_service: Optional[str]) -> None:
    """Note a service delegation token. One aimed at the backend is the Architect's."""
    if target_service == "backend":
        setattr(request.state, _STATE_CHANNEL, Channel.ARCHITECT)


def record_credential(
    request: HTTPConnection,
    actor_type: ActorType,
    credential_id: Optional[str] = None,
    credential_hint: Optional[str] = None,
) -> None:
    """Note which credential authenticated ``request``. Called by the auth code."""
    setattr(request.state, _STATE_ACTOR_TYPE, actor_type)
    setattr(request.state, _STATE_CREDENTIAL_ID, credential_id)
    setattr(request.state, _STATE_CREDENTIAL_HINT, credential_hint)


def resolve_provenance(request: HTTPConnection) -> RequestProvenance:
    state = request.state
    user = getattr(state, "user", None)
    if user is None:
        actor_type = ActorType.ANONYMOUS
    else:
        actor_type = getattr(state, _STATE_ACTOR_TYPE, None) or ActorType.USER
    return RequestProvenance(
        actor_type=actor_type,
        actor_id=str(user.id) if user is not None else None,
        credential_id=getattr(state, _STATE_CREDENTIAL_ID, None),
        credential_hint=getattr(state, _STATE_CREDENTIAL_HINT, None),
        channel=client_channel(request),
        ip=get_real_ip(request),
        user_agent=request.headers.get("user-agent"),
        request_id=request_id_of(request) or None,
    )


def client_channel(request: HTTPConnection) -> Channel:
    derived = getattr(request.state, _STATE_CHANNEL, None)
    if derived is not None:
        return derived
    try:
        claimed = Channel(request.headers.get(CLIENT_HEADER, "").strip().lower())
    except ValueError:
        return Channel.API
    if claimed in _CLAIMABLE_CHANNELS:
        return claimed
    if claimed in _IN_PROCESS_CHANNELS and _is_in_process(request):
        return claimed
    return Channel.API


def _is_in_process(request: HTTPConnection) -> bool:
    presented = request.headers.get(IN_PROCESS_HEADER, "")
    return hmac.compare_digest(presented.encode(), _IN_PROCESS_SECRET.encode())


def in_process_headers(channel: Channel, request: Optional[HTTPConnection] = None) -> dict:
    """Headers for a backend call made in-process on behalf of ``request``.

    The inner call is a new request from 127.0.0.1, so the original client's IP,
    user agent and request id are passed on with it.
    """
    headers = {CLIENT_HEADER: channel.value, IN_PROCESS_HEADER: _IN_PROCESS_SECRET}
    if request is not None:
        headers[CLIENT_IP_HEADER] = get_real_ip(request)
        user_agent = request.headers.get("user-agent")
        if user_agent:
            headers["User-Agent"] = user_agent
        request_id = request_id_of(request)
        if request_id:
            headers["X-Request-ID"] = request_id
    return headers


def attach_current_request(session) -> None:
    """Remember the request a session belongs to. Called by ``get_db()``."""
    request = _current_request.get()
    if request is not None:
        session.info[_REQUEST_KEY] = request


def bind_job_provenance(
    session,
    *,
    user_id: Optional[str],
    job_id: Optional[str],
    request_id: Optional[str],
) -> None:
    """Attribute a job's writes to the system, on behalf of the user who started it."""
    session.info[_PROVENANCE_KEY] = RequestProvenance(
        actor_type=ActorType.SYSTEM,
        actor_id=user_id,
        credential_id=None,
        credential_hint=None,
        channel=Channel.JOB,
        ip=None,
        user_agent=None,
        request_id=request_id,
        job_id=job_id,
    )


def provenance_of(session) -> Optional[RequestProvenance]:
    """The provenance of the writes on ``session``, or None outside a request or job."""
    bound = session.info.get(_PROVENANCE_KEY)
    if bound is not None:
        return bound
    request = session.info.get(_REQUEST_KEY)
    return resolve_provenance(request) if request is not None else None


class ProvenanceMiddleware:
    """Make the current request reachable from the sessions it opens.

    Pure ASGI, like ``RequestIDMiddleware``: the ContextVar has to reach the
    threadpool that runs sync dependencies, which copies the context it is
    started from. Must sit inside ``RequestIDMiddleware`` so the request id is
    already on the scope.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        scope.setdefault("state", {})
        token = _current_request.set(HTTPConnection(scope))
        try:
            await self.app(scope, receive, send)
        finally:
            _current_request.reset(token)
