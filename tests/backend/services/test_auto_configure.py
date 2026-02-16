"""
Tests for AutoConfigureService.

Tests the simplified LLM-first pipeline:
  analyse (single LLM call) → probe → correct (LLM call on failure)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.schemas.endpoint import (
    AutoConfigureRequest,
    AutoConfigureResult,
)

# ==================== Fixtures ====================


@pytest.fixture
def mock_llm():
    return MagicMock()


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = "test-user-id"
    user.organization_id = "test-org-id"
    return user


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def service(mock_db, mock_user, mock_llm):
    """Create AutoConfigureService with a mocked LLM."""
    with patch(
        "rhesis.backend.app.services.endpoint.auto_configure.get_user_generation_model",
        return_value=mock_llm,
    ):
        from rhesis.backend.app.services.endpoint.auto_configure import (
            AutoConfigureService,
        )

        svc = AutoConfigureService(mock_db, mock_user)
        svc.llm = mock_llm
        return svc


@pytest.fixture
def sample_result():
    """A typical successful AutoConfigureResult from the LLM."""
    return AutoConfigureResult(
        status="success",
        request_mapping={
            "messages": "{{ messages }}",
            "model": "gpt-4",
        },
        response_mapping={"output": "$.choices[0].message.content"},
        request_headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {{ auth_token }}",
        },
        url="https://api.openai.com/v1/chat/completions",
        method="POST",
        conversation_mode="stateless",
        probe_request={
            "messages": [{"role": "user", "content": "Hello, this is a test."}],
            "model": "gpt-4",
        },
        confidence=0.9,
        reasoning="Detected OpenAI Chat Completions API",
        warnings=[],
    )


# ==================== Analyse Tests ====================


class TestAnalyse:
    """Tests for the single-LLM-call analysis."""

    def test_analyse_returns_auto_configure_result(self, service, mock_llm, sample_result):
        mock_llm.generate.return_value = sample_result
        request = AutoConfigureRequest(input_text="openai.chat.completions.create(...)")

        result = service._analyse(request)

        assert isinstance(result, AutoConfigureResult)
        assert result.request_mapping is not None
        assert result.probe_request is not None
        mock_llm.generate.assert_called_once()

    def test_analyse_passes_url_to_template(self, service, mock_llm, sample_result):
        mock_llm.generate.return_value = sample_result
        request = AutoConfigureRequest(
            input_text="some code",
            url="https://custom.api.com/chat",
        )

        service._analyse(request)

        prompt = mock_llm.generate.call_args[0][0]
        assert "https://custom.api.com/chat" in prompt

    def test_analyse_llm_dict_response(self, service, mock_llm):
        """LLM returning a raw dict should be coerced to the model."""
        mock_llm.generate.return_value = {
            "status": "success",
            "request_mapping": {"query": "{{ input }}"},
            "response_mapping": {"output": "$.result"},
            "url": "https://api.example.com",
            "method": "POST",
            "confidence": 0.7,
            "reasoning": "Simple API",
        }
        request = AutoConfigureRequest(input_text="some code")

        result = service._analyse(request)

        assert isinstance(result, AutoConfigureResult)
        assert result.url == "https://api.example.com"

    def test_analyse_llm_error_raises(self, service, mock_llm):
        mock_llm.generate.return_value = {"error": "Could not parse"}
        request = AutoConfigureRequest(input_text="garbled")

        with pytest.raises(RuntimeError, match="Could not parse"):
            service._analyse(request)

    def test_analyse_llm_exception_propagates(self, service, mock_llm):
        mock_llm.generate.side_effect = Exception("LLM unavailable")
        request = AutoConfigureRequest(input_text="some code")

        with pytest.raises(Exception, match="LLM unavailable"):
            service._analyse(request)


# ==================== Probe Tests ====================


class TestProbe:
    """Tests for endpoint probing with self-correction."""

    @pytest.mark.asyncio
    async def test_probe_success(self, service, sample_result):
        with patch.object(
            service,
            "_probe_endpoint",
            new_callable=AsyncMock,
        ) as mock_probe:
            from rhesis.backend.app.services.endpoint.auto_configure import (
                ProbeOutcome,
            )

            mock_probe.return_value = ProbeOutcome(
                success=True,
                body={"choices": [{"message": {"content": "Hi"}}]},
                status_code=200,
                error=None,
            )
            request = AutoConfigureRequest(
                input_text="code",
                url="https://api.example.com",
                auth_token="token",
            )

            result = await service._probe_with_retries(sample_result, request)

            assert result.probe_success is True
            assert result.probe_attempts == 1
            assert result.probe_error is None
            assert result.probe_response is not None

    @pytest.mark.asyncio
    async def test_probe_failure_then_correction(self, service, mock_llm, sample_result):
        """Failed probe triggers LLM correction; second probe succeeds."""
        from rhesis.backend.app.services.endpoint.auto_configure import (
            ProbeOutcome,
        )

        probe_mock = AsyncMock(
            side_effect=[
                ProbeOutcome(False, {"error": "missing field"}, 422, "HTTP 422"),
                ProbeOutcome(
                    True,
                    {"choices": [{"message": {"content": "Hi"}}]},
                    200,
                    None,
                ),
            ]
        )

        corrected = sample_result.model_copy()
        corrected.probe_request = {"query": "test", "model": "gpt-4"}
        mock_llm.generate.return_value = corrected

        with patch.object(service, "_probe_endpoint", probe_mock):
            request = AutoConfigureRequest(
                input_text="code",
                url="https://api.example.com",
                auth_token="token",
            )

            result = await service._probe_with_retries(sample_result, request)

            assert result.probe_success is True
            assert result.probe_attempts == 2

    @pytest.mark.asyncio
    async def test_probe_all_retries_exhausted(self, service, mock_llm, sample_result):
        from rhesis.backend.app.services.endpoint.auto_configure import (
            ProbeOutcome,
        )

        probe_mock = AsyncMock(
            return_value=ProbeOutcome(False, {"error": "always fails"}, 422, "HTTP 422")
        )
        mock_llm.generate.return_value = sample_result

        with patch.object(service, "_probe_endpoint", probe_mock):
            request = AutoConfigureRequest(
                input_text="code",
                url="https://api.example.com",
                auth_token="token",
            )

            result = await service._probe_with_retries(sample_result, request)

            assert result.probe_success is False
            assert result.probe_attempts == 3
            assert result.probe_error is not None
            assert result.status == "partial"

    @pytest.mark.asyncio
    async def test_probe_connection_error_no_retry(self, service, sample_result):
        """Network errors should not trigger self-correction."""
        from rhesis.backend.app.services.endpoint.auto_configure import (
            ProbeOutcome,
        )

        probe_mock = AsyncMock(
            return_value=ProbeOutcome(False, None, None, "Connection error: refused")
        )

        with patch.object(service, "_probe_endpoint", probe_mock):
            request = AutoConfigureRequest(
                input_text="code",
                url="https://api.example.com",
            )

            result = await service._probe_with_retries(sample_result, request)

            assert result.probe_success is False
            assert result.probe_attempts == 1
            assert "Connection error" in result.probe_error

    @pytest.mark.asyncio
    async def test_probe_auth_failure_no_retry(self, service, sample_result):
        """Auth failures should stop retries immediately."""
        from rhesis.backend.app.services.endpoint.auto_configure import (
            ProbeOutcome,
        )

        probe_mock = AsyncMock(
            return_value=ProbeOutcome(False, {"error": "unauthorized"}, 401, "HTTP 401")
        )

        with patch.object(service, "_probe_endpoint", probe_mock):
            request = AutoConfigureRequest(
                input_text="code",
                url="https://api.example.com",
                auth_token="bad-token",
            )

            result = await service._probe_with_retries(sample_result, request)

            assert result.probe_success is False
            assert result.probe_attempts == 1
            assert result.probe_status_code == 401


# ==================== End-to-End Pipeline Tests ====================


class TestEndToEnd:
    """Full pipeline tests."""

    @pytest.mark.asyncio
    async def test_pipeline_success_with_probe(self, service, mock_llm, sample_result):
        mock_llm.generate.return_value = sample_result

        from rhesis.backend.app.services.endpoint.auto_configure import (
            ProbeOutcome,
        )

        with patch.object(
            service,
            "_probe_endpoint",
            new_callable=AsyncMock,
            return_value=ProbeOutcome(
                True,
                {"choices": [{"message": {"content": "Hi"}}]},
                200,
                None,
            ),
        ):
            request = AutoConfigureRequest(
                input_text="curl -X POST https://api.openai.com/v1/chat/completions",
                url="https://api.openai.com/v1/chat/completions",
                auth_token="sk-test",
            )

            result = await service.auto_configure(request)

            assert result.status == "success"
            assert result.probe_success is True
            assert result.probe_attempts == 1

    @pytest.mark.asyncio
    async def test_pipeline_without_probe(self, service, mock_llm, sample_result):
        mock_llm.generate.return_value = sample_result

        request = AutoConfigureRequest(
            input_text="some code",
            url="https://api.example.com",
            probe=False,
        )

        result = await service.auto_configure(request)

        assert result.status == "success"
        assert result.probe_attempts == 0

    @pytest.mark.asyncio
    async def test_pipeline_analyse_failure(self, service, mock_llm):
        mock_llm.generate.side_effect = RuntimeError("Could not parse")

        request = AutoConfigureRequest(
            input_text="asdfghjkl",
            url="https://api.example.com",
        )

        result = await service.auto_configure(request)

        assert result.status == "failed"
        assert "parse" in result.error.lower()

    @pytest.mark.asyncio
    async def test_pipeline_partial_on_probe_failure(self, service, mock_llm, sample_result):
        from rhesis.backend.app.services.endpoint.auto_configure import (
            ProbeOutcome,
        )

        mock_llm.generate.side_effect = [
            sample_result,  # _analyse
            sample_result,  # _correct attempt 1
            sample_result,  # _correct attempt 2
        ]

        with patch.object(
            service,
            "_probe_endpoint",
            new_callable=AsyncMock,
            return_value=ProbeOutcome(False, {"error": "bad"}, 422, "HTTP 422"),
        ):
            request = AutoConfigureRequest(
                input_text="some code",
                url="https://api.example.com",
                auth_token="token",
            )

            result = await service.auto_configure(request)

            assert result.status == "partial"
            assert result.probe_success is False
            assert result.confidence <= 0.5
            assert len(result.warnings) > 0

    @pytest.mark.asyncio
    async def test_pipeline_prefilled_url_overrides(self, service, mock_llm, sample_result):
        """Pre-filled URL/method should override LLM's values."""
        mock_llm.generate.return_value = sample_result

        request = AutoConfigureRequest(
            input_text="some code",
            url="https://custom.url.com/api",
            method="PUT",
            probe=False,
        )

        result = await service.auto_configure(request)

        assert result.url == "https://custom.url.com/api"
        assert result.method == "PUT"
