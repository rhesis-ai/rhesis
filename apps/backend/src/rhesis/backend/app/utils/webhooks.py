"""Signed outbound webhooks, following Standard Webhooks (https://www.standardwebhooks.com).

Each request carries three headers:

- ``webhook-id``: the message id, the same on every retry, so a receiver can drop duplicates
- ``webhook-timestamp``: Unix seconds of this attempt, so a receiver can refuse replays
- ``webhook-signature``: ``v1,<base64 HMAC-SHA256>`` of ``{id}.{timestamp}.{body}``, keyed by
  the base64 secret after its ``whsec_`` prefix

Destinations are tenant input, so delivery goes through ``SafeHttpClient``: HTTPS only, every
resolved address checked against the SSRF blocklist, redirects never followed, and a timeout.
"""

import base64
import hashlib
import hmac
import secrets
import time
from typing import Optional
from urllib.parse import urlparse

import httpx

from rhesis.backend.app.utils.ssrf_http_client import (
    SafeHttpClient,
    SSRFError,
    validate_url_safety,
)

SECRET_PREFIX = "whsec_"
TIMEOUT_SECONDS = 10.0


def generate_secret() -> str:
    """A new signing secret: ``whsec_`` and 24 random bytes in base64."""
    return SECRET_PREFIX + base64.b64encode(secrets.token_bytes(24)).decode()


def sign(secret: str, message_id: str, timestamp: int, body: bytes) -> str:
    """The ``webhook-signature`` value for one message."""
    key = base64.b64decode(secret.removeprefix(SECRET_PREFIX))
    signed = f"{message_id}.{timestamp}.".encode() + body
    digest = hmac.new(key, signed, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def signed_headers(
    secret: str, message_id: str, body: bytes, timestamp: Optional[int] = None
) -> dict[str, str]:
    timestamp = int(time.time()) if timestamp is None else timestamp
    return {
        "content-type": "application/json",
        "webhook-id": message_id,
        "webhook-timestamp": str(timestamp),
        "webhook-signature": sign(secret, message_id, timestamp, body),
    }


def _require_https(url: str) -> None:
    if urlparse(url).scheme != "https":
        raise SSRFError("Destination URL must use HTTPS")


def check_destination_url(url: str) -> None:
    """Raise ``SSRFError`` unless ``url`` is HTTPS to a public address. For saving a URL."""
    _require_https(url)
    validate_url_safety(url)


def post(url: str, body: bytes, headers: dict[str, str]) -> httpx.Response:
    """POST to a tenant-supplied URL. Raises ``SSRFError`` or an ``httpx`` error."""
    _require_https(url)
    # SafeHttpClient resolves and checks the address again, at send time.
    return SafeHttpClient(timeout=TIMEOUT_SECONDS).post_sync(url, content=body, headers=headers)


def post_signed(url: str, secret: str, message_id: str, body: bytes) -> httpx.Response:
    return post(url, body, signed_headers(secret, message_id, body))
