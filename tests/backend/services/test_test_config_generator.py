"""``TestConfigGeneratorService`` must not query the database on the event loop.

``POST /services/generate/test_config`` is an ``async def`` handler holding an
``OffLoopSession``: the requirements/project read and the template render all
have to happen inside ``anyio.to_thread.run_sync``. The guard test in
``tests/backend/test_no_sync_db_on_loop.py`` cannot see that far, so this does.
"""

import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.schemas.services import TestConfigResponse
from rhesis.backend.app.services.test_config_generator import TestConfigGeneratorService


def _service_with_stub_llm(llm) -> TestConfigGeneratorService:
    """Build the service without letting its constructor resolve a real model."""
    with patch.object(TestConfigGeneratorService, "_resolve_llm", return_value=llm):
        return TestConfigGeneratorService(db=MagicMock(), user=MagicMock())


@pytest.mark.unit
class TestGenerateConfigRunsDatabaseWorkOffTheLoop:
    @pytest.mark.asyncio
    async def test_prompt_is_rendered_in_a_worker_thread(self):
        threads: list = []
        expected = TestConfigResponse(requirements=[], topics=[], categories=[])
        llm = MagicMock()
        llm.a_generate = AsyncMock(return_value=expected)
        service = _service_with_stub_llm(llm)

        def _render(*_args):
            threads.append(threading.get_ident())
            return "rendered prompt"

        with patch.object(service, "_render_prompt", _render):
            result = await service.generate_config("test the login flow", organization_id="org-1")

        assert result is expected
        assert threads and threading.get_ident() not in threads
        llm.a_generate.assert_awaited_once_with("rendered prompt", schema=TestConfigResponse)

    @pytest.mark.asyncio
    async def test_a_dict_response_is_coerced_to_the_schema(self):
        llm = MagicMock()
        llm.a_generate = AsyncMock(
            return_value={"requirements": [], "topics": [], "categories": []}
        )
        service = _service_with_stub_llm(llm)

        with patch.object(service, "_render_prompt", lambda *_: "rendered prompt"):
            result = await service.generate_config("test the login flow", organization_id="org-1")

        assert isinstance(result, TestConfigResponse)

    @pytest.mark.asyncio
    async def test_provider_error_dict_becomes_a_runtime_error(self):
        llm = MagicMock()
        llm.a_generate = AsyncMock(return_value={"error": "context length exceeded"})
        service = _service_with_stub_llm(llm)

        with patch.object(service, "_render_prompt", lambda *_: "rendered prompt"):
            with pytest.raises(RuntimeError, match="context length exceeded"):
                await service.generate_config("test the login flow", organization_id="org-1")

    @pytest.mark.asyncio
    async def test_empty_prompt_is_rejected_before_any_read(self):
        llm = MagicMock()
        llm.a_generate = AsyncMock()
        service = _service_with_stub_llm(llm)
        render = MagicMock()

        with patch.object(service, "_render_prompt", render):
            with pytest.raises(ValueError, match="Prompt cannot be empty"):
                await service.generate_config("   ", organization_id="org-1")

        render.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_organization_is_rejected_before_any_read(self):
        llm = MagicMock()
        llm.a_generate = AsyncMock()
        service = _service_with_stub_llm(llm)
        render = MagicMock()

        with patch.object(service, "_render_prompt", render):
            with pytest.raises(ValueError, match="organization_id are required"):
                await service.generate_config("test the login flow", organization_id=None)

        render.assert_not_called()


@pytest.mark.unit
class TestRenderPrompt:
    def test_unknown_project_is_rejected(self):
        service = _service_with_stub_llm(MagicMock())

        with (
            patch(
                "rhesis.backend.app.services.test_config_generator.requirement_crud.get_requirements",
                return_value=[],
            ),
            patch(
                "rhesis.backend.app.services.test_config_generator.get_project",
                return_value=None,
            ),
        ):
            with pytest.raises(ValueError, match="not found or not accessible"):
                service._render_prompt("prompt", "org-1", "project-1", None)

    def test_requirements_are_read_into_plain_dicts(self):
        service = _service_with_stub_llm(MagicMock())
        requirement = MagicMock()
        requirement.name = "Accuracy"
        requirement.description = None

        with patch(
            "rhesis.backend.app.services.test_config_generator.requirement_crud.get_requirements",
            return_value=[requirement],
        ):
            rendered = service._render_prompt("prompt", "org-1", None, None)

        assert "Accuracy" in rendered
