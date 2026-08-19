import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Response

from rhesis.backend.app.error_handlers import public_message
from rhesis.backend.app.routers.services import (
    generate_content_endpoint,
    generate_embedding_endpoint,
)
from rhesis.backend.app.schemas.services import GenerateContentRequest, GenerateEmbeddingRequest
from rhesis.backend.app.utils.model_errors import ModelConfigurationError


class ProviderError(Exception):
    """Stand-in for a litellm/openai provider error.

    Those carry the status the provider answered with on ``status_code``, which
    is what separates "the provider said no" from a bug of ours.
    """

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


class TestGenerateContentEndpoint:
    """Test cases for the generate_content_endpoint function."""

    @pytest.mark.asyncio
    async def test_generate_content_endpoint_success(self):
        """Test successful content generation with valid request."""
        # Arrange
        mock_request = GenerateContentRequest(
            prompt="Generate a test function",
            schema={"type": "object", "properties": {"code": {"type": "string"}}},
        )

        expected_response = {"code": "def test_function():\n    return True"}
        mock_db = MagicMock()
        mock_user = MagicMock()
        http_response = Response()

        with patch(
            "rhesis.backend.app.utils.user_model_utils.get_generation_model_with_override"
        ) as mock_get_gen:
            mock_model = MagicMock()
            mock_model.a_generate = AsyncMock(return_value=expected_response)
            mock_get_gen.return_value = mock_model

            result = await generate_content_endpoint(
                mock_request, http_response, db=mock_db, current_user=mock_user
            )

            assert result == expected_response
            mock_model.a_generate.assert_called_once_with(
                "Generate a test function",
                schema={"type": "object", "properties": {"code": {"type": "string"}}},
            )
            mock_get_gen.assert_called_once_with(mock_db, mock_user)

    @pytest.mark.asyncio
    async def test_provider_error_keeps_the_providers_reason(self):
        """A provider that answered with a status told the caller the one thing
        they can act on -- "invalid api key" -- so it stays a 400 that says so."""
        mock_request = GenerateContentRequest(
            prompt="Generate a test function",
            schema={"type": "object"},
        )
        mock_db = MagicMock()
        mock_user = MagicMock()
        http_response = Response()

        with patch(
            "rhesis.backend.app.utils.user_model_utils.get_generation_model_with_override"
        ) as mock_get_gen:
            mock_get_gen.side_effect = ProviderError("invalid api key", status_code=401)

            with pytest.raises(HTTPException) as exc_info:
                await generate_content_endpoint(
                    mock_request, http_response, db=mock_db, current_user=mock_user
                )

            assert exc_info.value.status_code == 400
            assert str(exc_info.value.detail) == "Failed to generate content: invalid api key"

    @pytest.mark.asyncio
    async def test_internal_failure_is_masked(self):
        """A failure with no provider status is ours: masked 500, logged with a
        traceback. This is the exemption's edge -- it must not widen to cover
        our own bugs."""
        mock_request = GenerateContentRequest(
            prompt="Generate a test function",
            schema={"type": "object"},
        )
        mock_db = MagicMock()
        mock_user = MagicMock()
        http_response = Response()

        with patch(
            "rhesis.backend.app.utils.user_model_utils.get_generation_model_with_override"
        ) as mock_get_gen:
            mock_get_gen.side_effect = Exception("Model initialization failed")

            with pytest.raises(HTTPException) as exc_info:
                await generate_content_endpoint(
                    mock_request, http_response, db=mock_db, current_user=mock_user
                )

            assert exc_info.value.status_code == 500
            assert str(exc_info.value.detail) == public_message(500)
            assert "Model initialization failed" not in str(exc_info.value.detail)
            # Logged by internal_error, so the global handler won't repeat it.
            assert getattr(exc_info.value, "rhesis_logged", False) is True


class TestGenerateEmbeddingEndpoint:
    """Test cases for generate_embedding_endpoint's error status codes.

    A bad request from the caller (invalid text, provider rejects the
    content) and a deployment misconfiguration (DEFAULT_EMBEDDING_MODEL
    pointing back at this same endpoint) are different failure classes and
    must not both surface as a generic HTTP 400 — no client-side retry or
    input change fixes the second one.
    """

    def test_plain_provider_error_returns_400_with_the_reason(self):
        """A provider-side failure is still a 400 — the request itself is bad —
        and the provider's reason is what makes it actionable."""
        mock_request = GenerateEmbeddingRequest(text="some text")
        mock_db = MagicMock()
        mock_user = MagicMock()

        with patch(
            "rhesis.backend.app.utils.user_model_utils.get_user_embedding_model"
        ) as mock_get_embedding_model:
            mock_get_embedding_model.side_effect = ProviderError(
                "context length exceeded", status_code=400
            )

            with pytest.raises(HTTPException) as exc_info:
                generate_embedding_endpoint(mock_request, db=mock_db, current_user=mock_user)

            assert exc_info.value.status_code == 400
            assert (
                str(exc_info.value.detail)
                == "Failed to generate embedding: context length exceeded"
            )

    def test_model_configuration_error_keeps_its_message(self):
        """A message naming the caller's own model setting is theirs to read."""
        mock_request = GenerateEmbeddingRequest(text="some text")
        mock_db = MagicMock()
        mock_user = MagicMock()

        with patch(
            "rhesis.backend.app.utils.user_model_utils.get_user_embedding_model"
        ) as mock_get_embedding_model:
            mock_get_embedding_model.side_effect = ModelConfigurationError(
                "Your configured embedding model 'e5' requires an API key that is missing."
            )

            with pytest.raises(HTTPException) as exc_info:
                generate_embedding_endpoint(mock_request, db=mock_db, current_user=mock_user)

            assert exc_info.value.status_code == 400
            assert "requires an API key" in str(exc_info.value.detail)

    def test_internal_failure_is_masked(self):
        """No provider status means the failure is ours: masked 500, not a 400
        blaming the caller. Keeps the 400 exemption from widening."""
        mock_request = GenerateEmbeddingRequest(text="some text")
        mock_db = MagicMock()
        mock_user = MagicMock()

        with patch(
            "rhesis.backend.app.utils.user_model_utils.get_user_embedding_model"
        ) as mock_get_embedding_model:
            mock_get_embedding_model.side_effect = TypeError("embedder object is not callable")

            with pytest.raises(HTTPException) as exc_info:
                generate_embedding_endpoint(mock_request, db=mock_db, current_user=mock_user)

            assert exc_info.value.status_code == 500
            assert str(exc_info.value.detail) == public_message(500)
            assert "not callable" not in str(exc_info.value.detail)
            assert getattr(exc_info.value, "rhesis_logged", False) is True

    def test_recursive_native_provider_returns_500_not_400(self):
        """DEFAULT_EMBEDDING_MODEL resolving back to RhesisEmbedder is a server
        misconfiguration, not a bad request — must return 500."""
        from rhesis.sdk.models.providers.native import RhesisEmbedder

        mock_request = GenerateEmbeddingRequest(text="some text")
        mock_db = MagicMock()
        mock_user = MagicMock()

        # isinstance() against a Mock(spec=...) succeeds, so this stands in for
        # a real RhesisEmbedder without needing RHESIS_API_KEY configured.
        fake_native_embedder = MagicMock(spec=RhesisEmbedder)

        with patch(
            "rhesis.backend.app.utils.user_model_utils.get_user_embedding_model",
            return_value=fake_native_embedder,
        ):
            with pytest.raises(HTTPException) as exc_info:
                generate_embedding_endpoint(mock_request, db=mock_db, current_user=mock_user)

            assert exc_info.value.status_code == 500
            # The caller learns what is wrong; DEFAULT_EMBEDDING_MODEL and the
            # recursion are for the log.
            assert (
                str(exc_info.value.detail)
                == "No embedding model is configured for this deployment."
            )
            assert "recursively" not in str(exc_info.value.detail)

        fake_native_embedder.generate.assert_not_called()


class TestGenerateContentEndpointUsageForwarding:
    """`X-Rhesis-Usage` header forwarding -- see generate_content_endpoint's
    docstring. The resolved model's on_usage (if any) must still fire
    normally (covers a direct/curl caller authenticated as current_user),
    *and* the same usage must be captured and forwarded via the response
    header (covers a relaying RhesisLLM instance accruing on its own side).
    """

    @pytest.mark.asyncio
    async def test_forwards_captured_usage_via_header_and_still_calls_original_on_usage(self):
        mock_request = GenerateContentRequest(prompt="hello")
        mock_db = MagicMock()
        mock_user = MagicMock()
        http_response = Response()

        original_on_usage_calls = []

        with patch(
            "rhesis.backend.app.utils.user_model_utils.get_generation_model_with_override"
        ) as mock_get_gen:
            mock_model = MagicMock()
            mock_model.on_usage = lambda usage: original_on_usage_calls.append(usage)

            async def fake_a_generate(*args, **kwargs):
                mock_model.on_usage({"total_tokens": 42})
                return "hi there"

            mock_model.a_generate = fake_a_generate
            mock_get_gen.return_value = mock_model

            result = await generate_content_endpoint(
                mock_request, http_response, db=mock_db, current_user=mock_user
            )

            assert result == "hi there"
            # The platform's own accrual (current_user's org) still fires --
            # covers a direct/curl caller with no relay to forward to.
            assert original_on_usage_calls == [{"total_tokens": 42}]
            # And the same usage is also forwarded for a relaying caller.
            assert json.loads(http_response.headers["X-Rhesis-Usage"]) == {"total_tokens": 42}

    @pytest.mark.asyncio
    async def test_no_usage_emitted_means_no_header(self):
        mock_request = GenerateContentRequest(prompt="hello")
        mock_db = MagicMock()
        mock_user = MagicMock()
        http_response = Response()

        with patch(
            "rhesis.backend.app.utils.user_model_utils.get_generation_model_with_override"
        ) as mock_get_gen:
            mock_model = MagicMock()
            mock_model.on_usage = None
            mock_model.a_generate = AsyncMock(return_value="hi there")
            mock_get_gen.return_value = mock_model

            await generate_content_endpoint(
                mock_request, http_response, db=mock_db, current_user=mock_user
            )

            assert "X-Rhesis-Usage" not in http_response.headers

    @pytest.mark.asyncio
    async def test_string_model_from_get_model_has_no_on_usage_and_is_not_wrapped(self):
        """A bare-string model resolution (get_model() fallback path) is
        constructed without on_usage wiring -- hasattr guards against
        AttributeError, and no header is ever set for that case."""
        mock_request = GenerateContentRequest(prompt="hello")
        mock_db = MagicMock()
        mock_user = MagicMock()
        http_response = Response()

        with (
            patch(
                "rhesis.backend.app.utils.user_model_utils.get_generation_model_with_override"
            ) as mock_get_gen,
            patch("rhesis.sdk.models.factory.get_model") as mock_sdk_get_model,
        ):
            mock_get_gen.return_value = "openai/gpt-4o"

            mock_model = MagicMock(spec=["a_generate"])
            mock_model.a_generate = AsyncMock(return_value="hi there")
            mock_sdk_get_model.return_value = mock_model

            result = await generate_content_endpoint(
                mock_request, http_response, db=mock_db, current_user=mock_user
            )

            assert result == "hi there"
            assert "X-Rhesis-Usage" not in http_response.headers

    @pytest.mark.asyncio
    async def test_sums_usage_across_multiple_emissions_in_one_call(self):
        """`captured_usage` must accumulate, not `dict.update()`: a model
        that emits on_usage more than once in a single a_generate() call
        (e.g. a future streaming provider) must not have its earlier
        emission overwritten by a later, smaller one."""
        mock_request = GenerateContentRequest(prompt="hello")
        mock_db = MagicMock()
        mock_user = MagicMock()
        http_response = Response()

        with patch(
            "rhesis.backend.app.utils.user_model_utils.get_generation_model_with_override"
        ) as mock_get_gen:
            mock_model = MagicMock()
            mock_model.on_usage = None

            async def fake_a_generate(*args, **kwargs):
                mock_model.on_usage({"total_tokens": 10})
                mock_model.on_usage({"total_tokens": 5})
                return "hi there"

            mock_model.a_generate = fake_a_generate
            mock_get_gen.return_value = mock_model

            await generate_content_endpoint(
                mock_request, http_response, db=mock_db, current_user=mock_user
            )

            assert json.loads(http_response.headers["X-Rhesis-Usage"]) == {"total_tokens": 15}

    @pytest.mark.asyncio
    async def test_restores_original_on_usage_after_the_call(self):
        """The override must not leak past this request: a model that
        outlives the request (e.g. a future caching layer) must be left
        with its original callback, not a closure over this request's
        now-stale captured_usage dict."""
        mock_request = GenerateContentRequest(prompt="hello")
        mock_db = MagicMock()
        mock_user = MagicMock()
        http_response = Response()

        def original_callback(usage):
            pass

        with patch(
            "rhesis.backend.app.utils.user_model_utils.get_generation_model_with_override"
        ) as mock_get_gen:
            mock_model = MagicMock()
            mock_model.on_usage = original_callback
            mock_model.a_generate = AsyncMock(return_value="hi there")
            mock_get_gen.return_value = mock_model

            await generate_content_endpoint(
                mock_request, http_response, db=mock_db, current_user=mock_user
            )

            assert mock_model.on_usage is original_callback

    @pytest.mark.asyncio
    async def test_restores_original_on_usage_even_if_a_generate_raises(self):
        mock_request = GenerateContentRequest(prompt="hello")
        mock_db = MagicMock()
        mock_user = MagicMock()
        http_response = Response()

        def original_callback(usage):
            pass

        with patch(
            "rhesis.backend.app.utils.user_model_utils.get_generation_model_with_override"
        ) as mock_get_gen:
            mock_model = MagicMock()
            mock_model.on_usage = original_callback
            mock_model.a_generate = AsyncMock(side_effect=RuntimeError("boom"))
            mock_get_gen.return_value = mock_model

            with pytest.raises(HTTPException):
                await generate_content_endpoint(
                    mock_request, http_response, db=mock_db, current_user=mock_user
                )

            assert mock_model.on_usage is original_callback
