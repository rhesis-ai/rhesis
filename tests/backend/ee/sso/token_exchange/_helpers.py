"""Request and organization builders shared by the token-exchange tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from rhesis.backend.ee.sso.token_exchange.exchange import TokenExchangeRequest
from rhesis.backend.ee.sso.token_exchange.schemas import (
    GRANT_TYPE_TOKEN_EXCHANGE,
    TOKEN_TYPE_ACCESS_TOKEN,
)


def payload(**overrides) -> TokenExchangeRequest:
    """A request that parses, so a test reaches the step it cares about."""
    base = dict(
        grant_type=GRANT_TYPE_TOKEN_EXCHANGE,
        subject_token="header.body.sig",
        subject_token_type=TOKEN_TYPE_ACCESS_TOKEN,
        audience="rhesis:org:acme",
        requested_token_type=None,
        scope=None,
        client_id="brain-prod",
        client_secret="s3cret",
    )
    base.update(overrides)
    return TokenExchangeRequest(**base)


def live_org_with_sso():
    """Return a MagicMock that satisfies the org-resolution checks."""
    org = MagicMock()
    org.id = "00000000-0000-0000-0000-000000000001"
    org.slug = "acme"
    org.is_active = True
    org.sso_config = {"issuer_url": "https://idp.example.com"}
    return org
