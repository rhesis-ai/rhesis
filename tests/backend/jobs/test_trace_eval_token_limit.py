"""A trace not evaluated because of the model token limit is marked Skipped."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.constants import (
    TRACE_SKIPPED_REASON_TOKEN_LIMIT,
    TRACE_SKIPPED_STATUS,
    EntityType,
)
from rhesis.backend.app.crud.telemetry import (
    update_trace_conversation_metrics,
    update_trace_turn_metrics,
)
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.quota.enforcement import QuotaExceededError, QuotaVerdict
from rhesis.backend.jobs.telemetry import evaluate
from rhesis.backend.jobs.telemetry.evaluate import (
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


def _span(trace_metrics=None):
    span = MagicMock()
    span.trace_metrics = trace_metrics
    span.trace_metrics_status_id = None
    return span


@pytest.fixture
def at_the_limit():
    status = MagicMock(id="skipped-status")
    with (
        patch(f"{EVALUATE}.SessionLocal", return_value=MagicMock(spec=Session)),
        patch(f"{EVALUATE}.bind_scope_to_session"),
        patch(f"{EVALUATE}._prepare_evaluation", side_effect=_exceeded()),
        patch(
            "rhesis.backend.app.utils.crud_utils.get_or_create_status", return_value=status
        ) as get_status,
        patch("sqlalchemy.orm.attributes.flag_modified"),
    ):
        yield get_status


@pytest.mark.unit
class TestSkippedAtTheTokenLimit:
    def test_turn_evaluation_marks_the_root_span_skipped(self, at_the_limit):
        span = _span()
        with patch.object(evaluate, "_turn_root_span", return_value=span):
            out = evaluate_turn_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        assert out["status"] == "quota_exceeded"
        assert span.trace_metrics_status_id == "skipped-status"
        assert span.trace_metrics["skipped"] == {"reason": TRACE_SKIPPED_REASON_TOKEN_LIMIT}
        status_args = at_the_limit.call_args.args
        assert status_args[1] == TRACE_SKIPPED_STATUS
        assert status_args[2] == EntityType.TRACE

    def test_conversation_evaluation_marks_every_unevaluated_root_span(self, at_the_limit):
        fresh = _span()
        evaluated = _span({"turn_metrics": {"metrics": {}}})
        with patch.object(evaluate, "_conversation_root_spans", return_value=[fresh, evaluated]):
            out = evaluate_conversation_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        assert out["status"] == "quota_exceeded"
        assert fresh.trace_metrics_status_id == "skipped-status"
        # A span with results keeps them and its status.
        assert evaluated.trace_metrics_status_id is None
        assert "skipped" not in evaluated.trace_metrics

    def test_disabled_evaluation_is_not_marked(self, at_the_limit):
        span = _span()
        with (
            patch(f"{EVALUATE}._prepare_evaluation", return_value=None),
            patch.object(evaluate, "_turn_root_span", return_value=span),
        ):
            out = evaluate_turn_trace_metrics.run(TRACE_ID, PROJECT_ID, ORG_ID)

        assert out["status"] == "skipped"
        assert span.trace_metrics_status_id is None


@pytest.mark.unit
class TestResultsReplaceTheSkip:
    def test_turn_results_drop_the_skip_marker(self):
        db = MagicMock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = _span(
            {"skipped": {"reason": TRACE_SKIPPED_REASON_TOKEN_LIMIT}}
        )
        with patch(
            "rhesis.backend.app.crud.telemetry.bulk_update", return_value=[uuid4()]
        ) as bulk_update:
            update_trace_turn_metrics(db, str(uuid4()), {"metrics": {}})

        assert bulk_update.call_args.args[3]["trace_metrics"] == {"turn_metrics": {"metrics": {}}}

    def test_conversation_results_drop_the_skip_marker(self):
        span = _span({"skipped": {"reason": TRACE_SKIPPED_REASON_TOKEN_LIMIT}})
        db = MagicMock(spec=Session)
        db.query.return_value.filter.return_value.all.return_value = [span]
        with patch("sqlalchemy.orm.attributes.flag_modified"):
            update_trace_conversation_metrics(db, TRACE_ID, {"metrics": {}})

        assert span.trace_metrics == {"conversation_metrics": {"metrics": {}}}
