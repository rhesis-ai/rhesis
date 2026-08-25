"""
Unit tests for the async-dispatch wiring of the OWASP generation router
endpoint — calls the route handler coroutine directly (bypassing FastAPI's
dependency injection) with mocked dependencies, mirroring
test_garak_async_dispatch.py's approach for the sibling Garak router:
- generate launches generate_and_save_owasp_test_set via launch_job and
  returns the 202 task-response shape
- request fields are forwarded to the task unchanged
"""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.routers.owasp import generate_test_set
from rhesis.backend.app.schemas.owasp import OwaspFramework, OwaspGenerateRequest


@pytest.mark.unit
class TestGenerateTestSetDispatch:
    @pytest.mark.asyncio
    async def test_dispatches_generation_task_and_returns_202_shape(self):
        request = OwaspGenerateRequest(
            framework=OwaspFramework.LLM,
            purpose="Customer service chatbot for a bank",
            categories=["llm01"],
            num_tests=10,
        )
        current_user = MagicMock(organization_id="org-1")

        with patch("rhesis.backend.app.routers.owasp.launch_job") as mock_launcher:
            mock_launcher.return_value = MagicMock(id="task-owasp-123")

            response = await generate_test_set(
                request=request,
                current_user=current_user,
                db=MagicMock(),
            )

        mock_launcher.assert_called_once()
        _, call_kwargs = mock_launcher.call_args
        assert call_kwargs["current_user"] is current_user
        assert call_kwargs["framework"] == "llm"
        assert call_kwargs["purpose"] == "Customer service chatbot for a bank"
        assert call_kwargs["categories"] == ["llm01"]
        assert call_kwargs["num_tests"] == 10

        assert response.task_id == "task-owasp-123"
        assert response.framework == OwaspFramework.LLM
        assert response.num_tests == 10

    @pytest.mark.asyncio
    async def test_defaults_categories_to_none_for_whole_report(self):
        """Omitting `categories` must reach the task as None, not an empty
        list -- the task/synthesizer treats None as "every section"."""
        request = OwaspGenerateRequest(purpose="Autonomous coding agent")
        current_user = MagicMock(organization_id="org-1")

        with patch("rhesis.backend.app.routers.owasp.launch_job") as mock_launcher:
            mock_launcher.return_value = MagicMock(id="task-owasp-456")

            await generate_test_set(
                request=request,
                current_user=current_user,
                db=MagicMock(),
            )

        _, call_kwargs = mock_launcher.call_args
        assert call_kwargs["categories"] is None
