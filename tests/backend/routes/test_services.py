import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Response

from rhesis.backend.app.routers.services import generate_content_endpoint
from rhesis.backend.app.schemas.services import GenerateContentRequest


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
    async def test_generate_content_endpoint_exception_handling(self):
        """Test that exceptions are properly handled and converted to HTTPException."""
        # Arrange
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

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await generate_content_endpoint(
                    mock_request, http_response, db=mock_db, current_user=mock_user
                )

            assert exc_info.value.status_code == 400
            assert "Failed to generate content:" in str(exc_info.value.detail)
            assert "Model initialization failed" in str(exc_info.value.detail)


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
