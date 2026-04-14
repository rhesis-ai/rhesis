"""Unit tests for Celery trace metrics evaluation tasks.

These tests mock ``SessionLocal`` and do not require a migrated database.
If Alembic session setup fails locally (e.g. multiple heads), run with::

    RHESIS_SKIP_MIGRATIONS=1 uv run pytest ../../tests/backend/tasks/test_trace_metrics_evaluation.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from celery.exceptions import Retry
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.schemas.metric import MetricScope
from rhesis.backend.tasks.telemetry.evaluate import (
    CONVERSATION_INPUT_KEY,
    CONVERSATION_OUTPUT_KEY,
    _get_trace_metrics_config,
    _schedule_debounced_conversation_eval,
    evaluate_conversation_trace_metrics,
    evaluate_turn_trace_metrics,
)

TRACE_ID = "trace-uuid-1"
PROJECT_ID = "project-uuid-1"
ORG_ID = "org-uuid-1"
SPAN_DB_ID = "span-db-id-1"


def _mock_project(trace_metrics_config: dict | None = None) -> MagicMock:
    project = MagicMock()
    project.attributes = {"trace_metrics": trace_metrics_config or {"enabled": True}}
    return project


def _mock_root_span(
    *,
    conversation_id=None,
    attributes: dict | None = None,
    span_db_id: str = SPAN_DB_ID,
    trace_metrics: dict | None = None,
    trace_metrics_processed_at=None,
) -> MagicMock:
    span = MagicMock(spec=models.Trace)
    span.id = span_db_id
    span.trace_id = TRACE_ID
    span.span_id = "otel-span-1"
    span.parent_span_id = None
    span.conversation_id = conversation_id
    span.attributes = attributes or {
        CONVERSATION_INPUT_KEY: "user says hi",
        CONVERSATION_OUTPUT_KEY: "assistant replies",
    }
    span.trace_metrics = trace_metrics or {}
    span.trace_metrics_processed_at = trace_metrics_processed_at
    return span


def _db_mock_turn(project, root_span, status_row) -> MagicMock:
    """Query order: Project, Trace (root), Status."""

    def query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        if model is models.Project:
            q.first.return_value = project
        elif model is models.Trace:
            q.first.return_value = root_span
        elif model is models.Status:
            q.first.return_value = status_row
        return q

    db = MagicMock(spec=Session)
    db.query.side_effect = query_fn
    return db


def _db_mock_conversation(project, root_spans: list, status_row) -> MagicMock:
    """Query order: Project, Trace (roots .all()), Status."""

    def query_fn(model):
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        if model is models.Project:
            q.first.return_value = project
        elif model is models.Trace:
            q.all.return_value = root_spans
            q.first.return_value = root_spans[0] if root_spans else None
        elif model is models.Status:
            q.first.return_value = status_row
        return q

    db = MagicMock(spec=Session)
    db.query.side_effect = query_fn
    return db


def _mock_status_row(sid: str = "status-row-id") -> MagicMock:
    row = MagicMock()
    row.id = sid
    return row


def _mock_metric_model(name: str = "m1") -> MagicMock:
    m = MagicMock(spec=models.Metric)
    m.id = f"{name}-id"
    m.name = name
    m.class_name = "DummyMetric"
    m.backend_type = MagicMock()
    m.backend_type.name = "rhesis"
    m.score_type = "numeric"
    m.threshold = 0.5
    m.threshold_operator = "gte"
    m.evaluation_prompt = "prompt"
    m.evaluation_steps = None
    m.reasoning = None
    m.description = None
    m.metric_scope = [MetricScope.TRACE.value, MetricScope.SINGLE_TURN.value]
    m.min_score = 0.0
    m.max_score = 1.0
    m.categories = None
    m.passing_categories = None
    m.ground_truth_required = False
    m.context_required = False
    return m


@pytest.mark.unit
class TestGetTraceMetricsConfig:
    """Tests for _get_trace_metrics_config normalising different storage formats."""

    def test_dict_config_returned_as_is(self):
        project = _mock_project({"enabled": True, "sampling_rate": 0.5})
        config = _get_trace_metrics_config(project)
        assert config == {"enabled": True, "sampling_rate": 0.5}

    def test_list_of_metric_ids_normalised_to_dict(self):
        project = MagicMock()
        project.attributes = {"trace_metrics": ["id-1", "id-2"]}
        config = _get_trace_metrics_config(project)
        assert config == {"metric_ids": ["id-1", "id-2"]}

    def test_missing_trace_metrics_returns_empty_dict(self):
        project = MagicMock()
        project.attributes = {}
        config = _get_trace_metrics_config(project)
        assert config == {}

    def test_none_attributes_returns_empty_dict(self):
        project = MagicMock()
        project.attributes = None
        config = _get_trace_metrics_config(project)
        assert config == {}


@pytest.mark.unit
class TestEvaluateTurnTraceMetrics:
    def test_single_turn_no_conversation_id(self):
        project = _mock_project()
        root = _mock_root_span(conversation_id=None)
        status = _mock_status_row("pass-status-id")
        db = _db_mock_turn(project, root, status)
        mock_metric = _mock_metric_model()

        eval_results = {"m1": {"is_successful": True, "score": 1.0}}

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
                return_value=[mock_metric],
            ) as mock_load,
            patch("rhesis.backend.tasks.telemetry.evaluate.crud") as mock_crud,
            patch(
                "rhesis.backend.metrics.evaluator.MetricEvaluator",
            ) as mock_eval_cls,
        ):
            mock_eval_cls.return_value.evaluate.return_value = eval_results
            out = evaluate_turn_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        assert out["status"] == "success"
        assert out["trace_id"] == TRACE_ID
        mock_load.assert_called_once()
        assert mock_load.call_args.kwargs.get("phase") == "all"
        assert mock_load.call_args.args[0] is db
        assert mock_load.call_args.args[1] == ORG_ID
        mock_crud.update_trace_turn_metrics.assert_called_once()
        utm = mock_crud.update_trace_turn_metrics.call_args.kwargs
        assert utm["span_id"] == str(root.id)
        assert "metrics" in utm["turn_metrics"]
        assert utm["turn_metrics"]["metrics"] == eval_results
        db.close.assert_called_once()

    def test_trace_metrics_as_list_of_ids(self):
        """Reproduce the production bug: trace_metrics stored as a plain list of IDs."""
        project = MagicMock()
        project.attributes = {"trace_metrics": ["metric-id-1", "metric-id-2"]}
        project.owner = None
        project.user = None
        root = _mock_root_span(conversation_id=None)
        status = _mock_status_row("pass-status-id")
        db = _db_mock_turn(project, root, status)
        mock_metric = _mock_metric_model()

        eval_results = {"m1": {"is_successful": True, "score": 1.0}}

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
                return_value=[mock_metric],
            ) as mock_load,
            patch("rhesis.backend.tasks.telemetry.evaluate.crud") as mock_crud,
            patch(
                "rhesis.backend.metrics.evaluator.MetricEvaluator",
            ) as mock_eval_cls,
        ):
            mock_eval_cls.return_value.evaluate.return_value = eval_results
            out = evaluate_turn_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        assert out["status"] == "success"
        mock_load.assert_called_once()
        config_arg = mock_load.call_args.args[2]
        assert config_arg == {"metric_ids": ["metric-id-1", "metric-id-2"]}

    def test_multi_turn_with_conversation_id(self):
        project = _mock_project()
        root = _mock_root_span(conversation_id="conv-1")
        status = _mock_status_row()
        db = _db_mock_turn(project, root, status)
        mock_metric = _mock_metric_model()

        eval_results = {"m1": {"is_successful": True}}

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
                return_value=[mock_metric],
            ) as mock_load,
            patch("rhesis.backend.tasks.telemetry.evaluate.crud"),
            patch(
                "rhesis.backend.metrics.evaluator.MetricEvaluator",
            ) as mock_eval_cls,
            patch(
                "rhesis.backend.app.services.telemetry.trace_metrics_cache."
                "schedule_conversation_eval",
            ) as mock_schedule,
        ):
            mock_eval_cls.return_value.evaluate.return_value = eval_results
            evaluate_turn_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        mock_load.assert_called_once()
        assert mock_load.call_args.kwargs["phase"] == "turn"
        mock_schedule.assert_called_once_with(TRACE_ID, PROJECT_ID, ORG_ID)

    def test_project_disabled(self):
        project = _mock_project({"enabled": False})
        db = _db_mock_turn(project, None, None)

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
            ) as mock_load,
        ):
            out = evaluate_turn_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        assert out == {"status": "skipped", "trace_id": TRACE_ID}
        mock_load.assert_not_called()

    def test_sampling_rate_zero(self):
        project = _mock_project({"enabled": True, "sampling_rate": 0.0})
        db = _db_mock_turn(project, None, None)

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
            ) as mock_load,
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.random.random",
                return_value=1.0,
            ),
        ):
            out = evaluate_turn_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        assert out == {"status": "skipped", "trace_id": TRACE_ID}
        mock_load.assert_not_called()

    def test_no_root_span(self):
        project = _mock_project()
        db = _db_mock_turn(project, root_span=None, status_row=None)

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
        ):
            out = evaluate_turn_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        assert out == {"status": "no_root_span", "trace_id": TRACE_ID}

    def test_no_io_attributes(self):
        project = _mock_project()
        root = _mock_root_span(
            conversation_id=None,
            attributes={CONVERSATION_INPUT_KEY: "", CONVERSATION_OUTPUT_KEY: ""},
        )
        db = _db_mock_turn(project, root, None)

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
        ):
            out = evaluate_turn_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        assert out == {"status": "no_io", "trace_id": TRACE_ID}

    def test_non_retryable_exception_propagates(self):
        """Programming errors (RuntimeError, TypeError, etc.) should propagate immediately."""
        project = _mock_project()
        root = _mock_root_span()
        db = _db_mock_turn(project, root, _mock_status_row())
        mock_metric = _mock_metric_model()

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
                return_value=[mock_metric],
            ),
            patch(
                "rhesis.backend.metrics.evaluator.MetricEvaluator",
            ) as mock_eval_cls,
        ):
            mock_eval_cls.return_value.evaluate.side_effect = RuntimeError("eval boom")
            with pytest.raises(RuntimeError, match="eval boom"):
                evaluate_turn_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        db.close.assert_called_once()

    def test_transient_exception_retries(self):
        """Transient errors (IOError, ConnectionError) should trigger retry."""
        project = _mock_project()
        root = _mock_root_span()
        db = _db_mock_turn(project, root, _mock_status_row())
        mock_metric = _mock_metric_model()

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
                return_value=[mock_metric],
            ),
            patch(
                "rhesis.backend.metrics.evaluator.MetricEvaluator",
            ) as mock_eval_cls,
            patch.object(
                evaluate_turn_trace_metrics,
                "retry",
                side_effect=lambda exc=None: (_ for _ in ()).throw(Retry("retry")),
            ) as mock_retry,
        ):
            mock_eval_cls.return_value.evaluate.side_effect = ConnectionError("db gone")
            with pytest.raises(Retry):
                evaluate_turn_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        mock_retry.assert_called_once()
        db.close.assert_called_once()

    def test_status_derivation_pass(self):
        project = _mock_project()
        root = _mock_root_span()
        status = _mock_status_row("derived-pass-id")
        db = _db_mock_turn(project, root, status)
        mock_metric = _mock_metric_model()

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
                return_value=[mock_metric],
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.crud") as mock_crud,
            patch(
                "rhesis.backend.metrics.evaluator.MetricEvaluator",
            ) as mock_eval_cls,
        ):
            mock_eval_cls.return_value.evaluate.return_value = {
                "metrics": {
                    "a": {"is_successful": True},
                    "b": {"is_successful": True},
                },
            }
            evaluate_turn_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        passed_status_id = mock_crud.update_trace_turn_metrics.call_args.kwargs[
            "status_id"
        ]
        assert passed_status_id == "derived-pass-id"

    def test_status_derivation_fail(self):
        project = _mock_project()
        root = _mock_root_span()
        status = _mock_status_row("derived-fail-id")
        db = _db_mock_turn(project, root, status)
        mock_metric = _mock_metric_model()

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
                return_value=[mock_metric],
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.crud") as mock_crud,
            patch(
                "rhesis.backend.metrics.evaluator.MetricEvaluator",
            ) as mock_eval_cls,
        ):
            mock_eval_cls.return_value.evaluate.return_value = {
                "metrics": {
                    "a": {"is_successful": True},
                    "b": {"is_successful": False},
                },
            }
            evaluate_turn_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        passed_status_id = mock_crud.update_trace_turn_metrics.call_args.kwargs[
            "status_id"
        ]
        assert passed_status_id == "derived-fail-id"


@pytest.mark.unit
class TestEvaluateTurnWithRootSpanId:
    """Tests for the root_span_id parameter that fixes multi-turn race conditions."""

    def test_root_span_id_queries_by_id(self):
        """When root_span_id is provided, the task queries by DB primary key."""
        project = _mock_project()
        root = _mock_root_span(conversation_id="conv-1")
        status = _mock_status_row()
        db = _db_mock_turn(project, root, status)
        mock_metric = _mock_metric_model()
        eval_results = {"m1": {"is_successful": True}}

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
                return_value=[mock_metric],
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.crud") as mock_crud,
            patch(
                "rhesis.backend.metrics.evaluator.MetricEvaluator",
            ) as mock_eval_cls,
            patch(
                "rhesis.backend.app.services.telemetry.trace_metrics_cache."
                "schedule_conversation_eval",
            ),
        ):
            mock_eval_cls.return_value.evaluate.return_value = eval_results
            out = evaluate_turn_trace_metrics.run(
                TRACE_ID, PROJECT_ID, ORG_ID, root_span_id=SPAN_DB_ID,
            )

        assert out["status"] == "success"
        mock_crud.update_trace_turn_metrics.assert_called_once()
        utm = mock_crud.update_trace_turn_metrics.call_args.kwargs
        assert utm["span_id"] == str(root.id)

    def test_root_span_id_none_falls_back(self):
        """When root_span_id is None, the legacy latest-root-span query is used."""
        project = _mock_project()
        root = _mock_root_span(conversation_id=None)
        status = _mock_status_row()
        db = _db_mock_turn(project, root, status)
        mock_metric = _mock_metric_model()
        eval_results = {"m1": {"is_successful": True}}

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
                return_value=[mock_metric],
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.crud") as mock_crud,
            patch(
                "rhesis.backend.metrics.evaluator.MetricEvaluator",
            ) as mock_eval_cls,
        ):
            mock_eval_cls.return_value.evaluate.return_value = eval_results
            out = evaluate_turn_trace_metrics.run(
                TRACE_ID, PROJECT_ID, ORG_ID, root_span_id=None,
            )

        assert out["status"] == "success"
        mock_crud.update_trace_turn_metrics.assert_called_once()

    def test_root_span_id_not_found(self):
        """When root_span_id refers to a non-existent span, returns no_root_span."""
        project = _mock_project()
        db = _db_mock_turn(project, root_span=None, status_row=None)

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
        ):
            out = evaluate_turn_trace_metrics.run(
                TRACE_ID, PROJECT_ID, ORG_ID, root_span_id="nonexistent-id",
            )

        assert out == {"status": "no_root_span", "trace_id": TRACE_ID}


@pytest.mark.unit
class TestEvaluateConversationTraceMetrics:
    def test_multi_turn_evaluation(self):
        project = _mock_project()
        span1 = _mock_root_span(
            span_db_id="s1",
            attributes={
                CONVERSATION_INPUT_KEY: "u1",
                CONVERSATION_OUTPUT_KEY: "a1",
            },
        )
        span2 = _mock_root_span(
            span_db_id="s2",
            attributes={
                CONVERSATION_INPUT_KEY: "u2",
                CONVERSATION_OUTPUT_KEY: "a2",
            },
        )
        span1.trace_metrics = {}
        span2.trace_metrics = {}
        status = _mock_status_row("conv-status-id")
        db = _db_mock_conversation(project, [span1, span2], status)
        mock_metric = _mock_metric_model("multi")
        mock_metric.metric_scope = [MetricScope.TRACE.value, MetricScope.MULTI_TURN.value]

        eval_results = {"multi": {"is_successful": True}}

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
                return_value=[mock_metric],
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.crud") as mock_crud,
            patch(
                "rhesis.backend.metrics.evaluator.MetricEvaluator",
            ) as mock_eval_cls,
            patch(
                "rhesis.sdk.metrics.conversational.types.ConversationHistory",
            ) as mock_ch,
        ):
            conv_instance = MagicMock()
            conv_instance.format_conversation.return_value = "formatted thread"
            mock_ch.from_messages.return_value = conv_instance
            mock_eval_cls.return_value.evaluate.return_value = eval_results
            out = evaluate_conversation_trace_metrics.run(
                TRACE_ID, PROJECT_ID, ORG_ID,
            )

        assert out["status"] == "success"
        assert out["trace_id"] == TRACE_ID
        expected_messages = [
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
        ]
        mock_ch.from_messages.assert_called_once_with(expected_messages)
        mock_crud.update_trace_conversation_metrics.assert_called_once()
        ucm = mock_crud.update_trace_conversation_metrics.call_args.kwargs
        assert ucm["trace_id"] == TRACE_ID
        assert ucm["conversation_metrics"]["metrics"] == eval_results
        eval_kwargs = mock_eval_cls.return_value.evaluate.call_args.kwargs
        assert eval_kwargs["conversation_history"] is conv_instance
        assert eval_kwargs["output_text"] == "formatted thread".strip()
        db.close.assert_called_once()

    def test_no_multi_turn_metrics(self):
        project = _mock_project()
        db = _db_mock_conversation(project, [], None)

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
                return_value=[],
            ),
        ):
            out = evaluate_conversation_trace_metrics.run(
                TRACE_ID, PROJECT_ID, ORG_ID,
            )

        assert out == {"status": "no_metrics", "trace_id": TRACE_ID}

    def test_project_disabled(self):
        project = _mock_project({"enabled": False})
        db = _db_mock_conversation(project, [], None)

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
            ) as mock_load,
        ):
            out = evaluate_conversation_trace_metrics.run(
                TRACE_ID, PROJECT_ID, ORG_ID,
            )

        assert out == {"status": "skipped", "trace_id": TRACE_ID}
        mock_load.assert_not_called()

    def test_non_retryable_exception_propagates(self):
        """Programming errors should propagate, not retry."""
        project = _mock_project()
        span1 = _mock_root_span(
            attributes={
                CONVERSATION_INPUT_KEY: "u",
                CONVERSATION_OUTPUT_KEY: "a",
            },
        )
        span1.trace_metrics = {}
        db = _db_mock_conversation(project, [span1], _mock_status_row())
        mock_metric = _mock_metric_model()
        mock_metric.metric_scope = [MetricScope.TRACE.value, MetricScope.MULTI_TURN.value]

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
                return_value=[mock_metric],
            ),
            patch(
                "rhesis.backend.metrics.evaluator.MetricEvaluator",
            ) as mock_eval_cls,
            patch(
                "rhesis.sdk.metrics.conversational.types.ConversationHistory",
            ) as mock_ch,
        ):
            conv_instance = MagicMock()
            conv_instance.format_conversation.return_value = "x"
            mock_ch.from_messages.return_value = conv_instance
            mock_eval_cls.return_value.evaluate.side_effect = RuntimeError("conv eval")

            with pytest.raises(RuntimeError, match="conv eval"):
                evaluate_conversation_trace_metrics.run(
                    TRACE_ID, PROJECT_ID, ORG_ID,
                )

        db.close.assert_called_once()

    def test_transient_exception_retries(self):
        """Transient errors should trigger retry."""
        project = _mock_project()
        span1 = _mock_root_span(
            attributes={
                CONVERSATION_INPUT_KEY: "u",
                CONVERSATION_OUTPUT_KEY: "a",
            },
        )
        span1.trace_metrics = {}
        db = _db_mock_conversation(project, [span1], _mock_status_row())
        mock_metric = _mock_metric_model()
        mock_metric.metric_scope = [MetricScope.TRACE.value, MetricScope.MULTI_TURN.value]

        with (
            patch(
                "rhesis.backend.tasks.telemetry.evaluate.SessionLocal",
                return_value=db,
            ),
            patch("rhesis.backend.tasks.telemetry.evaluate.set_session_variables"),
            patch(
                "rhesis.backend.tasks.telemetry.evaluate._load_trace_scoped_metrics",
                return_value=[mock_metric],
            ),
            patch(
                "rhesis.backend.metrics.evaluator.MetricEvaluator",
            ) as mock_eval_cls,
            patch(
                "rhesis.sdk.metrics.conversational.types.ConversationHistory",
            ) as mock_ch,
            patch.object(
                evaluate_conversation_trace_metrics,
                "retry",
                side_effect=lambda exc=None: (_ for _ in ()).throw(Retry("retry")),
            ) as mock_retry,
        ):
            conv_instance = MagicMock()
            conv_instance.format_conversation.return_value = "x"
            mock_ch.from_messages.return_value = conv_instance
            mock_eval_cls.return_value.evaluate.side_effect = IOError("network gone")

            with pytest.raises(Retry):
                evaluate_conversation_trace_metrics.run(
                    TRACE_ID, PROJECT_ID, ORG_ID,
                )

        mock_retry.assert_called_once()
        db.close.assert_called_once()


@pytest.mark.unit
class TestScheduleDebounceSkipsWhenComplete:
    """_schedule_debounced_conversation_eval skips when conversation is complete."""

    def test_skips_when_conversation_complete(self):
        with (
            patch(
                "rhesis.backend.app.services.telemetry.trace_metrics_cache."
                "is_conversation_complete",
                return_value=True,
            ) as mock_complete,
            patch(
                "rhesis.backend.app.services.telemetry.trace_metrics_cache."
                "schedule_conversation_eval",
            ) as mock_schedule,
        ):
            _schedule_debounced_conversation_eval(TRACE_ID, PROJECT_ID, ORG_ID)

        mock_complete.assert_called_once_with(TRACE_ID)
        mock_schedule.assert_not_called()

    def test_schedules_when_not_complete(self):
        with (
            patch(
                "rhesis.backend.app.services.telemetry.trace_metrics_cache."
                "is_conversation_complete",
                return_value=False,
            ) as mock_complete,
            patch(
                "rhesis.backend.app.services.telemetry.trace_metrics_cache."
                "schedule_conversation_eval",
            ) as mock_schedule,
        ):
            _schedule_debounced_conversation_eval(TRACE_ID, PROJECT_ID, ORG_ID)

        mock_complete.assert_called_once_with(TRACE_ID)
        mock_schedule.assert_called_once_with(TRACE_ID, PROJECT_ID, ORG_ID)
