"""``generation.py`` must not query the database on the event loop.

Both endpoints behind these functions (``POST /services/generate/tests`` and
``POST /services/generate/multiturn-tests``) are ``async def`` handlers holding
an ``OffLoopSession``. That annotation is a promise that every use of the
session happens inside ``anyio.to_thread.run_sync``.
``tests/backend/test_no_sync_db_on_loop.py`` cannot see inside a handler; these
tests are the check that the work actually left the loop.
"""

import threading
from contextlib import contextmanager
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


def _recording_descriptions(threads: list, found: dict):
    """A ``get_requirement_descriptions`` stand-in that records the thread it ran on."""

    def _get(_db, names):
        threads.append(threading.get_ident())
        return {n: found[n] for n in names if n in found}

    return _get


@pytest.mark.unit
class TestRequirementDescriptions:
    """Generated tests should check what a requirement says, not just its name."""

    def test_stored_descriptions_are_looked_up_by_name(self):
        stored = {"R1: Never diagnoses": "No reply names a condition."}
        with patch.object(generation, "get_requirement_descriptions", lambda _db, _n: stored):
            result = generation.requirement_descriptions(MagicMock(), ["R1: Never diagnoses"])

        assert result == stored

    def test_nothing_found_is_none(self):
        with patch.object(generation, "get_requirement_descriptions", lambda _db, _n: {}):
            assert generation.requirement_descriptions(MagicMock(), ["A"]) is None

    def test_in_project_lookup_reads_under_that_project(self):
        scopes = []

        @contextmanager
        def _scope(_db, org, user, project):
            scopes.append((org, user, project))
            yield

        with (
            patch.object(generation, "temporary_project_scope", _scope),
            patch.object(generation, "get_requirement_descriptions", lambda _db, _n: {"A": "x"}),
        ):
            result = generation.requirement_descriptions_in_project(
                MagicMock(), "org", "user", "project", ["A"]
            )

        assert result == {"A": "x"}
        assert scopes == [("org", "user", "project")]

    @pytest.mark.asyncio
    async def test_single_turn_uses_stored_descriptions_in_the_same_worker_thread(self):
        model_threads: list = []
        lookup_threads: list = []
        # A client-sent value is replaced, and the caller's config is left alone.
        config = generation.GenerationConfig(
            requirements=["R1"], requirement_descriptions={"R1": "from the client"}
        )
        synthesizer = MagicMock()
        synthesizer.generate.return_value.to_dict.return_value = {"tests": []}

        with (
            patch.object(generation, "resolve_model", _recording_resolve_model(model_threads)),
            patch.object(
                generation,
                "get_requirement_descriptions",
                _recording_descriptions(lookup_threads, {"R1": "AC"}),
            ),
            patch.object(generation, "ConfigSynthesizer", return_value=synthesizer) as synth_cls,
        ):
            await generation.generate_tests(
                db=MagicMock(), user=MagicMock(), config=config, num_tests=1
            )

        assert lookup_threads == model_threads
        assert threading.get_ident() not in lookup_threads
        assert synth_cls.call_args.kwargs["config"].requirement_descriptions == {"R1": "AC"}
        assert config.requirement_descriptions == {"R1": "from the client"}

    @pytest.mark.asyncio
    async def test_single_turn_stream_looks_up_off_the_loop(self):
        threads: list = []
        config = generation.GenerationConfig(requirements=["R1"])

        async def _stream(num_tests):
            yield {"prompt": "hi"}

        synthesizer = MagicMock()
        synthesizer.generate_stream = _stream

        with (
            patch.object(generation, "resolve_model", MagicMock()),
            patch.object(
                generation,
                "get_requirement_descriptions",
                _recording_descriptions(threads, {"R1": "AC"}),
            ),
            patch.object(generation, "ConfigSynthesizer", return_value=synthesizer) as synth_cls,
        ):
            tests = [
                t
                async for t in generation.generate_tests_stream(
                    db=MagicMock(), user=MagicMock(), config=config, num_tests=1
                )
            ]

        assert tests == [{"prompt": "hi"}]
        assert threads and threading.get_ident() not in threads
        assert synth_cls.call_args.kwargs["config"].requirement_descriptions == {"R1": "AC"}

    @pytest.mark.asyncio
    async def test_multi_turn_uses_stored_descriptions_in_the_same_worker_thread(self):
        model_threads: list = []
        lookup_threads: list = []
        synthesizer = MagicMock()
        synthesizer.generate.return_value.to_dict.return_value = {"tests": []}

        with (
            patch.object(generation, "resolve_model", _recording_resolve_model(model_threads)),
            patch.object(
                generation,
                "get_requirement_descriptions",
                _recording_descriptions(lookup_threads, {"R1": "AC"}),
            ),
            patch(
                "rhesis.sdk.synthesizers.multi_turn.base.MultiTurnSynthesizer",
                return_value=synthesizer,
            ) as synth_cls,
        ):
            await generation.generate_multiturn_tests(
                db=MagicMock(),
                user=MagicMock(),
                config={
                    "generation_prompt": "test",
                    "requirements": ["R1"],
                    "requirement_descriptions": {"R1": "from the client"},
                },
                num_tests=1,
            )

        assert lookup_threads == model_threads
        assert threading.get_ident() not in lookup_threads
        assert synth_cls.call_args.kwargs["config"].requirement_descriptions == {"R1": "AC"}

    @pytest.mark.asyncio
    async def test_multi_turn_stream_looks_up_off_the_loop(self):
        threads: list = []

        async def _stream(num_tests):
            yield {"goal": "x"}

        synthesizer = MagicMock()
        synthesizer.generate_stream = _stream

        with (
            patch.object(generation, "resolve_model", MagicMock()),
            patch.object(
                generation,
                "get_requirement_descriptions",
                _recording_descriptions(threads, {"R1": "AC"}),
            ),
            patch(
                "rhesis.sdk.synthesizers.multi_turn.base.MultiTurnSynthesizer",
                return_value=synthesizer,
            ) as synth_cls,
        ):
            tests = [
                t
                async for t in generation.generate_multiturn_tests_stream(
                    db=MagicMock(),
                    user=MagicMock(),
                    config={"generation_prompt": "test", "requirement": ["R1"]},
                    num_tests=1,
                )
            ]

        assert tests == [{"goal": "x"}]
        assert threads and threading.get_ident() not in threads
        assert synth_cls.call_args.kwargs["config"].requirement_descriptions == {"R1": "AC"}


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
