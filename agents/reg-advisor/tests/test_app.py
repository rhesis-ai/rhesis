"""FastAPI surface."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from fastapi.testclient import TestClient

from reg_advisor import app as app_module
from reg_advisor.knowledge import DEFAULT_KNOWLEDGE_DIR, KnowledgeBaseError, load_knowledge_base
from reg_advisor.session import StateStore
from reg_advisor.state import Phase, RegAdvisorState


@pytest.fixture
def client() -> TestClient:
    """A client whose lifespan has run, so the knowledge base is validated."""
    with TestClient(app_module.app) as active:
        yield active


@pytest.fixture
def fake_turn(monkeypatch: pytest.MonkeyPatch):
    """Replace the turn layer, so the routes are tested without a model."""

    def install(response: str = "the reply", **state_kwargs):
        async def fake(message: str, *, conversation_id: str | None = None, **_: object) -> dict:
            return {
                "response": response,
                "conversation_id": conversation_id or "generated-id",
                "state": RegAdvisorState(**state_kwargs),
                "raw": {},
            }

        monkeypatch.setattr(app_module, "run_chat_turn_async", fake)

    return install


# --- read-only routes ------------------------------------------------------------------------


def test_root_describes_the_service_and_the_knowledge_base(client: TestClient) -> None:
    body = client.get("/").json()
    assert body["name"] == "Reg-Advisor"
    assert "Not legal advice" in body["description"]
    assert body["knowledge_base_verified_on"] == "2026-08-11"
    assert "POST /chat" in body["endpoints"].values()


def test_health_reports_startup_validated(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body == {"status": "healthy", "startup_validated": True}


def test_health_before_startup_reports_not_validated() -> None:
    """Without the lifespan the flag is false, which is what /chat gates on."""
    assert app_module.app.router.lifespan_context is not None
    body = TestClient(app_module.app).get("/health").json()
    assert body["startup_validated"] is False


# --- chat -------------------------------------------------------------------------------------


def test_chat_returns_the_turn_result(client: TestClient, fake_turn) -> None:
    fake_turn("Which markets?", phase=Phase.SCOPING, turn=1)
    body = client.post("/chat", json={"message": "I'm building an app"}).json()

    assert body == {
        "response": "Which markets?",
        "conversation_id": "generated-id",
        "phase": "scoping",
        "turn": 1,
    }


def test_chat_threads_the_conversation_id(client: TestClient, fake_turn) -> None:
    fake_turn()
    body = client.post("/chat", json={"message": "hi", "conversation_id": "abc"}).json()
    assert body["conversation_id"] == "abc"


def test_chat_is_503_until_startup_has_run(fake_turn) -> None:
    fake_turn()
    response = TestClient(app_module.app).post("/chat", json={"message": "hi"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Service starting up"


def test_a_missing_api_key_becomes_a_503_with_the_real_message(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_key(*_args: object, **_kwargs: object) -> dict:
        raise RuntimeError("No Gemini API key found. Set GOOGLE_API_KEY ...")

    monkeypatch.setattr(app_module, "run_chat_turn_async", no_key)
    response = client.post("/chat", json={"message": "hi"})

    assert response.status_code == 503
    assert "No Gemini API key" in response.json()["detail"]


def test_any_other_failure_becomes_a_generic_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(*_args: object, **_kwargs: object) -> dict:
        raise ValueError("internal detail that must not leak")

    monkeypatch.setattr(app_module, "run_chat_turn_async", boom)
    response = client.post("/chat", json={"message": "hi"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Error processing request"
    assert "internal detail" not in response.text


def test_a_missing_message_is_rejected(client: TestClient) -> None:
    assert client.post("/chat", json={}).status_code == 422


# --- conversations -----------------------------------------------------------------------------


def test_list_and_delete_conversations(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    store = StateStore()
    store.set("abc", RegAdvisorState(turn=3))
    monkeypatch.setattr(app_module, "default_store", store)

    listed = client.get("/conversations").json()
    assert listed == {"count": 1, "conversations": {"abc": 3}}

    assert client.delete("/conversations/abc").json() == {"deleted": "abc"}
    assert client.get("/conversations").json()["count"] == 0


def test_deleting_an_unknown_conversation_is_a_404(client: TestClient) -> None:
    assert client.delete("/conversations/never-existed").status_code == 404


# --- startup validation --------------------------------------------------------------------------


def test_a_broken_knowledge_base_stops_the_server_starting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dangling citation found mid-conversation is worse than a failed boot."""
    broken = tmp_path / "knowledge"
    shutil.copytree(DEFAULT_KNOWLEDGE_DIR, broken)

    taxonomy = broken / "taxonomy.yaml"
    data = yaml.safe_load(taxonomy.read_text(encoding="utf-8"))
    data["nodes"][0]["related_nodes"].append("EU-MD-GHOST-404")
    taxonomy.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    monkeypatch.setattr(
        app_module, "validate_knowledge_base", lambda: _validate(load_knowledge_base(broken))
    )
    with pytest.raises(KnowledgeBaseError, match="EU-MD-GHOST-404"), TestClient(app_module.app):
        pass


def _validate(base):
    from reg_advisor.knowledge import validate_knowledge_base

    return validate_knowledge_base(base)


# --- packaging ------------------------------------------------------------------------------------


def _in_fresh_interpreter(code: str) -> str:
    """Run code in a subprocess, because import side effects cannot be undone in-process."""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    finished = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True
    )
    return finished.stdout.strip()


def test_importing_the_package_does_not_build_the_app() -> None:
    """`app` is lazily loaded, so importing the library runs no route or startup code.

    FastAPI itself still loads — google-adk depends on it — but our app module does not.
    """
    loaded = _in_fresh_interpreter(
        "import sys, reg_advisor; print('reg_advisor.app' in sys.modules)"
    )
    assert loaded == "False"


def test_the_lazily_loaded_app_is_the_fastapi_instance() -> None:
    resolved = _in_fresh_interpreter("import reg_advisor; print(type(reg_advisor.app).__name__)")
    assert resolved == "FastAPI"


def test_an_unknown_attribute_still_raises() -> None:
    import reg_advisor

    assert "app" in reg_advisor.__all__
    with pytest.raises(AttributeError):
        _ = reg_advisor.no_such_thing


def test_lifespan_starts_the_connector(monkeypatch):
    """The lifespan dials the connector, which is what puts this app in the Playground.

    ``@endpoint`` registers at import time, and uvicorn imports the app module from
    ``uvicorn.main.run`` before ``asyncio.run``, so the connection is deferred with only a
    warning. Nothing else picks it up, so dropping this call silently unregisters the agent.
    """
    fake_client = Mock()
    monkeypatch.setattr(app_module, "rhesis_client", fake_client)

    with TestClient(app_module.app):
        pass

    fake_client.start_connector.assert_called_once()
