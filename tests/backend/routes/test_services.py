from unittest.mock import MagicMock, patch

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

        # Mock the get_model factory function to return a mock model
        with patch("rhesis.sdk.models.factory.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.generate.return_value = expected_response
            mock_get_model.return_value = mock_model

            # Act
            result = await generate_content_endpoint(mock_request)

            # Assert
            assert result == expected_response
            mock_model.generate.assert_called_once_with(
                "Generate a test function",
                schema={"type": "object", "properties": {"code": {"type": "string"}}},
            )

    @pytest.mark.asyncio
    async def test_generate_content_endpoint_exception_handling(self):
        """Test that exceptions are properly handled and converted to HTTPException."""
        # Arrange
        mock_request = GenerateContentRequest(
            prompt="Generate a test function",
            schema={"type": "object"},
        )

        # Mock the get_model factory function to raise an exception
        with patch("rhesis.sdk.models.factory.get_model") as mock_get_model:
            mock_get_model.side_effect = Exception("Model initialization failed")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await generate_content_endpoint(mock_request)

            assert exc_info.value.status_code == 400
            assert "Failed to generate content:" in str(exc_info.value.detail)
            assert "Model initialization failed" in str(exc_info.value.detail)
