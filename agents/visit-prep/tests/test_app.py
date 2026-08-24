"""The async chat endpoint awaits run_chat_turn_async (no thread-pool offload)."""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

from visit_prep.state import Phase


class _FakeState:
    phase = Phase.IDLE
    turn = 1


def _import_app_with_rhesis_disabled(monkeypatch):
    """Import the native app module with tracing off, so no client or provider is built."""
    monkeypatch.setenv("RHESIS_API_KEY", "")
    monkeypatch.setenv("RHESIS_PROJECT_ID", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    import visit_prep.app as app_mod

    return app_mod


def test_chat_endpoint_awaits_async_run(monkeypatch):
    app_mod = _import_app_with_rhesis_disabled(monkeypatch)

    called: dict[str, str] = {}

    async def fake_run_chat_turn_async(message, *, conversation_id=None):
        called["message"] = message
        called["conversation_id"] = conversation_id or ""
        return {
            "response": "hi",
            "conversation_id": conversation_id or "c1",
            "state": _FakeState(),
        }

    # The endpoint lives in the factory now, so patch the name the factory resolves.
    import visit_prep.app_factory as factory

    monkeypatch.setattr(factory, "run_chat_turn_async", fake_run_chat_turn_async)

    chat_endpoint_traced = app_mod.app.state.chat_endpoint_traced
    result = asyncio.run(chat_endpoint_traced(message="hello", conversation_id="c1"))

    assert result.response == "hi"
    assert called["message"] == "hello"
    assert called["conversation_id"] == "c1"


def test_lifespan_starts_the_connector(monkeypatch):
    """The lifespan dials the connector, which is what puts this app in the Playground.

    ``@endpoint`` registers at import time, and uvicorn imports the app module from
    ``uvicorn.main.run`` before ``asyncio.run``, so the connection is deferred with only a
    warning. Nothing else picks it up, so dropping this call silently unregisters the agent.
    """
    app_mod = _import_app_with_rhesis_disabled(monkeypatch)

    import visit_prep.app_factory as factory
    import visit_prep.session as session

    monkeypatch.setattr(session, "get_default_pipeline", lambda: None)
    fake_client = Mock()
    monkeypatch.setattr(factory, "get_default_client", lambda: fake_client)

    async def drive_lifespan():
        async with app_mod.app.router.lifespan_context(app_mod.app):
            pass

    asyncio.run(drive_lifespan())

    fake_client.start_connector.assert_called_once()
