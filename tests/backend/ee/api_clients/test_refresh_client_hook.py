"""Single-slot semantics for the refresh-token client minter hook.

The hook MUST refuse to silently replace an existing minter. Two
different implementations would produce ambiguous behaviour at runtime
(which one mints? which one rejects?) -- and the whole point of the
client-bound refresh flow is that exactly one well-defined function
does the AuthClient verification.

These tests cover the contract; the actual EE minter is unit-tested
elsewhere.
"""

from __future__ import annotations

import pytest

from rhesis.backend.app.auth.refresh_client_hook import (
    get_refresh_client_minter,
    register_refresh_client_minter,
    reset_refresh_client_minter,
)


def _make_minter(label: str):
    """Build a uniquely-identifiable minter for the test."""

    def _mint(db, request, old_token, user) -> str:  # type: ignore[no-untyped-def]
        return f"token-from-{label}"

    _mint.__qualname__ = f"_mint_{label}"
    return _mint


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Each test starts with a clean registry and tears down its own state."""
    reset_refresh_client_minter()
    yield
    reset_refresh_client_minter()


def test_get_returns_none_when_unset() -> None:
    """A Community-only deployment has no minter; core uses None as the signal."""
    assert get_refresh_client_minter() is None


def test_register_then_get_returns_same_callable() -> None:
    """Registration is observable via get -- the registry is not write-only."""
    minter = _make_minter("a")
    register_refresh_client_minter(minter)
    assert get_refresh_client_minter() is minter


def test_reregistering_same_callable_is_idempotent() -> None:
    """Bootstrap may run twice in a test session; same callable is a no-op."""
    minter = _make_minter("a")
    register_refresh_client_minter(minter)
    register_refresh_client_minter(minter)  # must not raise
    assert get_refresh_client_minter() is minter


def test_replacing_with_different_callable_raises() -> None:
    """Loud failure on misconfiguration: two implementations would diverge."""
    register_refresh_client_minter(_make_minter("a"))
    with pytest.raises(RuntimeError, match="already registered"):
        register_refresh_client_minter(_make_minter("b"))


def test_reset_clears_registration() -> None:
    """``reset_refresh_client_minter`` is the only way to drop a registration."""
    register_refresh_client_minter(_make_minter("a"))
    reset_refresh_client_minter()
    assert get_refresh_client_minter() is None
