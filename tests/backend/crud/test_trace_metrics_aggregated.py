"""Tests for get_trace_metrics_aggregated.

The project-level rollup behind ``GET /telemetry/metrics``. Tokens and costs here
must aggregate per *trace*: enrichment writes its trace-level blob onto every span
row, so summing across rows multiplies the real figure by the span count.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.schemas import SpanKind, StatusCode

from rhesis.backend.app.crud.telemetry import (
    create_trace_spans,
    get_trace_metrics_aggregated,
    mark_trace_processed,
)
from rhesis.backend.app.schemas.telemetry import OTELSpanCreate

TRACE_COST_USD = 0.05
TRACE_TOKENS = 420


def span(trace_id, span_id, project_id, *, parent=None, operation, tokens=None, error=False):
    now = datetime.now(timezone.utc)
    attributes = {AIAttributes.OPERATION_TYPE: operation}
    if tokens is not None:
        attributes[AIAttributes.MODEL_NAME] = "gpt-4"
        attributes[AIAttributes.LLM_TOKENS_INPUT] = tokens[0]
        attributes[AIAttributes.LLM_TOKENS_OUTPUT] = tokens[1]
        attributes[AIAttributes.LLM_TOKENS_TOTAL] = tokens[2]
    return OTELSpanCreate(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent,
        project_id=project_id,
        environment="development",
        span_name="ai.llm.invoke" if operation == "llm.invoke" else "ai.agent.invoke",
        span_kind=SpanKind.CLIENT,
        start_time=now,
        end_time=now + timedelta(seconds=1),
        status_code=StatusCode.ERROR if error else StatusCode.OK,
        attributes=attributes,
    )


def enrichment_blob(total_tokens=TRACE_TOKENS, cost_usd=TRACE_COST_USD):
    return {
        "costs": {
            "total_cost_usd": cost_usd,
            "total_cost_eur": cost_usd * 0.9,
            "total_input_tokens": 300,
            "total_output_tokens": 120,
            "total_tokens": total_tokens,
            "breakdown": [],
        }
    }


@pytest.fixture
def six_span_trace(test_db, db_project, test_org_id):
    """One enriched trace of six spans: an agent run plus five model calls.

    The shape that used to report six times the real cost.
    """
    trace_id = uuid.uuid4().hex
    project_id = str(db_project.id)
    spans = [
        span(trace_id, uuid.uuid4().hex[:16], project_id, operation="agent.invoke"),
    ]
    for _ in range(5):
        spans.append(
            span(
                trace_id,
                uuid.uuid4().hex[:16],
                project_id,
                parent=spans[0].span_id,
                operation="llm.invoke",
                tokens=(60, 24, 84),
            )
        )
    create_trace_spans(test_db, spans, organization_id=test_org_id)
    mark_trace_processed(test_db, trace_id, enrichment_blob())
    return trace_id, project_id


@pytest.mark.integration
class TestTokenAndCostAggregation:
    """Tokens and cost aggregate once per trace, not once per span row."""

    def test_cost_is_not_multiplied_by_span_count(
        self, test_db, six_span_trace, test_org_id
    ):
        """Regression: this used to report 6x the trace's real cost."""
        _, project_id = six_span_trace

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["total_spans"] == 6
        assert metrics["total_traces"] == 1
        assert metrics["total_cost_usd"] == pytest.approx(TRACE_COST_USD, rel=1e-6)

    def test_tokens_come_from_enrichment_not_a_raw_span_sum(
        self, test_db, six_span_trace, test_org_id
    ):
        """The enriched total wins, so aggregate-reporting frameworks aren't doubled."""
        _, project_id = six_span_trace

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["total_tokens"] == TRACE_TOKENS

    def test_span_counts_and_error_rate_still_span_level(
        self, test_db, db_project, test_org_id
    ):
        """Collapsing tokens per trace must not collapse the span-level metrics."""
        trace_id = uuid.uuid4().hex
        project_id = str(db_project.id)
        spans = [
            span(trace_id, uuid.uuid4().hex[:16], project_id, operation="agent.invoke"),
            span(
                trace_id,
                uuid.uuid4().hex[:16],
                project_id,
                operation="llm.invoke",
                tokens=(10, 5, 15),
                error=True,
            ),
        ]
        create_trace_spans(test_db, spans, organization_id=test_org_id)

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["total_spans"] == 2
        assert metrics["error_rate"] == pytest.approx(0.5)
        assert metrics["operation_breakdown"]["llm.invoke"] == 1
        assert metrics["operation_breakdown"]["agent.invoke"] == 1

    def test_unenriched_trace_falls_back_to_llm_invoke_spans(
        self, test_db, db_project, test_org_id
    ):
        """A freshly ingested trace still reports tokens before enrichment runs.

        The agent-run span repeats its children's aggregate, so a raw sum over all
        spans would report 60 instead of 30.
        """
        trace_id = uuid.uuid4().hex
        project_id = str(db_project.id)
        spans = [
            span(
                trace_id,
                uuid.uuid4().hex[:16],
                project_id,
                operation="agent.invoke",
                tokens=(20, 10, 30),
            ),
            span(
                trace_id,
                uuid.uuid4().hex[:16],
                project_id,
                operation="llm.invoke",
                tokens=(10, 5, 15),
            ),
            span(
                trace_id,
                uuid.uuid4().hex[:16],
                project_id,
                operation="llm.invoke",
                tokens=(10, 5, 15),
            ),
        ]
        create_trace_spans(test_db, spans, organization_id=test_org_id)

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["total_tokens"] == 30
        assert metrics["total_cost_usd"] == 0.0
