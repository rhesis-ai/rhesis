"""A trace not evaluated because of the model token limit is marked Skipped."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.constants import TRACE_SKIPPED_STATUS, EntityType
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.quota.enforcement import QuotaExceededError, QuotaVerdict
from rhesis.backend.jobs.telemetry import evaluate
from rhesis.backend.jobs.telemetry.evaluate import (
    CONVERSATION_INPUT_KEY,
    evaluate_conversation_trace_metrics,
    evaluate_turn_trace_metrics,
)

EVALUATE = "rhesis.backend.jobs.telemetry.evaluate"
TRACE_ID, PROJECT_ID, ORG_ID = "trace-1", str(uuid4()), str(uuid4())


def _exceeded() -> QuotaExceededError:
    return QuotaExceededError(
        QuotaVerdict(
            resource=QuotaResource.MODEL_TOKENS,
            used=10,
            limit=10,
            allowed=False,
            over_limit=True,
            kind="flow",
            period_end=None,
        )
    )


def _span(status_id=None, conversation_id=None):
    span = MagicMock()
    span.trace_metrics = None
    span.trace_metrics_processed_at = None
    span.trace_metrics_status_id = status_id
    span.attributes = {CONVERSATION_INPUT_KEY: "hello"}
    span.conversation_id = conversation_id
    return span


@pytest.fixture
def at_the_limit():
    """Evaluation is on, the phase has a metric, and building the evaluator hits the limit."""
    status = MagicMock(id="skipped-status")
    with (
        patch(f"{EVALUATE}.SessionLocal", return_value=MagicMock(spec=Session)),
        patch(f"{EVALUATE}.bind_scope_to_session"),
        patch(f"{EVALUATE}._load_evaluation_config", return_value=(MagicMock(), {})),
        patch(f"{EVALUATE}._load_project_trace_metrics", return_value=[MagicMock()]) as metrics,
        patch(f"{EVALUATE}._build_evaluator", side_effect=_exceeded()),
        patch(f"{EVALUATE}.get_or_create_status", return_value=status) as get_status,
        patch(f"{EVALUATE}._schedule_debounced_conversation_eval") as schedule,
    ):
        yield {"get_status": get_status, "metrics": metrics, "schedule": schedule}


def _run_turn(span):
    with patch.object(evaluate, "_turn_root_span", return_value=span):
        return evaluate_turn_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)


@pytest.mark.unit
class TestSkippedAtTheTokenLimit:
    def test_turn_evaluation_marks_the_root_span_skipped(self, at_the_limit):
        span = _span()
        out = _run_turn(span)

        assert out["status"] == "quota_exceeded"
        assert span.trace_metrics_status_id == "skipped-status"
        status_args = at_the_limit["get_status"].call_args.args
        assert status_args[1] == TRACE_SKIPPED_STATUS
        assert status_args[2] == EntityType.TRACE
        assert span.trace_metrics is None  # Nothing but the status is written.

    def test_turn_of_a_conversation_still_schedules_the_conversation(self, at_the_limit):
        _run_turn(_span(conversation_id="conv-1"))
        at_the_limit["schedule"].assert_called_once()

    def test_existing_status_is_kept(self, at_the_limit):
        span = _span(status_id="reviewer-pass")
        _run_turn(span)

        assert span.trace_metrics_status_id == "reviewer-pass"
        at_the_limit["get_status"].assert_not_called()

    def test_phase_without_metrics_is_not_marked(self, at_the_limit):
        at_the_limit["metrics"].return_value = []
        span = _span()
        out = _run_turn(span)

        assert out["status"] == "no_metrics"
        assert span.trace_metrics_status_id is None

    def test_span_without_input_or_output_is_not_marked(self, at_the_limit):
        span = _span()
        span.attributes = {}
        out = _run_turn(span)

        assert out["status"] == "no_io"
        assert span.trace_metrics_status_id is None

    def test_conversation_evaluation_marks_unmarked_root_spans(self, at_the_limit):
        fresh, reviewed = _span(), _span(status_id="reviewer-fail")
        trace = MagicMock()
        trace.messages.return_value.messages = ["hi"]
        with (
            patch.object(evaluate, "_conversation_root_spans", return_value=[fresh, reviewed]),
            patch(f"{EVALUATE}.load_evaluation_trace", return_value=trace),
        ):
            out = evaluate_conversation_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        assert out["status"] == "quota_exceeded"
        assert fresh.trace_metrics_status_id == "skipped-status"
        assert reviewed.trace_metrics_status_id == "reviewer-fail"

    def test_disabled_evaluation_is_not_marked(self, at_the_limit):
        span = _span()
        with patch(f"{EVALUATE}._load_evaluation_config", return_value=None):
            out = _run_turn(span)

        assert out["status"] == "skipped"
        assert span.trace_metrics_status_id is None
