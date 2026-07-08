"""The async chat endpoint must not run the blocking pipeline on the event loop."""

from __future__ import annotations

import asyncio
import threading

from dr_rhesis.state import Phase


class _FakeState:
    phase = Phase.IDLE
    turn = 1


def _import_app_with_rhesis_disabled(monkeypatch):
    # Set falsy Rhesis creds before import so load_dotenv (override=False) keeps
    # them and app.py falls back to DisabledClient -- no telemetry/network.
    monkeypatch.setenv("RHESIS_API_KEY", "")
    monkeypatch.setenv("RHESIS_PROJECT_ID", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    import dr_rhesis.app as app_mod

    return app_mod


def test_chat_endpoint_offloads_blocking_call_to_thread(monkeypatch):
    app_mod = _import_app_with_rhesis_disabled(monkeypatch)

    loop_thread = threading.get_ident()
    recorded: dict[str, int] = {}

    def fake_run_chat_turn(message, *, conversation_id=None):
        recorded["thread"] = threading.get_ident()
        return {
            "response": "hi",
            "conversation_id": conversation_id or "c1",
            "state": _FakeState(),
        }

    monkeypatch.setattr(app_mod, "run_chat_turn", fake_run_chat_turn)

    result = asyncio.run(app_mod.chat_endpoint_traced(message="hello", conversation_id="c1"))

    assert result.response == "hi"
    # The blocking work must have run on a worker thread, not the event loop.
    assert recorded["thread"] != loop_thread
