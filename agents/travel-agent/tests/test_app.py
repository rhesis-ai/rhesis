"""The HTTP surface."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.mocks import call, client_for, text
from travel_agent import app as app_module
from travel_agent.endpoint_mapping import REQUEST_MAPPING, RESPONSE_MAPPING
from travel_agent.session import StateStore
from travel_agent.terminals import GREETING


@pytest.fixture
def client(monkeypatch):
    """A live app with the model scripted and a store that does not leak between tests."""
    store = StateStore()

    async def _run_chat_turn(message, *, conversation_id=None, **_kwargs):
        from travel_agent.session import run_chat_turn as real

        return await real(
            message,
            conversation_id=conversation_id,
            store=store,
            client=client_for(call("greet_and_introduce"), text("done")),
        )

    monkeypatch.setattr(app_module, "run_chat_turn", _run_chat_turn)
    monkeypatch.setattr(app_module, "_startup_validated", True)
    monkeypatch.setattr(app_module, "default_store", store)
    with TestClient(app_module.app) as test_client:
        yield test_client


def test_root_lists_every_agent(client):
    payload = client.get("/").json()
    assert len(payload["agents"]) == 8
    assert any("Trip Coordinator" in agent for agent in payload["agents"])


def test_health_reports_startup(client):
    assert client.get("/health").json()["status"] == "healthy"


def test_chat_returns_the_reply_and_the_new_fields(client):
    payload = client.post("/chat", json={"message": "Hi", "conversation_id": "c1"}).json()

    assert payload["response"] == GREETING
    assert payload["conversation_id"] == "c1"
    assert payload["phase"] == "greeting"
    assert payload["degraded_services"] == []
    assert payload["brief"]["legs"] == []
    assert "plan_text" not in payload["brief"], (
        "the plan is in `response`, not repeated in the brief"
    )


def test_chat_is_unavailable_before_startup(monkeypatch, client):
    monkeypatch.setattr(app_module, "_startup_validated", False)
    assert client.post("/chat", json={"message": "Hi"}).status_code == 503


def test_conversations_can_be_listed_fetched_and_deleted(client):
    client.post("/chat", json={"message": "Hi", "conversation_id": "c1"})

    listed = client.get("/conversations").json()
    assert {"conversation_id": "c1", "message_count": 2} in listed

    detail = client.get("/conversations/c1").json()
    assert detail["message_count"] == 2
    assert [m["role"] for m in detail["history"]] == ["user", "assistant"]
    assert "brief" in detail

    assert client.delete("/conversations/c1").status_code == 200
    assert client.get("/conversations/c1").status_code == 404


def test_unknown_conversation_is_a_404(client):
    assert client.get("/conversations/nope").status_code == 404
    assert client.delete("/conversations/nope").status_code == 404


def test_endpoint_mapping_is_shared_by_both_entry_points():
    """The FastAPI route and the playground connector had drifted; they now share one source."""
    import travel_agent.app as app_source

    assert app_source.REQUEST_MAPPING is REQUEST_MAPPING
    assert app_source.RESPONSE_MAPPING is RESPONSE_MAPPING
    assert "{{ response }}" == RESPONSE_MAPPING["output"]
    for key in ("phase", "handoffs", "degraded_services"):
        assert key in RESPONSE_MAPPING["metadata"]
