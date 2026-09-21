"""PKCE (RFC 7636) code verifier and challenge generation.

Lifted unchanged from ``ee/sso/router.py``, where it was a private helper. Any
OAuth authorization-code flow wants it, not just SSO: it binds the code that
comes back to the client that asked for it, so an intercepted code cannot be
redeemed by anyone else.

Only S256 is offered. The ``plain`` method provides no binding worth having,
and some providers reject it outright.
"""

from __future__ import annotations

import hashlib
import secrets
from base64 import urlsafe_b64encode


def generate_pkce() -> tuple[str, str]:
    """Return ``(code_verifier, code_challenge)`` for the S256 method."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge
