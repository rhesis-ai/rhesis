"""The async chat endpoint awaits run_chat_turn_async (no thread-pool offload)."""

from __future__ import annotations

import asyncio

from visit_prep.state import Phase


class _FakeState:
    phase = Phase.IDLE
    turn = 1


def _import_app_with_rhesis_disabled(monkeypatch):
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

    monkeypatch.setattr(app_mod, "run_chat_turn_async", fake_run_chat_turn_async)

    result = asyncio.run(app_mod.chat_endpoint_traced(message="hello", conversation_id="c1"))

    assert result.response == "hi"
    assert called["message"] == "hello"
    assert called["conversation_id"] == "c1"
