"""``generation.py`` must not query the database on the event loop.

Both endpoints behind these functions (``POST /services/generate/tests`` and
``POST /services/generate/multiturn-tests``) are ``async def`` handlers holding
an ``OffLoopSession``. That annotation is a promise that every use of the
session happens inside ``anyio.to_thread.run_sync``.
``tests/backend/test_no_sync_db_on_loop.py`` cannot see inside a handler; these
tests are the check that the work actually left the loop.
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.services import generation
from tests.backend._helpers import records_thread


def _recording_resolve_model(threads: list):
    """A ``resolve_model`` stand-in that records the thread it ran on."""
    return records_thread(threads, MagicMock(name="model"))


@pytest.mark.unit
class TestGenerateTestsRunsDatabaseWorkOffTheLoop:
    @pytest.mark.asyncio
    async def test_model_resolution_happens_in_a_worker_thread(self):
        threads: list = []
        synthesizer = MagicMock()
        synthesizer.generate.return_value.to_dict.return_value = {"tests": [{"prompt": "hi"}]}

        with (
            patch.object(generation, "resolve_model", _recording_resolve_model(threads)),
            patch.object(generation, "ConfigSynthesizer", return_value=synthesizer),
        ):
            tests = await generation.generate_tests(
                db=MagicMock(), user=MagicMock(), config=MagicMock(), num_tests=1
            )

        assert tests == [{"prompt": "hi"}]
        assert threads and threading.get_ident() not in threads

    @pytest.mark.asyncio
    async def test_source_content_is_loaded_in_the_same_worker_thread(self):
        threads: list = []
        source_threads: list = []
        synthesizer = MagicMock()
        synthesizer.generate.return_value.to_dict.return_value = {"tests": []}

        def _get_source_specifications(**_kwargs):
            source_threads.append(threading.get_ident())
            return []

        with (
            patch.object(generation, "resolve_model", _recording_resolve_model(threads)),
            patch.object(generation, "get_source_specifications", _get_source_specifications),
            patch.object(generation, "ConfigSynthesizer", return_value=synthesizer),
        ):
            await generation.generate_tests(
                db=MagicMock(),
                user=MagicMock(),
                config=MagicMock(),
                num_tests=1,
                sources=[MagicMock()],
            )

        # One hop for both reads, and not the event loop's thread.
        assert source_threads == threads
        assert threading.get_ident() not in threads


@pytest.mark.unit
class TestGenerateMultiturnTestsRunsDatabaseWorkOffTheLoop:
    @pytest.mark.asyncio
    async def test_model_resolution_happens_in_a_worker_thread(self):
        threads: list = []
        synthesizer = MagicMock()
        synthesizer.generate.return_value.to_dict.return_value = {"tests": [{"goal": "x"}]}

        with (
            patch.object(generation, "resolve_model", _recording_resolve_model(threads)),
            patch(
                "rhesis.sdk.synthesizers.multi_turn.base.MultiTurnSynthesizer",
                return_value=synthesizer,
            ),
        ):
            result = await generation.generate_multiturn_tests(
                db=MagicMock(),
                user=MagicMock(),
                config={"generation_prompt": "test a chatbot"},
                num_tests=1,
            )

        assert result == {"tests": [{"goal": "x"}]}
        assert threads and threading.get_ident() not in threads


@pytest.mark.unit
class TestValidateModelOverride:
    def test_no_override_reads_nothing(self):
        with patch("rhesis.backend.app.crud.model.get_model") as mock_get_model:
            generation.validate_model_override(MagicMock(), MagicMock(), None)

        mock_get_model.assert_not_called()

    def test_unknown_override_is_a_400(self):
        from fastapi import HTTPException

        with patch("rhesis.backend.app.crud.model.get_model", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                generation.validate_model_override(MagicMock(), MagicMock(), "model-uuid")

        assert exc_info.value.status_code == 400
        assert "model-uuid" in exc_info.value.detail

    def test_known_override_passes(self):
        user = MagicMock()

        with patch(
            "rhesis.backend.app.crud.model.get_model", return_value=MagicMock()
        ) as mock_get_model:
            generation.validate_model_override(MagicMock(), user, "model-uuid")

        # Looked up under the caller's tenant, not globally.
        assert mock_get_model.call_args.kwargs["organization_id"] == str(user.organization_id)
