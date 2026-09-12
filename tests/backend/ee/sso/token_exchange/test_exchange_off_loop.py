"""``run_token_exchange`` must keep its database work off the event loop.

The orchestrator is a coroutine (it awaits the subject IdP's JWKS endpoint and
Redis), so any query it runs inline runs on the loop and blocks every other
request in the worker process. Steps 2-5a and steps 8-11 are therefore
dispatched with ``anyio.to_thread.run_sync``.

These tests drive the orchestrator with a recording session and assert that no
query was issued from the loop's own thread. The step order those threads must
not reshuffle is pinned by ``test_feature_gating.py``.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from rhesis.backend.app.features import FeatureRegistry
from rhesis.backend.ee.sso.token_exchange.exchange import (
    TokenExchangeError,
    run_token_exchange,
)
from tests.backend.ee.sso.token_exchange._helpers import live_org_with_sso, payload


def _recording_db(org, threads: list[int]):
    """A session that records the thread every ``query()`` was issued from."""
    db = MagicMock()

    def _query(*args, **kwargs):
        threads.append(threading.get_ident())
        result = MagicMock()
        result.filter.return_value.first.return_value = org
        return result

    db.query.side_effect = _query
    return db


@pytest.mark.unit
@pytest.mark.asyncio
async def test_org_resolution_runs_in_a_worker_thread(monkeypatch):
    monkeypatch.setattr(FeatureRegistry, "is_available", classmethod(lambda cls, name, org: True))
    monkeypatch.setattr(
        "rhesis.backend.ee.sso.token_exchange.exchange.authenticate_client",
        lambda *a, **kw: None,
    )

    loop_thread = threading.get_ident()
    query_threads: list[int] = []
    db = _recording_db(live_org_with_sso(), query_threads)

    with pytest.raises(TokenExchangeError) as exc:
        await run_token_exchange(db, payload(), sso_config_loader=lambda _org: object())

    # Reaching client auth means the org lookup ran.
    assert exc.value.reason_code == "client_auth_failed"
    assert query_threads, "expected the org lookup to have issued a query"
    assert loop_thread not in query_threads


@pytest.mark.unit
@pytest.mark.asyncio
async def test_client_authentication_runs_in_a_worker_thread(monkeypatch):
    monkeypatch.setattr(FeatureRegistry, "is_available", classmethod(lambda cls, name, org: True))

    loop_thread = threading.get_ident()
    auth_threads: list[int] = []

    def _authenticate_client(*args, **kwargs):
        auth_threads.append(threading.get_ident())
        return None

    monkeypatch.setattr(
        "rhesis.backend.ee.sso.token_exchange.exchange.authenticate_client",
        _authenticate_client,
    )

    db = _recording_db(live_org_with_sso(), [])

    with pytest.raises(TokenExchangeError):
        await run_token_exchange(db, payload(), sso_config_loader=lambda _org: object())

    assert len(auth_threads) == 1
    assert loop_thread not in auth_threads
