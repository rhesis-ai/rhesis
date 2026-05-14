"""Status-code mapping for ``/auth/token-exchange`` rejections.

We pin the mapping so that:

- ``invalid_client``        -> 401 (RFC 6749 §5.2)
- ``invalid_grant``         -> 400
- ``invalid_target``        -> 400
- ``invalid_scope``         -> 400
- ``unauthorized_client``   -> 403 (specifically: cross-org reuse)
- ``unsupported_grant_type``-> 400
- ``temporarily_unavailable`` -> 503

The test does not exercise the orchestrator (no DB needed); it
validates ``_status_for`` directly so a future refactor that splits
the status into a header field cannot quietly drop a code.
"""

from __future__ import annotations

import pytest

from rhesis.backend.ee.sso.token_exchange.exchange import TokenExchangeError
from rhesis.backend.ee.sso.token_exchange.router import _status_for


@pytest.mark.parametrize(
    "error_code,http_status_override,expected",
    [
        ("invalid_request", 0, 400),
        # invalid_client comes with an explicit 401 override from the
        # orchestrator (RFC 6749 §5.2).
        ("invalid_client", 401, 401),
        ("invalid_grant", 0, 400),
        ("invalid_target", 0, 400),
        ("invalid_scope", 0, 400),
        # unauthorized_client must be 403 (cross-org mint attempt).
        ("unauthorized_client", 403, 403),
        ("unsupported_grant_type", 0, 400),
        ("temporarily_unavailable", 503, 503),
    ],
)
def test_status_for(
    error_code: str, http_status_override: int, expected: int
) -> None:
    err = TokenExchangeError(
        error_code, "test_reason", http_status=http_status_override
    )
    assert _status_for(err) == expected


def test_status_for_unknown_error_falls_back_to_400() -> None:
    """Defensive: a future error code without a mapping defaults to 400."""
    err = TokenExchangeError("brand_new_code", "x", http_status=0)
    assert _status_for(err) == 400
