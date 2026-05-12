"""Pydantic models for the RFC 8693 token-exchange grant.

Two response shapes:

- :class:`TokenExchangeSuccessResponse` -- the RFC 8693 success body.
- :class:`TokenExchangeErrorResponse` -- the RFC 6749 §5.2 error body
  the router returns on every rejection. Bodies are minimal
  (``{"error": "<code>"}``) so they cannot serve as oracles; the
  validator's internal ``reason_code`` is emitted only into the audit
  event, never into the HTTP body.

Why no Pydantic model for the request?
--------------------------------------
The request body is ``application/x-www-form-urlencoded`` (RFC 8693).
We parse the form fields manually in the router and feed them into
:func:`rhesis.backend.ee.sso.token_exchange.exchange.run_token_exchange`
because:

1. RFC 8693 needs explicit single-vs-multi handling for ``audience``
   (multiple ``audience`` form values must be rejected as
   ``invalid_request``); Pydantic's BaseModel coerces silently.
2. The form is the security boundary -- using Pydantic here would
   route us through FastAPI's dependency validation, which raises
   422 before our handler can stamp the cache headers and emit the
   audit event.

Doing the parsing inline in the router keeps the response shape and
audit emission under our explicit control on every error path.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

#: RFC 8693 grant type URN.
GRANT_TYPE_TOKEN_EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"

#: RFC 8693 subject / requested token type URN we accept (v1 only).
TOKEN_TYPE_ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"


class TokenExchangeSuccessResponse(BaseModel):
    """RFC 8693 success body.

    ``token_type`` is the canonical OAuth string ``"Bearer"``;
    ``issued_token_type`` echoes the type URN (always ``access_token``
    in v1).
    """

    access_token: str
    issued_token_type: str = TOKEN_TYPE_ACCESS_TOKEN
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int = Field(
        ...,
        description="Seconds until the access token expires.",
    )
    scope: str = Field(
        ...,
        description="Space-separated resolved scope string.",
    )
    refresh_token: Optional[str] = Field(
        default=None,
        description=(
            "Present only when offline_access is in the resolved scope."
        ),
    )
    refresh_expires_in: Optional[int] = Field(
        default=None,
        description="Seconds until the refresh token expires.",
    )


class TokenExchangeErrorResponse(BaseModel):
    """RFC 6749 §5.2 error body.

    Deliberately minimal: omitting ``error_description`` /
    ``error_uri`` denies an attacker any ability to use the response
    body as an oracle to distinguish failure modes.
    """

    error: str


__all__ = [
    "GRANT_TYPE_TOKEN_EXCHANGE",
    "TOKEN_TYPE_ACCESS_TOKEN",
    "TokenExchangeErrorResponse",
    "TokenExchangeSuccessResponse",
]
