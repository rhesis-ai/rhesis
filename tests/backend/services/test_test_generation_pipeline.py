"""Tests for the streaming test generation pipeline.

Covers streamed config generation, test generation, DB context fetching,
and error handling across both phases.
"""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.schemas.services import TestConfigResponse
from rhesis.backend.app.services.test_generation_pipeline import (
    _fetch_db_context,
    _render_config_prompt,
    _stream_config,
    test_generation_pipeline_stream,
)
from rhesis.sdk.synthesizers.streaming import IncrementalJsonArrayParser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(model_id=None):
    """Build a minimal User-like object with settings."""
    gen = SimpleNamespace(model_id=model_id)
    models = SimpleNamespace(generation=gen)
    settings = SimpleNamespace(models=models)
    return SimpleNamespace(
        settings=settings,
        organization_id=uuid.uuid4(),
    )


def _make_behavior(name, description=""):
    return SimpleNamespace(name=name, description=description)


def _make_project(name="TestProject", description="A test project"):
    return SimpleNamespace(name=name, description=description)


def _streaming_llm(behaviors=None, topics=None, categories=None):
    """Return a mock LLM whose generate_stream yields a single combined JSON.

    The response is a JSON object with ``behaviors``, ``topics``, and
    ``categories`` arrays, streamed character-by-character so the
    ``IncrementalConfigParser`` can parse items incrementally.
    """
    response = json.dumps(
        {
            "behaviors": behaviors or [],
            "topics": topics or [],
            "categories": categories or [],
        }
    )

    async def _fake_stream(prompt, schema=None):
        for ch in response:
            yield ch

    llm = MagicMock()
    llm.generate_stream = MagicMock(side_effect=_fake_stream)
    return llm


def _db_context(**overrides):
    ctx = {
        "prompt": "test a chatbot",
        "sample_size": 6,
        "behaviors": [{"name": "Accuracy", "description": "Correct answers"}],
        "project_name": None,
        "project_description": None,
        "previous_messages": [],
    }
    ctx.update(overrides)
    return ctx


async def _collect_ndjson(async_gen):
    """Consume an async bytes generator and parse NDJSON events."""
    events = []
    async for chunk in async_gen:
        line = chunk.decode("utf-8").strip()
        if line:
            events.append(json.loads(line))
    return events


# ---------------------------------------------------------------------------
# _fetch_db_context
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.services
class TestFetchDbContext:
    def test_returns_behaviors_and_prompt(self):
        mock_db = MagicMock()
        behaviors = [_make_behavior("Accuracy", "Be accurate")]
        org_id = str(uuid.uuid4())

        with patch("rhesis.backend.app.services.test_generation_pipeline.crud") as crud:
            crud.get_behaviors.return_value = behaviors
            ctx = _fetch_db_context(
                db=mock_db,
                organization_id=org_id,
                prompt="test chatbot",
            )

        assert ctx["prompt"] == "test chatbot"
        assert len(ctx["behaviors"]) == 1
        assert ctx["behaviors"][0]["name"] == "Accuracy"
        assert ctx["project_name"] is None
        assert ctx["previous_messages"] == []

    def test_fetches_project_when_id_provided(self):
        mock_db = MagicMock()
        org_id = str(uuid.uuid4())
        project_id = str(uuid.uuid4())
        project = _make_project("MyProject", "A chatbot")

        with patch("rhesis.backend.app.services.test_generation_pipeline.crud") as crud:
            crud.get_behaviors.return_value = []
            crud.get_project.return_value = project
            ctx = _fetch_db_context(
                db=mock_db,
                organization_id=org_id,
                prompt="test",
                project_id=project_id,
            )

        assert ctx["project_name"] == "MyProject"
        assert ctx["project_description"] == "A chatbot"

    def test_raises_when_project_not_found(self):
        mock_db = MagicMock()
        org_id = str(uuid.uuid4())

        with patch("rhesis.backend.app.services.test_generation_pipeline.crud") as crud:
            crud.get_behaviors.return_value = []
            crud.get_project.return_value = None
            with pytest.raises(ValueError, match="not found"):
                _fetch_db_context(
                    db=mock_db,
                    organization_id=org_id,
                    prompt="test",
                    project_id=str(uuid.uuid4()),
                )

    def test_passes_previous_messages(self):
        mock_db = MagicMock()
        msgs = [{"content": "refine"}]

        with patch("rhesis.backend.app.services.test_generation_pipeline.crud") as crud:
            crud.get_behaviors.return_value = []
            ctx = _fetch_db_context(
                db=mock_db,
                organization_id=str(uuid.uuid4()),
                prompt="test",
                previous_messages=msgs,
            )

        assert ctx["previous_messages"] == msgs


# ---------------------------------------------------------------------------
# _render_config_prompt
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.services
class TestRenderConfigPrompt:
    def test_renders_template_with_behaviors(self):
        ctx = _db_context()
        result = _render_config_prompt(ctx)
        assert "Accuracy" in result
        assert "test a chatbot" in result

    def test_includes_project_context(self):
        ctx = _db_context(
            project_name="FinBot",
            project_description="Financial advisor",
        )
        result = _render_config_prompt(ctx)
        assert "FinBot" in result
        assert "Financial advisor" in result


# ---------------------------------------------------------------------------
# _stream_config
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestStreamConfig:
    async def test_yields_config_items_from_all_dimensions(self):
        llm = _streaming_llm(
            behaviors=[
                {"name": "Accuracy", "description": "Be accurate", "active": True},
            ],
            topics=[
                {"name": "Auth", "description": "Authentication", "active": True},
            ],
            categories=[
                {"name": "Security", "description": "Security tests", "active": False},
            ],
        )

        events = []
        async for event in _stream_config(llm, _db_context()):
            events.append(event)

        config_items = [e for e in events if e["type"] == "config_item"]
        categories_seen = {e["category"] for e in config_items}

        assert categories_seen == {"behaviors", "topics", "categories"}
        assert len(config_items) == 3

    async def test_yields_config_done_with_total(self):
        llm = _streaming_llm(
            behaviors=[
                {"name": "B1", "description": "d", "active": True},
                {"name": "B2", "description": "d", "active": True},
            ],
            topics=[
                {"name": "T1", "description": "d", "active": True},
            ],
            categories=[],
        )

        events = []
        async for event in _stream_config(llm, _db_context()):
            events.append(event)

        done_events = [e for e in events if e["type"] == "config_done"]
        assert len(done_events) == 1
        assert done_events[0]["total"] == 3

    async def test_yields_collected_config_response(self):
        llm = _streaming_llm(
            behaviors=[
                {"name": "B1", "description": "d", "active": True},
            ],
            topics=[
                {"name": "T1", "description": "d", "active": False},
            ],
            categories=[
                {"name": "C1", "description": "d", "active": True},
            ],
        )

        collected = None
        async for event in _stream_config(llm, _db_context()):
            if event.get("type") == "_collected":
                collected = event["config"]

        assert collected is not None
        assert isinstance(collected, TestConfigResponse)
        assert len(collected.behaviors) == 1
        assert len(collected.topics) == 1
        assert len(collected.categories) == 1

    async def test_skips_items_without_name(self):
        llm = _streaming_llm(
            behaviors=[
                {"name": "", "description": "no name", "active": True},
                {"name": "Valid", "description": "ok", "active": True},
            ],
            topics=[],
            categories=[],
        )

        events = []
        async for event in _stream_config(llm, _db_context()):
            events.append(event)

        config_items = [e for e in events if e["type"] == "config_item"]
        assert len(config_items) == 1
        assert config_items[0]["name"] == "Valid"

    async def test_handles_llm_error_gracefully(self):
        """If the LLM call fails, an error event is emitted."""

        async def _failing_stream(prompt, schema=None):
            raise RuntimeError("LLM exploded")
            yield  # noqa: RET503

        llm = MagicMock()
        llm.generate_stream = MagicMock(side_effect=_failing_stream)

        events = []
        async for event in _stream_config(llm, _db_context()):
            events.append(event)

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "LLM exploded" in error_events[0]["message"]

        done_events = [e for e in events if e["type"] == "config_done"]
        assert len(done_events) == 1
        assert done_events[0]["total"] == 0


# ---------------------------------------------------------------------------
# IncrementalConfigParser
# ---------------------------------------------------------------------------


def _config_response_json(**overrides):
    payload = {
        "behaviors": [
            {"name": "Compliance", "description": "d", "active": True},
            {"name": "Reliability", "description": "d", "active": True},
        ],
        "topics": [
            {"name": "Claim Process", "description": "d", "active": True},
            {"name": "Insurance Policy", "description": "d", "active": False},
        ],
        "categories": [
            {"name": "Functional Testing", "description": "d", "active": True},
            {"name": "Security Testing", "description": "d", "active": False},
        ],
    }
    payload.update(overrides)
    return json.dumps(payload)


@pytest.mark.unit
@pytest.mark.services
class TestIncrementalConfigParser:
    def test_single_chunk_attributes_each_array(self):
        """Non-streaming models may deliver the full JSON in one chunk."""
        from rhesis.backend.app.services.streaming_utils import IncrementalConfigParser

        parser = IncrementalConfigParser()
        parsed = parser.feed(_config_response_json())

        assert [cat for cat, _ in parsed] == [
            "behaviors",
            "behaviors",
            "topics",
            "topics",
            "categories",
            "categories",
        ]

    def test_char_stream_attributes_each_array(self):
        from rhesis.backend.app.services.streaming_utils import IncrementalConfigParser

        parser = IncrementalConfigParser()
        parsed = []
        for ch in _config_response_json():
            parsed.extend(parser.feed(ch))

        assert {cat for cat, _ in parsed} == {"behaviors", "topics", "categories"}
        assert len(parsed) == 6

    def test_empty_array_does_not_shift_later_keys(self):
        from rhesis.backend.app.services.streaming_utils import IncrementalConfigParser

        parser = IncrementalConfigParser()
        parsed = parser.feed(
            _config_response_json(
                behaviors=[],
                topics=[{"name": "Auth", "description": "d", "active": True}],
                categories=[{"name": "Security", "description": "d", "active": True}],
            )
        )

        assert parsed == [
            ("topics", {"name": "Auth", "description": "d", "active": True}),
            ("categories", {"name": "Security", "description": "d", "active": True}),
        ]


# ---------------------------------------------------------------------------
# IncrementalJsonArrayParser
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.services
class TestIncrementalJsonArrayParser:
    def test_nested_arrays_do_not_break_parsing(self):
        """Objects containing nested arrays must not prematurely close the top-level array."""
        stream = json.dumps(
            {
                "tests": [
                    {"name": "A", "tags": ["x", "y"]},
                    {"name": "B", "tags": ["z"]},
                ]
            }
        )
        parser = IncrementalJsonArrayParser()
        results = parser.feed(stream)
        assert len(results) == 2
        assert results[0]["name"] == "A"
        assert results[0]["tags"] == ["x", "y"]
        assert results[1]["name"] == "B"

    def test_buffer_is_trimmed(self):
        """After emitting objects the consumed buffer prefix should be trimmed."""
        parser = IncrementalJsonArrayParser()
        parser.feed('{"items": [{"a": 1}')
        assert len(parser._buffer) < 25
        parser.feed(', {"b": 2}]}')
        assert len(parser._buffer) < 15

    def test_strings_with_braces_and_brackets(self):
        """Braces and brackets inside JSON strings must not affect parsing."""
        stream = json.dumps(
            {
                "items": [
                    {"val": "has { and [ and ] and }"},
                    {"val": "ok"},
                ]
            }
        )
        parser = IncrementalJsonArrayParser()
        results = parser.feed(stream)
        assert len(results) == 2
        assert results[0]["val"] == "has { and [ and ] and }"


# ---------------------------------------------------------------------------
# test_generation_pipeline_stream (end-to-end)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.services
@pytest.mark.asyncio
class TestPipelineStream:
    async def test_single_turn_pipeline(self):
        """Full pipeline: config → single-turn streaming tests → done."""
        user = _make_user()
        mock_db = MagicMock()
        org_id = str(uuid.uuid4())

        llm = _streaming_llm(
            behaviors=[
                {"name": "Accuracy", "description": "d", "active": True},
            ],
            topics=[
                {"name": "Auth", "description": "d", "active": True},
            ],
            categories=[
                {"name": "Functional", "description": "d", "active": True},
            ],
        )

        fake_tests = [
            {"prompt": {"content": "test1"}, "behavior": "Accuracy"},
            {"prompt": {"content": "test2"}, "behavior": "Accuracy"},
        ]

        async def _fake_stream(**kwargs):
            for t in fake_tests:
                yield t

        with (
            patch(
                "rhesis.backend.app.services.test_generation_pipeline._resolve_config_llm",
                return_value=llm,
            ),
            patch(
                "rhesis.backend.app.services.test_generation_pipeline._fetch_db_context",
                return_value=_db_context(),
            ),
            patch(
                "rhesis.backend.app.services.test_generation_pipeline.generate_tests_stream",
                side_effect=_fake_stream,
            ) as mock_gen,
        ):
            events = await _collect_ndjson(
                test_generation_pipeline_stream(
                    db=mock_db,
                    user=user,
                    prompt="test a chatbot",
                    organization_id=org_id,
                    num_tests=2,
                )
            )

        types = [e["type"] for e in events]
        assert "config_item" in types
        assert "config_done" in types
        assert "test" in types
        assert "tests_done" in types
        assert types[-1] == "done"

        test_events = [e for e in events if e["type"] == "test"]
        assert len(test_events) == 2
        assert all(e["test_type"] == "single_turn" for e in test_events)

        done_event = next(e for e in events if e["type"] == "tests_done")
        assert done_event["total"] == 2

        mock_gen.assert_called_once()

    async def test_multi_turn_pipeline(self):
        """Full pipeline with multi-turn streaming test type."""
        user = _make_user()
        mock_db = MagicMock()
        org_id = str(uuid.uuid4())

        llm = _streaming_llm(
            behaviors=[
                {"name": "B", "description": "d", "active": True},
            ],
            topics=[
                {"name": "T", "description": "d", "active": True},
            ],
            categories=[
                {"name": "C", "description": "d", "active": True},
            ],
        )

        fake_tests = [
            {"test_configuration": {"goal": "test goal"}, "behavior": "B"},
        ]

        async def _fake_stream(**kwargs):
            for t in fake_tests:
                yield t

        with (
            patch(
                "rhesis.backend.app.services.test_generation_pipeline._resolve_config_llm",
                return_value=llm,
            ),
            patch(
                "rhesis.backend.app.services.test_generation_pipeline._fetch_db_context",
                return_value=_db_context(),
            ),
            patch(
                "rhesis.backend.app.services.test_generation_pipeline.generate_multiturn_tests_stream",
                side_effect=_fake_stream,
            ) as mock_gen,
        ):
            events = await _collect_ndjson(
                test_generation_pipeline_stream(
                    db=mock_db,
                    user=user,
                    prompt="test chatbot",
                    organization_id=org_id,
                    test_type="multi_turn",
                    num_tests=1,
                )
            )

        test_events = [e for e in events if e["type"] == "test"]
        assert len(test_events) == 1
        assert test_events[0]["test_type"] == "multi_turn"
        mock_gen.assert_called_once()

    async def test_config_failure_aborts_pipeline(self):
        """If config generation fails, pipeline skips Phase 2 entirely."""
        user = _make_user()
        mock_db = MagicMock()

        async def _always_fail(prompt, schema=None):
            raise RuntimeError("LLM down")
            yield  # noqa: RET503

        llm = MagicMock()
        llm.generate_stream = MagicMock(side_effect=_always_fail)

        with (
            patch(
                "rhesis.backend.app.services.test_generation_pipeline._resolve_config_llm",
                return_value=llm,
            ),
            patch(
                "rhesis.backend.app.services.test_generation_pipeline._fetch_db_context",
                return_value=_db_context(),
            ),
        ):
            events = await _collect_ndjson(
                test_generation_pipeline_stream(
                    db=mock_db,
                    user=user,
                    prompt="test",
                    organization_id=str(uuid.uuid4()),
                )
            )

        types = [e["type"] for e in events]
        assert "error" in types
        assert "test" not in types
        assert types[-1] == "done"

    async def test_test_generation_failure_reports_error(self):
        """If test generation raises, error event is emitted but pipeline finishes."""
        user = _make_user()
        mock_db = MagicMock()

        llm = _streaming_llm(
            behaviors=[
                {"name": "B", "description": "d", "active": True},
            ],
            topics=[
                {"name": "T", "description": "d", "active": True},
            ],
            categories=[
                {"name": "C", "description": "d", "active": True},
            ],
        )

        async def _failing_stream(**kwargs):
            raise RuntimeError("generation boom")
            yield  # noqa: RET503

        with (
            patch(
                "rhesis.backend.app.services.test_generation_pipeline._resolve_config_llm",
                return_value=llm,
            ),
            patch(
                "rhesis.backend.app.services.test_generation_pipeline._fetch_db_context",
                return_value=_db_context(),
            ),
            patch(
                "rhesis.backend.app.services.test_generation_pipeline.generate_tests_stream",
                side_effect=_failing_stream,
            ),
        ):
            events = await _collect_ndjson(
                test_generation_pipeline_stream(
                    db=mock_db,
                    user=user,
                    prompt="test",
                    organization_id=str(uuid.uuid4()),
                )
            )

        types = [e["type"] for e in events]
        assert "config_done" in types
        error_events = [e for e in events if e["type"] == "error"]
        assert any("generation boom" in e["message"] for e in error_events)
        assert "tests_done" in types
        assert types[-1] == "done"

    async def test_inactive_behaviors_fallback(self):
        """When all behaviors are inactive, pipeline uses the first one."""
        user = _make_user()
        mock_db = MagicMock()

        llm = _streaming_llm(
            behaviors=[
                {"name": "OnlyBehavior", "description": "d", "active": False},
            ],
            topics=[
                {"name": "T", "description": "d", "active": True},
            ],
            categories=[
                {"name": "C", "description": "d", "active": True},
            ],
        )

        async def _empty_stream(**kwargs):
            return
            yield  # noqa: RET503

        with (
            patch(
                "rhesis.backend.app.services.test_generation_pipeline._resolve_config_llm",
                return_value=llm,
            ),
            patch(
                "rhesis.backend.app.services.test_generation_pipeline._fetch_db_context",
                return_value=_db_context(),
            ),
            patch(
                "rhesis.backend.app.services.test_generation_pipeline.generate_tests_stream",
                side_effect=_empty_stream,
            ) as mock_gen,
        ):
            await _collect_ndjson(
                test_generation_pipeline_stream(
                    db=mock_db,
                    user=user,
                    prompt="test",
                    organization_id=str(uuid.uuid4()),
                )
            )

        call_kwargs = mock_gen.call_args
        sdk_config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        assert sdk_config.behaviors == ["OnlyBehavior"]

    async def test_skips_config_when_provided(self):
        """When config is provided, Phase 1 is skipped entirely."""
        user = _make_user()
        mock_db = MagicMock()

        config = TestConfigResponse(
            behaviors=[{"name": "B1", "description": "d", "active": True}],
            topics=[{"name": "T1", "description": "d", "active": True}],
            categories=[{"name": "C1", "description": "d", "active": True}],
        )

        async def _fake_stream(**kwargs):
            yield {"prompt": {"content": "test1"}, "behavior": "B1"}

        with patch(
            "rhesis.backend.app.services.test_generation_pipeline.generate_tests_stream",
            side_effect=_fake_stream,
        ):
            events = await _collect_ndjson(
                test_generation_pipeline_stream(
                    db=mock_db,
                    user=user,
                    prompt="test",
                    organization_id=str(uuid.uuid4()),
                    config=config,
                )
            )

        types = [e["type"] for e in events]
        assert "config_item" not in types
        assert "config_done" not in types
        assert "test" in types
        assert types[-1] == "done"
