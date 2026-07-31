import json
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.services.explorer import (
    evaluate_suggestions_stream,
    invoke_endpoint_for_suggestions_stream,
    suggestion_pipeline_stream,
)

# Resolved at call time inside EndpointInvoker, so the source modules are the patch targets.
_DB_CTX_PATCH = "rhesis.backend.app.database.get_db_with_tenant_variables"
_SVC_PATCH = "rhesis.backend.app.dependencies.get_endpoint_service"

# Imported by name into suggestions.py, so patched there rather than at their source module.
_RESOLVE_METRICS_PATCH = "rhesis.backend.app.services.explorer.suggestions._resolve_sdk_metrics"
_RUN_METRICS_PATCH = "rhesis.backend.app.services.explorer.suggestions._run_metrics_on_text"
_GENERATE_SUGGESTIONS_PATCH = (
    "rhesis.backend.app.services.explorer.suggestions.generate_suggestions"
)
_INVOKER_PATCH = "rhesis.backend.app.services.explorer.suggestions.EndpointInvoker"

# Function-body imports inside suggestion_pipeline_stream, so patched at their source module.
_RESOLVE_EMBEDDER_PATCH = "rhesis.backend.app.services.explorer.embeddings.resolve_embedder"
_EMBED_ONE_PATCH = "rhesis.backend.app.services.explorer.embeddings.a_generate_embedding_vector"


def _mock_db_context(test_db):
    @contextmanager
    def _ctx(*_args, **_kwargs):
        yield test_db

    return _ctx


class _Suggestion:
    """Stand-in for the Pydantic suggestion objects the router passes in."""

    def __init__(self, input_text):
        self.input = input_text


async def _collect(stream):
    """Drain an NDJSON byte stream into a list of decoded events."""
    events = []
    async for chunk in stream:
        for line in chunk.decode("utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events


@pytest.mark.integration
@pytest.mark.service
@pytest.mark.asyncio
class TestInvokeEndpointForSuggestionsStream:
    """Test the NDJSON stream that generates outputs for non-persisted suggestions."""

    async def test_emits_one_item_per_suggestion_then_summary(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """Every suggestion gets an item event, followed by a single summary."""
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "an answer"})
        suggestions = [_Suggestion("first"), _Suggestion("second"), _Suggestion("third")]

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            events = await _collect(
                invoke_endpoint_for_suggestions_stream(
                    db=test_db,
                    endpoint_id=str(uuid.uuid4()),
                    suggestions=suggestions,
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                )
            )

        items = [e for e in events if e["type"] == "item"]
        summary = [e for e in events if e["type"] == "summary"]

        assert len(items) == 3
        assert len(summary) == 1
        assert summary[0] == {"type": "summary", "generated": 3, "total": 3}
        assert events[-1]["type"] == "summary"

        # Items arrive in completion order, so identify them by index.
        assert {i["index"] for i in items} == {0, 1, 2}
        by_index = {i["index"]: i for i in items}
        assert by_index[0]["input"] == "first"
        assert by_index[2]["input"] == "third"
        assert all(i["output"] == "an answer" and i["error"] is None for i in items)

    async def test_failures_are_reported_per_item_and_excluded_from_generated(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """A failing invocation yields an item with an error and does not count as generated."""

        async def _invoke(**kwargs):
            if kwargs["input_data"]["input"] == "bad":
                raise RuntimeError("endpoint exploded")
            return {"output": "fine"}

        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(side_effect=_invoke)

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            events = await _collect(
                invoke_endpoint_for_suggestions_stream(
                    db=test_db,
                    endpoint_id=str(uuid.uuid4()),
                    suggestions=[_Suggestion("good"), _Suggestion("bad")],
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                )
            )

        by_index = {e["index"]: e for e in events if e["type"] == "item"}
        summary = next(e for e in events if e["type"] == "summary")

        assert by_index[0]["output"] == "fine"
        assert by_index[0]["error"] is None
        assert by_index[1]["output"] == ""
        assert by_index[1]["error"] == "endpoint exploded"
        assert summary == {"type": "summary", "generated": 1, "total": 2}

    async def test_empty_suggestions_emits_only_summary(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """No suggestions means no item events, and a zero summary."""
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "unused"})

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            events = await _collect(
                invoke_endpoint_for_suggestions_stream(
                    db=test_db,
                    endpoint_id=str(uuid.uuid4()),
                    suggestions=[],
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                )
            )

        assert events == [{"type": "summary", "generated": 0, "total": 0}]
        mock_svc.invoke_endpoint.assert_not_awaited()

    async def test_every_invocation_gets_its_own_tenant_scoped_session(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """Each suggestion is invoked on a session opened with the caller's tenant identity."""
        calls = []

        @contextmanager
        def _recording_ctx(*args, **kwargs):
            calls.append(args)
            yield test_db

        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "ok"})

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _recording_ctx),
        ):
            await _collect(
                invoke_endpoint_for_suggestions_stream(
                    db=test_db,
                    endpoint_id=str(uuid.uuid4()),
                    suggestions=[_Suggestion("a"), _Suggestion("b")],
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                )
            )

        assert len(calls) == 2
        for args in calls:
            assert args == (test_org_id, authenticated_user_id, "")


@pytest.mark.integration
@pytest.mark.service
@pytest.mark.asyncio
class TestEvaluateSuggestionsStream:
    """Test the NDJSON stream that evaluates non-persisted suggestion outputs."""

    async def test_emits_one_item_per_suggestion_then_summary(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """Every suggestion gets an item event, followed by a single summary."""
        run_metrics = AsyncMock(return_value={"Correctness": {"score": 1.0, "is_successful": True}})

        with (
            patch(_RESOLVE_METRICS_PATCH, return_value=[]),
            patch(_RUN_METRICS_PATCH, new=run_metrics),
        ):
            events = await _collect(
                evaluate_suggestions_stream(
                    db=test_db,
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                    metric_names=["Correctness"],
                    suggestions=[
                        {"input": "first", "output": "answer one"},
                        {"input": "second", "output": "answer two"},
                    ],
                )
            )

        items = [e for e in events if e["type"] == "item"]
        summary = [e for e in events if e["type"] == "summary"]

        assert len(items) == 2
        assert summary == [{"type": "summary", "evaluated": 2, "total": 2}]
        assert events[-1]["type"] == "summary"
        assert {i["index"] for i in items} == {0, 1}
        assert all(i["label"] == "pass" and i["error"] is None for i in items)

    async def test_missing_output_is_unlabeled_and_excluded_from_evaluated(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """A suggestion with no output yet is reported as unlabeled, not evaluated."""
        with (
            patch(_RESOLVE_METRICS_PATCH, return_value=[]),
            patch(_RUN_METRICS_PATCH, new=AsyncMock()),
        ):
            events = await _collect(
                evaluate_suggestions_stream(
                    db=test_db,
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                    metric_names=["Correctness"],
                    suggestions=[{"input": "no output yet", "output": ""}],
                )
            )

        item = next(e for e in events if e["type"] == "item")
        summary = next(e for e in events if e["type"] == "summary")

        assert item["label"] == ""
        assert item["error"] == "no output to evaluate"
        assert summary == {"type": "summary", "evaluated": 0, "total": 1}

    async def test_metric_failure_reported_as_error_item(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """A metric run that raises is reported as an error item, not a crash."""
        with (
            patch(_RESOLVE_METRICS_PATCH, return_value=[]),
            patch(_RUN_METRICS_PATCH, new=AsyncMock(side_effect=RuntimeError("metric exploded"))),
        ):
            events = await _collect(
                evaluate_suggestions_stream(
                    db=test_db,
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                    metric_names=["Correctness"],
                    suggestions=[{"input": "in", "output": "out"}],
                )
            )

        item = next(e for e in events if e["type"] == "item")
        summary = next(e for e in events if e["type"] == "summary")

        assert item["label"] == "error"
        assert item["error"] == "metric exploded"
        assert summary == {"type": "summary", "evaluated": 0, "total": 1}

    async def test_empty_suggestions_emits_only_summary(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """No suggestions means no item events, and a zero summary."""
        with (
            patch(_RESOLVE_METRICS_PATCH, return_value=[]),
            patch(_RUN_METRICS_PATCH, new=AsyncMock()),
        ):
            events = await _collect(
                evaluate_suggestions_stream(
                    db=test_db,
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                    metric_names=["Correctness"],
                    suggestions=[],
                )
            )

        assert events == [{"type": "summary", "evaluated": 0, "total": 0}]


async def _fake_suggestion_stream(items):
    """Stand-in for generate_suggestions(..., stream=True)'s async generator."""
    yield {"type": "meta", "num_examples_used": len(items)}
    for topic, text in items:
        yield {"type": "item", "topic": topic, "input": text}


@pytest.mark.integration
@pytest.mark.service
@pytest.mark.asyncio
class TestSuggestionPipelineStream:
    """Test the unified generate → embed → invoke → evaluate NDJSON stream."""

    async def test_pipelines_generation_output_and_evaluation(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """Each suggestion gets a matching output and evaluation, ending in the summaries."""
        mock_invoker = MagicMock()
        mock_invoker.invoke = AsyncMock(return_value=("an answer", None))
        run_metrics = AsyncMock(return_value={"Correctness": {"score": 1.0, "is_successful": True}})

        with (
            patch(
                _GENERATE_SUGGESTIONS_PATCH,
                new=AsyncMock(
                    return_value=_fake_suggestion_stream([("", "first"), ("", "second")])
                ),
            ),
            patch(_INVOKER_PATCH, return_value=mock_invoker),
            patch(_RESOLVE_METRICS_PATCH, return_value=[]),
            patch(_RUN_METRICS_PATCH, new=run_metrics),
        ):
            events = await _collect(
                suggestion_pipeline_stream(
                    db=test_db,
                    test_set_identifier="some-test-set",
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                    endpoint_id=str(uuid.uuid4()),
                    metric_names=["Correctness"],
                    num_suggestions=2,
                )
            )

        by_type = {}
        for e in events:
            by_type.setdefault(e["type"], []).append(e)

        assert {e["index"] for e in by_type["suggestion"]} == {0, 1}
        assert {e["index"] for e in by_type["output"]} == {0, 1}
        assert {e["index"] for e in by_type["evaluation"]} == {0, 1}
        assert all(e["label"] == "pass" for e in by_type["evaluation"])
        assert by_type["suggestions_done"] == [
            {
                "type": "suggestions_done",
                "total": 2,
                "num_examples_used": 2,
                "diversity_order": None,
                "diversity_scores": None,
            }
        ]
        assert by_type["output_summary"] == [{"type": "output_summary", "generated": 2, "total": 2}]
        assert by_type["eval_summary"] == [{"type": "eval_summary", "evaluated": 2, "total": 2}]
        assert events[-1]["type"] == "done"

    async def test_output_failure_skips_evaluation_for_that_item(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """An endpoint failure produces an output error event and no evaluation event."""
        mock_invoker = MagicMock()
        mock_invoker.invoke = AsyncMock(return_value=("", "endpoint exploded"))

        with (
            patch(
                _GENERATE_SUGGESTIONS_PATCH,
                new=AsyncMock(return_value=_fake_suggestion_stream([("", "only")])),
            ),
            patch(_INVOKER_PATCH, return_value=mock_invoker),
            patch(_RESOLVE_METRICS_PATCH, return_value=[]),
            patch(_RUN_METRICS_PATCH, new=AsyncMock()),
        ):
            events = await _collect(
                suggestion_pipeline_stream(
                    db=test_db,
                    test_set_identifier="some-test-set",
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                    endpoint_id=str(uuid.uuid4()),
                    metric_names=["Correctness"],
                    num_suggestions=1,
                )
            )

        output_events = [e for e in events if e["type"] == "output"]
        assert output_events == [
            {
                "type": "output",
                "index": 0,
                "input": "only",
                "output": "",
                "error": "endpoint exploded",
            }
        ]
        assert not any(e["type"] == "evaluation" for e in events)
        output_summary = next(e for e in events if e["type"] == "output_summary")
        eval_summary = next(e for e in events if e["type"] == "eval_summary")
        assert output_summary == {"type": "output_summary", "generated": 0, "total": 1}
        assert eval_summary == {"type": "eval_summary", "evaluated": 0, "total": 0}

    async def test_generate_embeddings_produces_diversity_order(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """With generate_embeddings=True, suggestions_done carries a real diversity ordering."""
        mock_invoker = MagicMock()
        mock_invoker.invoke = AsyncMock(return_value=("an answer", None))
        run_metrics = AsyncMock(return_value={"Correctness": {"score": 1.0, "is_successful": True}})

        vectors = {"first": [1.0, 0.0], "second": [0.0, 1.0]}

        async def _fake_embed(text, db, user_id, embedder=None):
            return vectors[text]

        with (
            patch(
                _GENERATE_SUGGESTIONS_PATCH,
                new=AsyncMock(
                    return_value=_fake_suggestion_stream([("", "first"), ("", "second")])
                ),
            ),
            patch(_INVOKER_PATCH, return_value=mock_invoker),
            patch(_RESOLVE_METRICS_PATCH, return_value=[]),
            patch(_RUN_METRICS_PATCH, new=run_metrics),
            patch(_RESOLVE_EMBEDDER_PATCH, return_value=MagicMock()),
            patch(_EMBED_ONE_PATCH, new=AsyncMock(side_effect=_fake_embed)),
        ):
            events = await _collect(
                suggestion_pipeline_stream(
                    db=test_db,
                    test_set_identifier="some-test-set",
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                    endpoint_id=str(uuid.uuid4()),
                    metric_names=["Correctness"],
                    num_suggestions=2,
                    generate_embeddings=True,
                )
            )

        done = next(e for e in events if e["type"] == "suggestions_done")
        assert done["total"] == 2
        assert sorted(done["diversity_order"]) == [0, 1]
        assert len(done["diversity_scores"]) == 2
        assert all(score is not None for score in done["diversity_scores"])
