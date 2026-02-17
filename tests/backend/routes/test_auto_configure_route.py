"""
Tests for the POST /endpoints/auto-configure route.

Run with:
  cd apps/backend
  RHESIS_SKIP_MIGRATIONS=1 uv run pytest ../../tests/backend/routes/test_auto_configure_route.py -v
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.schemas.endpoint import (
    AutoConfigureResult,
)


class TestAutoConfigureRoute:
    """Tests for the auto-configure endpoint route."""

    def test_auto_configure_route_success(self, authenticated_client: TestClient):
        """POST /endpoints/auto-configure should return 200 with result."""
        mock_result = AutoConfigureResult(
            status="success",
            request_mapping={"query": "{{ input }}"},
            response_mapping={"output": "$.response"},
            request_headers={"Content-Type": "application/json"},
            url="https://api.example.com",
            method="POST",
            confidence=0.85,
            reasoning="Detected API",
            warnings=[],
            probe_success=True,
            probe_attempts=1,
        )

        with patch("rhesis.backend.app.routers.endpoint.AutoConfigureService") as MockService:
            mock_instance = MagicMock()
            mock_instance.auto_configure = AsyncMock(return_value=mock_result)
            MockService.return_value = mock_instance

            response = authenticated_client.post(
                "/endpoints/auto-configure",
                json={
                    "input_text": ("curl -X POST https://api.example.com"),
                    "url": "https://api.example.com",
                    "auth_token": "token123",
                    "probe": True,
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert data["request_mapping"] is not None
            assert data["confidence"] == 0.85

    def test_auto_configure_route_unauthenticated(self, client: TestClient):
        """POST /endpoints/auto-configure without auth should return 401/403."""
        response = client.post(
            "/endpoints/auto-configure",
            json={
                "input_text": "some code",
                "url": "https://api.example.com",
            },
        )

        # Should be rejected - 401 or 403
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_auto_configure_route_missing_input_text(self, authenticated_client: TestClient):
        """POST /endpoints/auto-configure with missing input_text should return 422."""
        response = authenticated_client.post(
            "/endpoints/auto-configure",
            json={
                "url": "https://api.example.com",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_auto_configure_route_llm_unavailable(self, authenticated_client: TestClient):
        """LLM unavailable should return a clear error."""
        with patch("rhesis.backend.app.routers.endpoint.AutoConfigureService") as MockService:
            MockService.side_effect = ValueError("No AI model configured")

            response = authenticated_client.post(
                "/endpoints/auto-configure",
                json={
                    "input_text": "some code",
                    "url": "https://api.example.com",
                },
            )

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
