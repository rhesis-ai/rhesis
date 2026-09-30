from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from docs_assistant import app as app_module
from docs_assistant.corpus.cache import DocsUnavailable
from docs_assistant.schemas import Route, TurnResponse


def _response(**overrides) -> TurnResponse:
    base = dict(
        conversation_id="c1",
        turn=1,
        route=Route.ANSWERED,
        response="Answer",
        answer_md="Answer",
        citations=[],
        docs_as_of=datetime(2026, 9, 30, tzinfo=timezone.utc),
        answer_id="a1",
    )
    return TurnResponse(**{**base, **overrides})


@pytest.fixture
def client(monkeypatch, cache):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(app_module.state, "cache", cache)
    with TestClient(app_module.app) as test_client:
        yield test_client
    app_module.state.cache = None


def test_health_reports_docs_and_model(client):
    body = client.get("/health").json()
    assert body["status"] == "healthy"
    assert body["docs"] == "ready"
    assert body["pages"] == 8
    assert body["model_ready"] is True
    assert body["docs_as_of"]


def test_root_lists_endpoints(client):
    assert client.get("/").json()["endpoints"]["chat"] == "POST /chat"


def test_chat_returns_the_turn(client, monkeypatch):
    seen = {}

    async def fake_run_turn(message, *, cache, conversation_id):
        seen.update(message=message, conversation_id=conversation_id)
        return _response()

    monkeypatch.setattr(app_module, "run_turn", fake_run_turn)
    body = client.post("/chat", json={"message": "hi", "conversation_id": "c1"}).json()
    assert seen == {"message": "hi", "conversation_id": "c1"}
    assert body["route"] == "answered"
    assert body["docs_as_of"].startswith("2026-09-30")


def test_empty_message_is_rejected(client):
    assert client.post("/chat", json={"message": ""}).status_code == 422


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (DocsUnavailable("down"), 503, "docs_unavailable"),
        (RuntimeError("No API key for the docs assistant"), 503, "No API key"),
        (RuntimeError("boom"), 500, "Error processing request"),
        (ValueError("boom"), 500, "Error processing request"),
    ],
)
def test_chat_errors(client, monkeypatch, error, status, detail):
    async def failing(*args, **kwargs):
        raise error

    monkeypatch.setattr(app_module, "run_turn", failing)
    response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == status
    assert detail in response.json()["detail"]


def test_docs_down_at_startup_still_serves_health(monkeypatch, cache, site):
    site.down = True
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(app_module.state, "cache", cache)
    with TestClient(app_module.app) as client:
        assert client.get("/health").json()["docs"] == "unavailable"
        assert client.post("/chat", json={"message": "hi"}).status_code == 503
    app_module.state.cache = None
