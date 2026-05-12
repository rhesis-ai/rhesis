"""SSO endpoint rate limits.

Per-IP, pre-auth rate limits for the SSO routes mounted by
:func:`rhesis.backend.ee.bootstrap`. Lives under ``ee/`` rather than core
because every consumer is an EE route handler in
:mod:`rhesis.backend.ee.sso.router`.

Rationale for the chosen values:

- ``SSO_LOGIN_RATE_LIMIT`` / ``SSO_CALLBACK_RATE_LIMIT``: 10/min is high
  enough that a single user retrying after a redirect glitch is never
  throttled, low enough to discourage automated probing.
- ``SSO_TEST_CONNECTION_RATE_LIMIT``: 5/min applies only to the admin
  ``POST /organizations/{id}/sso/test`` endpoint, which performs an
  outbound HTTP request to the customer's IdP and should not be a free
  amplification vector.
- ``SSO_ADMIN_RATE_LIMIT``: 20/min covers GET / PUT / DELETE on the
  admin SSO config endpoints; comfortably above human admin usage.
"""

from __future__ import annotations

SSO_LOGIN_RATE_LIMIT = "10/minute"
SSO_CALLBACK_RATE_LIMIT = "10/minute"
SSO_TEST_CONNECTION_RATE_LIMIT = "5/minute"
SSO_ADMIN_RATE_LIMIT = "20/minute"

__all__ = [
    "SSO_ADMIN_RATE_LIMIT",
    "SSO_CALLBACK_RATE_LIMIT",
    "SSO_LOGIN_RATE_LIMIT",
    "SSO_TEST_CONNECTION_RATE_LIMIT",
]
