"""Unit tests for :mod:`rhesis.backend.ee.api_clients.refresh_minter`.

The module-private ``_strip_offline_access`` helper is the
security-relevant unit here: ``offline_access`` is an OIDC
convention for "give me a refresh token", not an authority. The
access token's ``scope`` claim must NOT carry it (or a future
per-route scope check might mistakenly grant it as an authority),
but the persisted refresh row MUST keep it so re-rotation preserves
the original intent.
"""

from __future__ import annotations

import pytest

from rhesis.backend.ee.api_clients.refresh_minter import (
    _strip_offline_access,
)


@pytest.mark.parametrize(
    "given,expected",
    [
        ("full offline_access", "full"),
        ("read offline_access", "read"),
        ("offline_access full", "full"),
        ("read full offline_access", "read full"),
        ("full", "full"),
        ("offline_access", None),  # only offline_access -> nothing left
    ],
)
def test_strips_offline_access_token(given: str, expected: str | None) -> None:
    assert _strip_offline_access(given) == expected


def test_none_input_passes_through() -> None:
    """UI/SSO refresh rows have NULL scope; the helper must not coerce that."""
    assert _strip_offline_access(None) is None


def test_empty_string_passes_through() -> None:
    assert _strip_offline_access("") == ""


def test_does_not_strip_substrings() -> None:
    """``offline_access_v2`` is a different scope; substring match would be wrong."""
    assert _strip_offline_access("full offline_access_v2") == (
        "full offline_access_v2"
    )
