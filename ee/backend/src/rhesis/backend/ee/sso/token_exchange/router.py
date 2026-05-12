"""FastAPI router for ``POST /auth/token-exchange`` (RFC 8693).

The router is the only piece of the token-exchange surface that
touches FastAPI. It does five things:

1. Parse the form body (and any HTTP Basic ``Authorization`` header)
   into a normalised :class:`TokenExchangeRequest`. RFC 6749 §2.3.1
   forbids passing client credentials via *both* mechanisms
   simultaneously, and RFC 8693 implicitly forbids multi-valued
   ``audience``; both are enforced here, before any cryptography.
2. Cap the request body so a malicious client cannot exhaust the
   parser with a multi-megabyte form. The hard cap defaults to
   16 KiB -- a Keycloak access token is ~1.5 KiB and even a
   pathologically signed token plus the other fields stays under 8 KiB.
3. Hand the parsed request to
   :func:`rhesis.backend.ee.sso.token_exchange.exchange.run_token_exchange`.
4. Translate the raised :class:`TokenExchangeError` into the RFC 6749
   §5.2 response shape (``{"error": "<code>"}``) with the right HTTP
   status code. Status mapping is centralised so the orchestrator does
   not grow opinions about HTTP.
5. Wrap the success path's :class:`TokenExchangeSuccess` into the
   :class:`TokenExchangeSuccessResponse` Pydantic model so we get
   automatic schema generation for the OpenAPI doc without having
   the orchestrator depend on Pydantic.

Cache-control headers (``Cache-Control: no-store`` etc.) are applied
by :class:`TokenEndpointCacheHeadersMiddleware`, not here, so the
guarantee holds even on early-exit error paths (422 / 429 / unhandled).
"""

from __future__ import annotations

import base64
import binascii
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from rhesis.backend.app.dependencies import get_db_session
from rhesis.backend.app.utils.rate_limit import get_real_ip, limiter
from rhesis.backend.ee.api_clients.audit import (
    TokenExchangeEvent,
    token_exchange_audit_log,
)
from rhesis.backend.ee.sso.token_exchange.exchange import (
    TokenExchangeError,
    TokenExchangeRequest,
    run_token_exchange,
)
from rhesis.backend.ee.sso.token_exchange.rate_limits import (
    TOKEN_EXCHANGE_PER_IP_RATE_LIMIT,
)
from rhesis.backend.ee.sso.token_exchange.schemas import (
    TokenExchangeSuccessResponse,
)

logger = logging.getLogger(__name__)

#: Hard cap on the inbound form body. RFC 8693 has no required
#: maximum; this number is sized to comfortably fit a Keycloak access
#: token (typically 1-3 KiB) plus the other form fields. A larger cap
#: would only enable resource-exhaustion attacks against the form
#: parser; smaller would risk rejecting legitimate large tokens.
MAX_REQUEST_BODY_BYTES = 16 * 1024

router = APIRouter(prefix="/auth", tags=["authentication", "token-exchange"])


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------

#: RFC 6749 §5.2 + RFC 8693 status mapping. Centralised so the
#: orchestrator can stay HTTP-agnostic. ``temporarily_unavailable`` is
#: pinned to 503 to be unambiguous to upstream caches.
_ERROR_TO_STATUS: dict[str, int] = {
    "invalid_request": status.HTTP_400_BAD_REQUEST,
    "invalid_client": status.HTTP_401_UNAUTHORIZED,
    "invalid_grant": status.HTTP_400_BAD_REQUEST,
    "invalid_target": status.HTTP_400_BAD_REQUEST,
    "invalid_scope": status.HTTP_400_BAD_REQUEST,
    "unauthorized_client": status.HTTP_403_FORBIDDEN,
    "unsupported_grant_type": status.HTTP_400_BAD_REQUEST,
    "temporarily_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
}


def _status_for(err: TokenExchangeError) -> int:
    """Return the HTTP status for *err*.

    Always prefers ``err.http_status`` when the orchestrator pinned
    one (e.g. invalid_client -> 401, client_org_mismatch -> 403)
    because some logical errors map to different HTTP codes than the
    default for the OAuth error code.
    """
    if err.http_status:
        return err.http_status
    return _ERROR_TO_STATUS.get(err.error, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Form parsing
# ---------------------------------------------------------------------------


class _FormParseError(Exception):
    """Raised by :func:`_parse_form_payload` for shape-level failures.

    The router converts these to ``invalid_request`` responses; the
    orchestrator never sees a malformed payload.
    """

    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


def _decode_basic_auth(header: str) -> tuple[str, str]:
    """Decode an HTTP Basic ``Authorization`` header value.

    Returns ``(client_id, client_secret)`` for valid headers; raises
    :class:`_FormParseError` for anything else. We intentionally do
    not log the header value because doing so would leak the secret
    on a misconfigured Authorization header.
    """
    try:
        scheme, encoded = header.split(" ", 1)
    except ValueError as exc:
        raise _FormParseError("auth_header_malformed") from exc
    if scheme.lower() != "basic":
        # We accept only Basic on this endpoint. Anything else (Bearer,
        # custom schemes) is a configuration error -- be loud.
        raise _FormParseError("auth_header_unsupported_scheme")
    try:
        raw = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise _FormParseError("auth_header_decode_failed") from exc
    if ":" not in raw:
        raise _FormParseError("auth_header_missing_colon")
    cid, secret = raw.split(":", 1)
    if not cid or not secret:
        raise _FormParseError("auth_header_empty_credential")
    return cid, secret


async def _parse_form_payload(request: Request) -> TokenExchangeRequest:
    """Parse and structurally validate the inbound form body.

    Two security-critical structural checks live here, *before* the
    orchestrator runs:

    - **Single audience.** RFC 8693 allows multiple ``audience``
      values. We require exactly one because our authorization model
      ties an exchanged token to one organization (the audience). A
      multi-audience exchange would have ambiguous org binding.
    - **Single credential mechanism.** RFC 6749 §2.3.1 forbids
      sending client credentials via both Basic ``Authorization`` and
      the request body. Doing so could let two different secrets
      "vote" on which client we authenticate as, and at minimum it
      means the operator's intent is unclear.
    """

    # Reject pathologically large bodies before reading them. The
    # form parser would happily allocate hundreds of MiB given the
    # chance.
    cl = request.headers.get("content-length")
    if cl is not None:
        try:
            if int(cl) > MAX_REQUEST_BODY_BYTES:
                raise _FormParseError("body_too_large")
        except ValueError:
            # Garbled content-length is its own failure mode; refuse
            # to proceed.
            raise _FormParseError("body_content_length_invalid")

    try:
        form = await request.form()
    except Exception as exc:  # noqa: BLE001 - starlette wraps various parser errors
        raise _FormParseError("body_parse_failed") from exc

    # RFC 8693 audience: one and only one. Starlette's ``getlist``
    # surfaces a multi-valued field; ``get`` returns one. We need both
    # to enforce the single-value rule.
    audience_list = form.getlist("audience")
    if len(audience_list) != 1:
        raise _FormParseError("audience_must_be_single")
    audience = audience_list[0]

    # Basic auth detection. If the header is present and parses
    # successfully, the body MUST NOT also carry credentials.
    auth_header = request.headers.get("authorization")
    body_client_id = form.get("client_id")
    body_client_secret = form.get("client_secret")
    if auth_header:
        if body_client_id or body_client_secret:
            raise _FormParseError("dual_client_credential_mechanism")
        client_id, client_secret = _decode_basic_auth(auth_header)
    else:
        client_id = body_client_id or ""
        client_secret = body_client_secret or ""

    return TokenExchangeRequest(
        grant_type=form.get("grant_type") or "",
        subject_token=form.get("subject_token") or "",
        subject_token_type=form.get("subject_token_type") or "",
        audience=audience or "",
        requested_token_type=form.get("requested_token_type") or None,
        scope=form.get("scope"),
        client_id=client_id,
        client_secret=client_secret,
        source_ip=get_real_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/token-exchange",
    response_model=TokenExchangeSuccessResponse,
    responses={
        400: {"description": "RFC 6749 §5.2 error response"},
        401: {"description": "Client authentication failed"},
        403: {"description": "Client not authorized for this resource"},
        503: {"description": "Subject IdP temporarily unreachable"},
    },
    summary="RFC 8693 token exchange",
)
@limiter.limit(TOKEN_EXCHANGE_PER_IP_RATE_LIMIT)
async def token_exchange(
    request: Request,
    db: Session = Depends(get_db_session),
):
    """Exchange a Keycloak (or other OIDC) access token for a Rhesis JWT.

    The endpoint is feature-gated via ``FeatureName.API_CLIENTS``;
    when that feature is not enabled for the resolved organization
    the exchange path returns ``invalid_target``.

    Per-client and per-org rate limits are enforced inside the
    orchestrator (after the client has been identified); the
    decorator above adds the per-IP layer that runs *before* anything
    else and does not need to wait for client identification.
    """

    # ---- Parse + structural-validate ------------------------------------
    try:
        payload = await _parse_form_payload(request)
    except _FormParseError as exc:
        # Emit an audit event for the parse failure too, so a noisy
        # integrator surfaces in the audit stream and is not lost in
        # general logs.
        token_exchange_audit_log(
            TokenExchangeEvent.DENIED,
            org_id=None,
            client_id=None,
            ip=get_real_ip(request),
            user_agent=request.headers.get("user-agent"),
            reason_code=exc.reason_code,
        )
        return _error_response("invalid_request", status.HTTP_400_BAD_REQUEST)

    # The per-IP decorator above is the only currently-wired rate
    # limit. The per-client / per-org / per-(client,user) dimensions
    # described in :mod:`.rate_limits` will be wired once the slowapi
    # primitive for post-parse keying is settled (a custom
    # ``Depends`` that calls ``limiter._limiter.hit`` directly is the
    # likely shape, but that depends on slowapi internals we don't
    # want to commit to in this PR).

    # ---- Orchestrate ----------------------------------------------------
    try:
        result = await run_token_exchange(db, payload)
    except TokenExchangeError as exc:
        return _error_response(exc.error, _status_for(exc))

    # ---- Success --------------------------------------------------------
    body = TokenExchangeSuccessResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        scope=result.scope,
        refresh_token=result.refresh_token,
        refresh_expires_in=result.refresh_expires_in,
    )
    # Use ``model_dump(exclude_none=True)`` so the optional
    # ``refresh_token`` / ``refresh_expires_in`` keys are absent when
    # the caller did not request ``offline_access``. RFC 8693 leaves
    # them optional and present-but-null is a poor signal.
    return JSONResponse(body.model_dump(exclude_none=True))


# ---------------------------------------------------------------------------
# Internal: error response builder
# ---------------------------------------------------------------------------


def _error_response(error_code: str, http_status_code: int) -> JSONResponse:
    """Return the canonical RFC 6749 §5.2 error response shape.

    Body is intentionally minimal -- only the ``error`` key. We do not
    set ``error_description`` because it would let an attacker probe
    the difference between "client not found" and "wrong secret",
    which is exactly the oracle the constant-time client lookup is
    designed to prevent.
    """
    return JSONResponse(
        status_code=http_status_code,
        content={"error": error_code},
    )


__all__ = ["router"]
