"""What a person sees when SSO sign-in fails, and what the backend logs about it.

Every failure goes through ``login_error_redirect``: the real reason and detail go to the
log, the browser gets a short public code that the ``/auth/sso-error`` page turns into a
message, plus the request id so an admin can find the log line.
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlencode

from fastapi.responses import RedirectResponse

from rhesis.backend.app.utils.request_context import get_request_id

logger = logging.getLogger(__name__)

#: Internal reason -> public code. The frontend has one message per public code.
PUBLIC_CODES = {
    # The IdP sent an error back (the person cancelled, or the IdP refused them).
    "idp_error": "idp_denied",
    # The callback can't be matched to a sign-in this browser started.
    "invalid_callback": "expired",
    "invalid_state": "expired",
    "org_mismatch": "expired",
    "missing_verifier": "expired",
    # SSO isn't usable for this organization.
    "sso_unavailable": "sso_unavailable",
    "org_not_found": "sso_unavailable",
    "sso_disabled": "sso_unavailable",
    "idp_unreachable": "idp_unreachable",
    "authentication_failed": "idp_response_invalid",
    "email_missing": "email_missing",
    "invalid_email": "email_missing",
    "email_unverified": "email_unverified",
    "domain_not_allowed": "domain_not_allowed",
    "cross_org_collision": "account_elsewhere",
    "auto_provision_disabled": "not_invited",
    "seat_limit_reached": "no_seats",
    "no_matching_group": "no_access",
    "groups_unavailable": "groups_unavailable",
}
GENERIC_CODE = "login_failed"


def public_code(reason: str) -> str:
    return PUBLIC_CODES.get(reason, GENERIC_CODE)


def login_error_redirect(
    frontend_url: str,
    reason: str,
    *,
    org_id: str = "",
    email: Optional[str] = None,
    detail: object = "",
) -> RedirectResponse:
    """Log why sign-in failed and send the browser to the friendly error page."""
    logger.warning(
        "SSO sign-in failed: reason=%s org=%s email=%s detail=%s",
        reason,
        org_id or "-",
        email or "-",
        detail or "-",
    )
    params = {"error": public_code(reason)}
    ref = get_request_id()
    if ref:
        params["ref"] = ref
    return RedirectResponse(
        url=f"{frontend_url}/auth/sso-error?{urlencode(params)}", status_code=302
    )


__all__ = ["GENERIC_CODE", "PUBLIC_CODES", "login_error_redirect", "public_code"]
