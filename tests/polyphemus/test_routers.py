"""
Integration-style tests for the Polyphemus FastAPI router.

Uses FastAPI's synchronous TestClient (wraps the async ASGI app). All external
dependencies (auth, Vertex AI HTTP calls, GCP credentials) are mocked so no
network calls are made.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from rhesis.polyphemus.main import app
from rhesis.polyphemus.utils.rate_limit import check_rate_limit

_CONFIGURED_MODELS = {
    "polyphemus-default": "projects/p/locations/us-central1/endpoints/default",
    "polyphemus-opus": "projects/p/locations/us-central1/endpoints/opus",
}

_DEFAULT_ENV = {
    "POLYPHEMUS_ENDPOINT_ID": "test-endpoint-id",
    "POLYPHEMUS_PROJECT_ID": "test-project-id",
    "POLYPHEMUS_LOCATION": "us-central1",
}


def _make_user(user_id: str = "user-1", email: str = "user@example.com") -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.email = email
    return user


def _ok_vertex_response(content: str = "Hello from Polyphemus!") -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 8, "completion_tokens": 12},
    }
    return resp


@pytest.fixture
def mock_user() -> MagicMock:
    return _make_user()


@pytest.fixture
def client(mock_user):
    """TestClient with auth and rate limiting bypassed (check_rate_limit overridden)."""

    async def _no_auth():
        return mock_user

    app.dependency_overrides[check_rate_limit] = _no_auth
    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Health / root endpoints
# ---------------------------------------------------------------------------


class TestHealthEndpoints:
    def test_root_returns_service_name(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert "Polyphemus" in body["service"]
        assert body["status"] == "running"

    def test_health_check_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /generate — success paths
# ---------------------------------------------------------------------------


class TestGenerateEndpointSuccess:
    def test_basic_generate(self, client):
        payload = {"messages": [{"role": "user", "content": "Hello!"}]}
        with patch.dict(os.environ, _DEFAULT_ENV):
            with patch.dict(
                "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
            ):
                with patch(
                    "rhesis.polyphemus.services.services._get_vertex_access_token",
                    return_value="fake-token",
                ):
                    with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                        mock_client.post = AsyncMock(return_value=_ok_vertex_response())
                        resp = client.post("/generate", json=payload)

        assert resp.status_code == 200
        body = resp.json()
        assert "choices" in body
        assert body["choices"][0]["message"]["role"] == "assistant"
        assert "Hello from Polyphemus!" in body["choices"][0]["message"]["content"]

    def test_generate_with_all_optional_fields(self, client):
        payload = {
            "messages": [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Summarise AI."},
            ],
            "model": "polyphemus-default",
            "temperature": 0.5,
            "max_tokens": 256,
            "top_p": 0.9,
            "top_k": 40,
        }
        with patch.dict(os.environ, _DEFAULT_ENV):
            with patch.dict(
                "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
            ):
                with patch(
                    "rhesis.polyphemus.services.services._get_vertex_access_token",
                    return_value="t",
                ):
                    with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                        mock_client.post = AsyncMock(return_value=_ok_vertex_response("Summary."))
                        resp = client.post("/generate", json=payload)

        assert resp.status_code == 200

    def test_generate_returns_usage_block(self, client):
        payload = {"messages": [{"role": "user", "content": "Count to 3."}]}
        with patch.dict(os.environ, _DEFAULT_ENV):
            with patch.dict(
                "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
            ):
                with patch(
                    "rhesis.polyphemus.services.services._get_vertex_access_token",
                    return_value="t",
                ):
                    with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                        mock_client.post = AsyncMock(return_value=_ok_vertex_response())
                        resp = client.post("/generate", json=payload)

        body = resp.json()
        assert "usage" in body
        assert body["usage"]["prompt_tokens"] == 8
        assert body["usage"]["completion_tokens"] == 12
        assert body["usage"]["total_tokens"] == 20

    def test_generate_with_json_schema(self, client):
        payload = {
            "messages": [{"role": "user", "content": "Give me data."}],
            "json_schema": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
            },
        }
        with patch.dict(os.environ, _DEFAULT_ENV):
            with patch.dict(
                "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
            ):
                with patch(
                    "rhesis.polyphemus.services.services._get_vertex_access_token",
                    return_value="t",
                ):
                    with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                        mock_client.post = AsyncMock(return_value=_ok_vertex_response())
                        resp = client.post("/generate", json=payload)

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /generate — error paths
# ---------------------------------------------------------------------------


class TestGenerateEndpointErrors:
    def test_missing_endpoint_id_returns_400(self, client):
        payload = {"messages": [{"role": "user", "content": "hi"}]}
        env = {k: v for k, v in _DEFAULT_ENV.items() if k != "POLYPHEMUS_ENDPOINT_ID"}
        with patch.dict(os.environ, env):
            os.environ.pop("POLYPHEMUS_ENDPOINT_ID", None)
            resp = client.post("/generate", json=payload)

        assert resp.status_code == 400
        assert "endpoint" in resp.json()["detail"].lower()

    def test_missing_project_id_returns_400(self, client):
        payload = {"messages": [{"role": "user", "content": "hi"}]}
        env = {k: v for k, v in _DEFAULT_ENV.items() if k != "POLYPHEMUS_PROJECT_ID"}
        with patch.dict(os.environ, env):
            os.environ.pop("POLYPHEMUS_PROJECT_ID", None)
            resp = client.post("/generate", json=payload)

        assert resp.status_code == 400

    def test_value_error_returns_400(self, client):
        payload = {"messages": [{"role": "user", "content": "hi"}]}
        with patch.dict(os.environ, _DEFAULT_ENV):
            with patch(
                "rhesis.polyphemus.routers.services.generate_text_via_vertex_endpoint",
                side_effect=ValueError("Invalid parameter"),
            ):
                resp = client.post("/generate", json=payload)

        assert resp.status_code == 400
        assert "Invalid parameter" in resp.json()["detail"]

    def test_runtime_error_returns_500(self, client):
        payload = {"messages": [{"role": "user", "content": "hi"}]}
        with patch.dict(os.environ, _DEFAULT_ENV):
            with patch(
                "rhesis.polyphemus.routers.services.generate_text_via_vertex_endpoint",
                side_effect=RuntimeError("Vertex unreachable"),
            ):
                resp = client.post("/generate", json=payload)

        assert resp.status_code == 500
        assert "Vertex unreachable" in resp.json()["detail"]

    def test_unexpected_exception_returns_500(self, client):
        payload = {"messages": [{"role": "user", "content": "hi"}]}
        with patch.dict(os.environ, _DEFAULT_ENV):
            with patch(
                "rhesis.polyphemus.routers.services.generate_text_via_vertex_endpoint",
                side_effect=Exception("Unexpected boom"),
            ):
                resp = client.post("/generate", json=payload)

        assert resp.status_code == 500

    def test_invalid_request_body_returns_422(self, client):
        resp = client.post("/generate", json={"temperature": 0.5})
        assert resp.status_code == 422

    def test_empty_messages_list_returns_400(self, client):
        payload = {"messages": []}
        with patch.dict(os.environ, _DEFAULT_ENV):
            with patch.dict(
                "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
            ):
                with patch(
                    "rhesis.polyphemus.services.services._get_vertex_access_token",
                    return_value="t",
                ):
                    resp = client.post("/generate", json=payload)

        assert resp.status_code == 400

    def test_vertex_503_retried_then_fails_with_500(self, client):
        payload = {"messages": [{"role": "user", "content": "hi"}]}
        always_503 = MagicMock()
        always_503.status_code = 503
        always_503.text = "Service Unavailable"

        with patch.dict(os.environ, _DEFAULT_ENV):
            with patch.dict(
                "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
            ):
                with patch(
                    "rhesis.polyphemus.services.services._get_vertex_access_token",
                    return_value="t",
                ):
                    with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                        mock_client.post = AsyncMock(return_value=always_503)
                        with patch(
                            "rhesis.polyphemus.services.services.asyncio.sleep",
                            new_callable=AsyncMock,
                        ):
                            resp = client.post("/generate", json=payload)

        assert resp.status_code == 500
