"""
Stress tests for the Polyphemus service.

These tests verify correctness and stability under load:
- Large input payloads (many tokens / many messages)
- High-concurrency async request fanout
- Boundary conditions on generation parameters
- Mixed concurrent workloads

All HTTP and auth calls are mocked — no real network traffic is generated.

Marked slow/performance so CI can exclude them by default (e.g. pytest -m "not slow").
"""

import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.polyphemus.schemas import GenerateRequest, Message
from rhesis.polyphemus.services.services import (
    _build_vertex_request_body,
    generate_text_via_vertex_endpoint,
)

pytestmark = [pytest.mark.slow, pytest.mark.performance]

_CONFIGURED_MODELS = {
    "polyphemus-default": "projects/p/locations/us-central1/endpoints/default",
    "polyphemus-opus": "projects/p/locations/us-central1/endpoints/opus",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok_http_response(content: str = "ok") -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    return resp


def _make_request(content: str = "Hello", model: str | None = None) -> GenerateRequest:
    return GenerateRequest(
        messages=[Message(role="user", content=content)],
        model=model,
    )


# ---------------------------------------------------------------------------
# Large token / payload sizes
# ---------------------------------------------------------------------------


class TestLargeInputTokenSizes:
    """Verify that the service handles large message payloads correctly."""

    def test_schema_accepts_short_message(self):
        req = _make_request("Hi")
        assert req.messages[0].content == "Hi"

    def test_schema_accepts_medium_message(self):
        content = "word " * 500  # ~2 500 chars / ~500 tokens
        req = _make_request(content)
        assert len(req.messages[0].content) == len(content)

    def test_schema_accepts_large_message(self):
        content = "token " * 4_000  # ~24 000 chars / ~4 000 tokens
        req = _make_request(content)
        assert len(req.messages[0].content) == len(content)

    def test_schema_accepts_very_large_message(self):
        content = "x " * 32_000  # ~64 000 chars — beyond typical context windows
        req = _make_request(content)
        assert len(req.messages) == 1

    def test_build_body_large_content_preserved(self):
        content = "word " * 10_000
        msgs = [Message(role="user", content=content)]
        body = _build_vertex_request_body(msgs)
        assert body["messages"][0]["content"] == content

    def test_many_messages_in_one_request(self):
        """A conversation with 200 turns should parse and build without issue."""
        messages = [
            Message(role="user" if i % 2 == 0 else "assistant", content=f"Turn {i}")
            for i in range(200)
        ]
        req = GenerateRequest(messages=messages)
        body = _build_vertex_request_body(req.messages)
        assert len(body["messages"]) == 200

    def test_build_body_with_system_and_many_user_turns(self):
        messages = [Message(role="system", content="You are helpful.")] + [
            Message(role="user", content="Question " * 100) for _ in range(50)
        ]
        body = _build_vertex_request_body(messages)
        assert body["messages"][0]["role"] == "system"
        assert len(body["messages"]) == 51

    async def test_generate_with_large_input(self):
        content = "Please analyse the following text: " + "data " * 3_000
        req = _make_request(content)

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(
                        return_value=_ok_http_response("Analysis complete.")
                    )
                    result = await generate_text_via_vertex_endpoint(
                        req, endpoint_id="ep", project_id="proj"
                    )

        assert result["choices"][0]["message"]["content"] == "Analysis complete."

    async def test_generate_with_many_messages(self):
        messages = [
            Message(role="user" if i % 2 == 0 else "assistant", content=f"message {i}")
            for i in range(100)
        ]
        req = GenerateRequest(messages=messages)

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

        assert "choices" in result


# ---------------------------------------------------------------------------
# Concurrent request tests
# ---------------------------------------------------------------------------


class TestConcurrentRequests:
    """Verify the async service is safe under concurrent load."""

    async def _run_n_concurrent(self, n: int, content: str = "hi") -> List[dict]:
        """Fire n concurrent generation requests and return all results."""
        req = _make_request(content)

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(
                        return_value=_ok_http_response(f"Response to: {content}")
                    )
                    tasks = [
                        generate_text_via_vertex_endpoint(req, endpoint_id="ep", project_id="proj")
                        for _ in range(n)
                    ]
                    results = await asyncio.gather(*tasks)

        return list(results)

    async def test_10_concurrent_requests_all_succeed(self):
        results = await self._run_n_concurrent(10)
        assert len(results) == 10
        assert all("choices" in r for r in results)

    async def test_50_concurrent_requests_all_succeed(self):
        results = await self._run_n_concurrent(50)
        assert len(results) == 50
        assert all(r["choices"][0]["message"]["role"] == "assistant" for r in results)

    async def test_100_concurrent_requests_all_succeed(self):
        results = await self._run_n_concurrent(100)
        assert len(results) == 100

    async def test_mixed_models_concurrent(self):
        """Alternate between default and opus in concurrent calls."""
        requests = [
            GenerateRequest(
                messages=[Message(role="user", content=f"Question {i}")],
                model="polyphemus-default" if i % 2 == 0 else "polyphemus-opus",
            )
            for i in range(40)
        ]
        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(return_value=_ok_http_response())
                    tasks = [
                        generate_text_via_vertex_endpoint(r, endpoint_id="ep", project_id="proj")
                        for r in requests
                    ]
                    results = await asyncio.gather(*tasks)

        assert len(results) == 40
        models = [r["model"] for r in results]
        assert "polyphemus-default" in models
        assert "polyphemus-opus" in models

    async def test_concurrent_requests_with_varying_sizes(self):
        """Concurrent requests with short, medium, and large payloads."""
        sizes = [10, 100, 1_000, 5_000, 10_000]  # characters
        requests = [
            GenerateRequest(messages=[Message(role="user", content="x " * size)]) for size in sizes
        ]
        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(return_value=_ok_http_response())
                    tasks = [
                        generate_text_via_vertex_endpoint(r, endpoint_id="ep", project_id="proj")
                        for r in requests
                    ]
                    results = await asyncio.gather(*tasks)

        assert len(results) == len(sizes)

    async def test_concurrent_partial_failures(self):
        """Some requests fail (transport error) while others succeed — gather should propagate."""
        import httpx

        ok_resp = _ok_http_response()
        fail_exc = httpx.TransportError("Simulated network error")

        # Alternate: even indices succeed, odd indices fail
        side_effects = [ok_resp if i % 2 == 0 else fail_exc for i in range(10)]

        requests = [_make_request(f"msg {i}") for i in range(10)]
        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(side_effect=side_effects)
                    with patch(
                        "rhesis.polyphemus.services.services.asyncio.sleep",
                        new_callable=AsyncMock,
                    ):
                        results = await asyncio.gather(
                            *[
                                generate_text_via_vertex_endpoint(
                                    r, endpoint_id="ep", project_id="proj"
                                )
                                for r in requests
                            ],
                            return_exceptions=True,
                        )

        successes = [r for r in results if isinstance(r, dict)]
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(successes) > 0
        assert len(failures) > 0


# ---------------------------------------------------------------------------
# Parameter boundary / edge-case stress
# ---------------------------------------------------------------------------


class TestParameterBoundaryStress:
    """Stress the parameter validation and clamping across many edge values."""

    @pytest.mark.parametrize(
        "temperature",
        [-10.0, -1.0, -0.001, 0.0],
    )
    async def test_invalid_temperatures_all_clamped(self, temperature):
        req = GenerateRequest(
            messages=[Message(role="user", content="hi")],
            temperature=temperature,
        )
        captured: dict = {}

        async def capture(url, *, json, headers, timeout):
            captured.update(json)
            return _ok_http_response()

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = capture
                    await generate_text_via_vertex_endpoint(
                        req, endpoint_id="ep", project_id="proj"
                    )

        assert captured["temperature"] == 0.7, f"Expected clamped temp for input {temperature}"

    @pytest.mark.parametrize(
        "top_p",
        [-1.0, 0.0, 1.001, 2.0, 100.0],
    )
    async def test_invalid_top_p_all_clamped(self, top_p):
        req = GenerateRequest(
            messages=[Message(role="user", content="hi")],
            top_p=top_p,
        )
        captured: dict = {}

        async def capture(url, *, json, headers, timeout):
            captured.update(json)
            return _ok_http_response()

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = capture
                    await generate_text_via_vertex_endpoint(
                        req, endpoint_id="ep", project_id="proj"
                    )

        assert captured["top_p"] == 1.0, f"Expected clamped top_p for input {top_p}"

    @pytest.mark.parametrize("max_tokens", [1, 128, 512, 1024, 4096, 8192, 32768])
    async def test_various_max_tokens_forwarded(self, max_tokens):
        req = GenerateRequest(
            messages=[Message(role="user", content="hi")],
            max_tokens=max_tokens,
        )
        captured: dict = {}

        async def capture(url, *, json, headers, timeout):
            captured.update(json)
            return _ok_http_response()

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = capture
                    await generate_text_via_vertex_endpoint(
                        req, endpoint_id="ep", project_id="proj"
                    )

        assert captured["max_tokens"] == max_tokens

    async def test_generate_throughput_wall_clock(self):
        """
        Run 200 concurrent mocked requests and assert asyncio.sleep is never
        called in the happy path (deterministic; avoids flaky wall-clock).
        """
        req = _make_request("quick benchmark")
        sleep_mock = AsyncMock()

        with patch.dict(
            "rhesis.polyphemus.services.services.POLYPHEMUS_MODELS", _CONFIGURED_MODELS
        ):
            with patch(
                "rhesis.polyphemus.services.services._get_vertex_access_token", return_value="t"
            ):
                with patch("rhesis.polyphemus.services.services._http_client") as mock_client:
                    mock_client.post = AsyncMock(return_value=_ok_http_response())
                    with patch(
                        "rhesis.polyphemus.services.services.asyncio.sleep", sleep_mock
                    ):
                        tasks = [
                            generate_text_via_vertex_endpoint(
                                req, endpoint_id="ep", project_id="proj"
                            )
                            for _ in range(200)
                        ]
                        await asyncio.gather(*tasks)

        assert sleep_mock.call_count == 0, "Happy path must not call asyncio.sleep"
