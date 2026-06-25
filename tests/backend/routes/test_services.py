from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

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

        with patch(
            "rhesis.backend.app.utils.user_model_utils.get_generation_model_with_override"
        ) as mock_get_gen:
            mock_model = MagicMock()
            mock_model.a_generate = AsyncMock(return_value=expected_response)
            mock_get_gen.return_value = mock_model

            result = await generate_content_endpoint(
                mock_request, db=mock_db, current_user=mock_user
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

        with patch(
            "rhesis.backend.app.utils.user_model_utils.get_generation_model_with_override"
        ) as mock_get_gen:
            mock_get_gen.side_effect = Exception("Model initialization failed")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await generate_content_endpoint(
                    mock_request, db=mock_db, current_user=mock_user
                )

            assert exc_info.value.status_code == 400
            assert "Failed to generate content:" in str(exc_info.value.detail)
            assert "Model initialization failed" in str(exc_info.value.detail)
