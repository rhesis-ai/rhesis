"""
Unit tests for the Polyphemus service layer.

Covers:
- resolve_model: alias normalisation and validation
- _build_vertex_request_body: JSON body construction
- generate_text_via_vertex_endpoint: full async generation flow including
  parameter clamping, retry logic, error propagation, and response mapping.
"""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from rhesis.polyphemus.schemas import GenerateRequest, Message
from rhesis.polyphemus.services.services import (
    _build_vertex_request_body,
    generate_text_via_vertex_endpoint,
    resolve_model,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONFIGURED_MODELS = {
    "polyphemus-default": "projects/p/locations/us-central1/endpoints/default",
    "polyphemus-opus": "projects/p/locations/us-central1/endpoints/opus",
}


def _ok_http_response(
    content: str = "Test response", prompt_tokens: int = 10, completion_tokens: int = 20
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }
    return resp


def _error_http_response(status: int, text: str = "Error") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# resolve_model
# ---------------------------------------------------------------------------


class TestResolveModel:
    def test_none_returns_default_alias(self):
        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            assert resolve_model(None) == "polyphemus-default"

    def test_explicit_default_alias(self):
        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            assert resolve_model("polyphemus-default") == "polyphemus-default"

    def test_opus_alias(self):
        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            assert resolve_model("polyphemus-opus") == "polyphemus-opus"

    def test_invalid_alias_raises(self):
        with pytest.raises(ValueError, match="Invalid model"):
            resolve_model("gpt-4")

    def test_unknown_alias_raises(self):
        with pytest.raises(ValueError, match="Invalid model"):
            resolve_model("polyphemus-unknown")

    def test_unconfigured_model_raises(self):
        # Model is a valid alias but the env var is not set (None value)
        unconfigured = {"polyphemus-default": None, "polyphemus-opus": None}
        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", unconfigured, clear=True
        ):
            with pytest.raises(ValueError, match="not configured"):
                resolve_model("polyphemus-default")

    def test_only_opus_configured(self):
        partial = {"polyphemus-default": None, "polyphemus-opus": "opus-endpoint"}
        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", partial, clear=True
        ):
            assert resolve_model("polyphemus-opus") == "polyphemus-opus"

    def test_empty_string_alias_raises(self):
        # empty string is falsy → treated as None → default alias → may still raise if unconfigured
        unconfigured = {"polyphemus-default": None, "polyphemus-opus": None}
        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", unconfigured, clear=True
        ):
            with pytest.raises(ValueError):
                resolve_model("")


# ---------------------------------------------------------------------------
# _build_vertex_request_body
# ---------------------------------------------------------------------------


class TestBuildVertexRequestBody:
    def test_minimal_body_structure(self):
        messages = [Message(role="user", content="Hello")]
        body = _build_vertex_request_body(messages)
        assert "messages" in body
        assert body["messages"] == [{"role": "user", "content": "Hello"}]
        assert "temperature" in body
        assert "top_p" in body

    def test_default_temperature_and_top_p(self):
        body = _build_vertex_request_body([Message(content="hi")])
        assert body["temperature"] == 0.6
        assert body["top_p"] == 1.0

    def test_custom_temperature_and_top_p(self):
        body = _build_vertex_request_body([Message(content="hi")], temperature=0.3, top_p=0.85)
        assert body["temperature"] == 0.3
        assert body["top_p"] == 0.85

    def test_max_tokens_included_when_set(self):
        body = _build_vertex_request_body([Message(content="hi")], max_tokens=512)
        assert body["max_tokens"] == 512

    def test_max_tokens_excluded_when_none(self):
        body = _build_vertex_request_body([Message(content="hi")], max_tokens=None)
        assert "max_tokens" not in body

    def test_top_k_included_when_positive(self):
        body = _build_vertex_request_body([Message(content="hi")], top_k=40)
        assert body["top_k"] == 40

    def test_top_k_zero_included(self):
        body = _build_vertex_request_body([Message(content="hi")], top_k=0)
        assert body["top_k"] == 0

    def test_top_k_negative_excluded(self):
        body = _build_vertex_request_body([Message(content="hi")], top_k=-1)
        assert "top_k" not in body

    def test_top_k_none_excluded(self):
        body = _build_vertex_request_body([Message(content="hi")], top_k=None)
        assert "top_k" not in body

    def test_json_schema_response_format(self):
        schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
        body = _build_vertex_request_body([Message(content="hi")], json_schema=schema)
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["response_format"]["json_schema"]["schema"] == schema

    def test_json_schema_none_excluded(self):
        body = _build_vertex_request_body([Message(content="hi")], json_schema=None)
        assert "response_format" not in body

    def test_message_role_none_defaults_to_user(self):
        # Message with role=None should be serialised as "user"
        body = _build_vertex_request_body([Message(role=None, content="hi")])
        assert body["messages"][0]["role"] == "user"

    def test_multiple_messages_preserved(self):
        msgs = [
            Message(role="system", content="Be concise."),
            Message(role="user", content="Question."),
            Message(role="assistant", content="Answer."),
        ]
        body = _build_vertex_request_body(msgs)
        roles = [m["role"] for m in body["messages"]]
        assert roles == ["system", "user", "assistant"]


# ---------------------------------------------------------------------------
# generate_text_via_vertex_endpoint
# ---------------------------------------------------------------------------


class TestGenerateTextViaVertexEndpoint:
    """Tests for the main async generation function."""

    async def test_successful_generation(self):
        req = GenerateRequest(messages=[Message(role="user", content="Hello")])
        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token",
                return_value="fake-token",
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(return_value=_ok_http_response("Hi there!"))
                    result = await generate_text_via_vertex_endpoint(
                        req, endpoint_id="ep-1", project_id="proj-1"
                    )

        assert result["choices"][0]["message"]["content"] == "Hi there!"
        assert result["model"] == "polyphemus-default"
        assert result["usage"]["total_tokens"] == 30

    async def test_usage_tokens_summed(self):
        req = GenerateRequest(messages=[Message(role="user", content="Hi")])
        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(
                        return_value=_ok_http_response(prompt_tokens=15, completion_tokens=25)
                    )
                    result = await generate_text_via_vertex_endpoint(
                        req, endpoint_id="ep", project_id="proj"
                    )

        assert result["usage"]["prompt_tokens"] == 15
        assert result["usage"]["completion_tokens"] == 25
        assert result["usage"]["total_tokens"] == 40

    async def test_empty_messages_raises_value_error(self):
        req = GenerateRequest(messages=[])
        with pytest.raises(ValueError, match="At least one non-system message"):
            await generate_text_via_vertex_endpoint(req, endpoint_id="ep", project_id="proj")

    async def test_only_system_message_raises_value_error(self):
        req = GenerateRequest(messages=[Message(role="system", content="Be helpful.")])
        with pytest.raises(ValueError, match="At least one non-system message"):
            await generate_text_via_vertex_endpoint(req, endpoint_id="ep", project_id="proj")

    async def test_only_whitespace_content_raises_value_error(self):
        req = GenerateRequest(messages=[Message(role="user", content="   ")])
        with pytest.raises(ValueError, match="At least one non-system message"):
            await generate_text_via_vertex_endpoint(req, endpoint_id="ep", project_id="proj")

    async def test_invalid_model_raises_value_error(self):
        req = GenerateRequest(
            messages=[Message(role="user", content="hi")],
            model="gpt-unsupported",
        )
        with pytest.raises(ValueError, match="Invalid model"):
            await generate_text_via_vertex_endpoint(req, endpoint_id="ep", project_id="proj")

    async def test_temperature_zero_clamped_to_default(self, caplog):
        req = GenerateRequest(
            messages=[Message(role="user", content="hi")],
            temperature=0.0,
        )
        captured_body: Dict[str, Any] = {}

        async def capture_post(url, *, json, headers, timeout):
            captured_body.update(json)
            return _ok_http_response()

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = capture_post
                    await generate_text_via_vertex_endpoint(
                        req, endpoint_id="ep", project_id="proj"
                    )

        assert captured_body["temperature"] == 0.6

    async def test_negative_temperature_clamped(self, caplog):
        req = GenerateRequest(
            messages=[Message(role="user", content="hi")],
            temperature=-1.0,
        )
        captured_body: Dict[str, Any] = {}

        async def capture_post(url, *, json, headers, timeout):
            captured_body.update(json)
            return _ok_http_response()

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = capture_post
                    await generate_text_via_vertex_endpoint(
                        req, endpoint_id="ep", project_id="proj"
                    )

        assert captured_body["temperature"] == 0.6

    async def test_top_p_above_one_clamped(self):
        req = GenerateRequest(
            messages=[Message(role="user", content="hi")],
            top_p=1.5,
        )
        captured_body: Dict[str, Any] = {}

        async def capture_post(url, *, json, headers, timeout):
            captured_body.update(json)
            return _ok_http_response()

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = capture_post
                    await generate_text_via_vertex_endpoint(
                        req, endpoint_id="ep", project_id="proj"
                    )

        assert captured_body["top_p"] == 1.0

    async def test_top_p_zero_clamped(self):
        req = GenerateRequest(
            messages=[Message(role="user", content="hi")],
            top_p=0.0,
        )
        captured_body: Dict[str, Any] = {}

        async def capture_post(url, *, json, headers, timeout):
            captured_body.update(json)
            return _ok_http_response()

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = capture_post
                    await generate_text_via_vertex_endpoint(
                        req, endpoint_id="ep", project_id="proj"
                    )

        assert captured_body["top_p"] == 1.0

    async def test_negative_top_k_excluded_from_body(self):
        req = GenerateRequest(
            messages=[Message(role="user", content="hi")],
            top_k=-1,
        )
        captured_body: Dict[str, Any] = {}

        async def capture_post(url, *, json, headers, timeout):
            captured_body.update(json)
            return _ok_http_response()

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = capture_post
                    await generate_text_via_vertex_endpoint(
                        req, endpoint_id="ep", project_id="proj"
                    )

        assert "top_k" not in captured_body

    async def test_retry_on_500_then_success(self):
        req = GenerateRequest(messages=[Message(role="user", content="hi")])
        responses = [_error_http_response(500), _ok_http_response("Retry worked")]

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(side_effect=responses)
                    with patch(
                        "rhesis.polyphemus.services.services.asyncio.sleep", new_callable=AsyncMock
                    ):
                        result = await generate_text_via_vertex_endpoint(
                            req, endpoint_id="ep", project_id="proj"
                        )

        assert result["choices"][0]["message"]["content"] == "Retry worked"

    async def test_retry_on_429_then_success(self):
        req = GenerateRequest(messages=[Message(role="user", content="hi")])
        responses = [_error_http_response(429), _ok_http_response()]

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(side_effect=responses)
                    with patch(
                        "rhesis.polyphemus.services.services.asyncio.sleep", new_callable=AsyncMock
                    ):
                        result = await generate_text_via_vertex_endpoint(
                            req, endpoint_id="ep", project_id="proj"
                        )

        assert result["choices"][0]["message"]["content"] == "Test response"

    async def test_all_retries_exhausted_raises_runtime_error(self):
        req = GenerateRequest(messages=[Message(role="user", content="hi")])
        always_500 = [_error_http_response(500)] * 3

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(side_effect=always_500)
                    with patch(
                        "rhesis.polyphemus.services.services.asyncio.sleep", new_callable=AsyncMock
                    ):
                        with pytest.raises(RuntimeError, match="Vertex AI endpoint failed"):
                            await generate_text_via_vertex_endpoint(
                                req, endpoint_id="ep", project_id="proj"
                            )

    async def test_transport_error_retries_then_raises(self):
        req = GenerateRequest(messages=[Message(role="user", content="hi")])

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(
                        side_effect=httpx.TransportError("Connection refused")
                    )
                    with patch(
                        "rhesis.polyphemus.services.services.asyncio.sleep", new_callable=AsyncMock
                    ):
                        with pytest.raises(RuntimeError, match="unreachable"):
                            await generate_text_via_vertex_endpoint(
                                req, endpoint_id="ep", project_id="proj"
                            )

    async def test_transport_error_then_success(self):
        req = GenerateRequest(messages=[Message(role="user", content="hi")])

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(
                        side_effect=[
                            httpx.TransportError("Timeout"),
                            _ok_http_response("Recovered"),
                        ]
                    )
                    with patch(
                        "rhesis.polyphemus.services.services.asyncio.sleep", new_callable=AsyncMock
                    ):
                        result = await generate_text_via_vertex_endpoint(
                            req, endpoint_id="ep", project_id="proj"
                        )

        assert result["choices"][0]["message"]["content"] == "Recovered"

    async def test_non_200_non_retryable_raises_immediately(self):
        req = GenerateRequest(messages=[Message(role="user", content="hi")])

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    # 400 is not in the retryable set — only one HTTP call should be made
                    mock_client.post = AsyncMock(
                        return_value=_error_http_response(400, "Bad Request")
                    )
                    with pytest.raises(RuntimeError, match="400"):
                        await generate_text_via_vertex_endpoint(
                            req, endpoint_id="ep", project_id="proj"
                        )

                    assert mock_client.post.call_count == 1

    async def test_empty_choices_in_response_raises(self):
        req = GenerateRequest(messages=[Message(role="user", content="hi")])
        empty_choices_resp = MagicMock()
        empty_choices_resp.status_code = 200
        empty_choices_resp.json.return_value = {"choices": [], "usage": {}}

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(return_value=empty_choices_resp)
                    with pytest.raises(RuntimeError, match="no choices"):
                        await generate_text_via_vertex_endpoint(
                            req, endpoint_id="ep", project_id="proj"
                        )

    async def test_json_schema_forwarded_to_vertex(self):
        schema = {"type": "object", "properties": {"result": {"type": "string"}}}
        req = GenerateRequest(
            messages=[Message(role="user", content="Give structured output.")],
            json_schema=schema,
        )
        captured_body: Dict[str, Any] = {}

        async def capture_post(url, *, json, headers, timeout):
            captured_body.update(json)
            return _ok_http_response()

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = capture_post
                    await generate_text_via_vertex_endpoint(
                        req, endpoint_id="ep", project_id="proj"
                    )

        assert "response_format" in captured_body
        assert captured_body["response_format"]["type"] == "json_schema"

    async def test_correct_url_constructed(self):
        req = GenerateRequest(messages=[Message(role="user", content="hi")])
        captured_url: list = []

        async def capture_post(url, *, json, headers, timeout):
            captured_url.append(url)
            return _ok_http_response()

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = capture_post
                    await generate_text_via_vertex_endpoint(
                        req,
                        endpoint_id="ep-999",
                        project_id="my-project",
                        location="europe-west4",
                    )

        assert len(captured_url) == 1
        url = captured_url[0]
        assert "europe-west4-aiplatform.googleapis.com" in url
        assert "my-project" in url
        assert "ep-999" in url
        assert "rawPredict" in url

    async def test_opus_model_in_response(self):
        req = GenerateRequest(
            messages=[Message(role="user", content="hi")],
            model="polyphemus-opus",
        )
        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(return_value=_ok_http_response())
                    result = await generate_text_via_vertex_endpoint(
                        req, endpoint_id="ep", project_id="proj"
                    )

        assert result["model"] == "polyphemus-opus"
