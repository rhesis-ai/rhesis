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

from rhesis.backend.app.constants import TestExecutionContext
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

    def test_cost_is_not_multiplied_by_span_count(self, test_db, six_span_trace, test_org_id):
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

    def test_span_counts_and_error_rate_still_span_level(self, test_db, db_project, test_org_id):
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


def run_span(trace_id, project_id, test_run_id, *, operation, tokens=None):
    """A span stamped with a test run, the way test execution ingests them."""
    created = span(trace_id, uuid.uuid4().hex[:16], project_id, operation=operation, tokens=tokens)
    created.attributes[TestExecutionContext.SpanAttributes.TEST_RUN_ID] = str(test_run_id)
    return created


@pytest.mark.integration
class TestTestRunScoping:
    """Metrics narrowed to a single test run.

    Without this the test run Traces tab has to hide its rollup tiles, because the
    only numbers available cover the whole project.
    """

    @pytest.fixture
    def two_runs(self, test_db, db_project, test_org_id, db_test_run, db_test_run_running):
        """Two runs in one project: 2 llm spans totalling 150 tokens, and 1 of 500."""
        project_id = str(db_project.id)
        run_a, run_b = db_test_run.id, db_test_run_running.id

        trace_a = uuid.uuid4().hex
        create_trace_spans(
            test_db,
            [
                run_span(trace_a, project_id, run_a, operation="agent.invoke"),
                run_span(trace_a, project_id, run_a, operation="llm.invoke", tokens=(50, 25, 75)),
                run_span(trace_a, project_id, run_a, operation="llm.invoke", tokens=(50, 25, 75)),
            ],
            organization_id=test_org_id,
        )

        trace_b = uuid.uuid4().hex
        create_trace_spans(
            test_db,
            [
                run_span(
                    trace_b, project_id, run_b, operation="llm.invoke", tokens=(400, 100, 500)
                ),
            ],
            organization_id=test_org_id,
        )
        return project_id, str(run_a), str(run_b), trace_a

    def test_counts_only_the_requested_run(self, test_db, two_runs, test_org_id):
        project_id, run_a, _, _ = two_runs

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id, test_run_id=run_a
        )

        assert metrics["total_traces"] == 1
        assert metrics["total_spans"] == 3
        assert metrics["total_tokens"] == 150

    def test_the_other_run_does_not_leak_in(self, test_db, two_runs, test_org_id):
        project_id, _, run_b, _ = two_runs

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id, test_run_id=run_b
        )

        assert metrics["total_traces"] == 1
        assert metrics["total_spans"] == 1
        assert metrics["total_tokens"] == 500

    def test_without_a_run_the_whole_project_is_counted(self, test_db, two_runs, test_org_id):
        """The Traces page passes no test_run_id and must be unaffected."""
        project_id, _, _, _ = two_runs

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["total_traces"] >= 2
        assert metrics["total_tokens"] >= 650

    def test_cost_is_scoped_too(self, test_db, two_runs, test_org_id):
        """Enrichment writes its blob per trace, so cost has to follow the same filter."""
        project_id, run_a, run_b, trace_a = two_runs
        mark_trace_processed(test_db, trace_a, enrichment_blob())

        priced = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id, test_run_id=run_a
        )
        unpriced = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id, test_run_id=run_b
        )

        assert priced["total_cost_usd"] == pytest.approx(TRACE_COST_USD)
        assert unpriced["total_cost_usd"] == 0.0

    def test_malformed_run_id_is_a_400(self, test_db, db_project, test_org_id):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as caught:
            get_trace_metrics_aggregated(
                test_db,
                organization_id=test_org_id,
                project_id=str(db_project.id),
                test_run_id="not-a-uuid",
            )

        assert caught.value.status_code == 400
