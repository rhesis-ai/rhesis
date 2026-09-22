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


def legacy_enrichment_blob(models):
    """A blob shaped the way every already-enriched trace in the database is.

    No trace-level cost split, no models_used, and no per-span provider -- those keys
    arrived after enrichment had already run over everything. The rollup has to derive
    them from the breakdown, otherwise the new figures are blank until every trace
    happens to be re-enriched, which nothing triggers.
    """
    return {
        "costs": {
            "total_cost_usd": 0.03 * len(models),
            "total_cost_eur": 0.027 * len(models),
            "total_input_tokens": 200 * len(models),
            "total_output_tokens": 100 * len(models),
            "total_tokens": 300 * len(models),
            "breakdown": [
                {
                    "span_id": uuid.uuid4().hex[:16],
                    "model_name": model,
                    "input_tokens": 200,
                    "output_tokens": 100,
                    "total_tokens": 300,
                    "input_cost_usd": 0.02,
                    "output_cost_usd": 0.01,
                    "total_cost_usd": 0.03,
                    "input_cost_eur": 0.018,
                    "output_cost_eur": 0.009,
                    "total_cost_eur": 0.027,
                }
                for model in models
            ],
        }
    }


@pytest.mark.integration
class TestUsageBreakdown:
    """The input/output split and the models behind it."""

    def test_splits_tokens_and_cost(self, test_db, six_span_trace, test_org_id):
        _, project_id = six_span_trace

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["total_input_tokens"] == 300
        assert metrics["total_output_tokens"] == 120

    def test_derives_the_cost_split_for_a_blob_that_has_none(
        self, test_db, db_project, test_org_id
    ):
        """The case that covers every trace already in the database."""
        trace_id = uuid.uuid4().hex
        project_id = str(db_project.id)
        create_trace_spans(
            test_db,
            [span(trace_id, uuid.uuid4().hex[:16], project_id, operation="agent.invoke")],
            organization_id=test_org_id,
        )
        mark_trace_processed(test_db, trace_id, legacy_enrichment_blob(["gpt-4"]))

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["total_input_cost_usd"] == pytest.approx(0.02)
        assert metrics["total_output_cost_usd"] == pytest.approx(0.01)
        assert metrics["total_cost_usd"] == pytest.approx(0.03)

    def test_the_split_is_not_multiplied_by_span_count(self, test_db, db_project, test_org_id):
        """Same trap as the total: the blob is on every span row of the trace."""
        trace_id = uuid.uuid4().hex
        project_id = str(db_project.id)
        create_trace_spans(
            test_db,
            [
                span(trace_id, uuid.uuid4().hex[:16], project_id, operation="agent.invoke"),
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
            ],
            organization_id=test_org_id,
        )
        mark_trace_processed(test_db, trace_id, legacy_enrichment_blob(["gpt-4"]))

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["total_spans"] == 3
        assert metrics["total_input_cost_usd"] == pytest.approx(0.02)

    def test_models_come_off_span_attributes_before_enrichment(
        self, test_db, db_project, test_org_id
    ):
        """An unenriched trace has no blob, so the spans are the only source."""
        trace_id = uuid.uuid4().hex
        project_id = str(db_project.id)
        create_trace_spans(
            test_db,
            [
                span(
                    trace_id,
                    uuid.uuid4().hex[:16],
                    project_id,
                    operation="llm.invoke",
                    tokens=(10, 5, 15),
                )
            ],
            organization_id=test_org_id,
        )

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["models_used"] == ["gpt-4"]
        assert metrics["providers_used"] == ["openai"]

    def test_models_come_off_the_blob_when_the_spans_are_out_of_scope(
        self, test_db, db_project, test_org_id, db_test_run
    ):
        """The test-run case, and the reason the blob is read at all.

        ``test_run_id`` is stamped on the root span, not on the llm.invoke children, so
        scoping to a run leaves no span carrying a model name. The enrichment blob is
        written onto every span row of the trace, including that root, so it still knows.
        """
        trace_id = uuid.uuid4().hex
        project_id = str(db_project.id)
        create_trace_spans(
            test_db,
            [run_span(trace_id, project_id, db_test_run.id, operation="function.invoke")],
            organization_id=test_org_id,
        )
        mark_trace_processed(
            test_db, trace_id, legacy_enrichment_blob(["gemini-2.0-flash", "gpt-4"])
        )

        metrics = get_trace_metrics_aggregated(
            test_db,
            organization_id=test_org_id,
            project_id=project_id,
            test_run_id=str(db_test_run.id),
        )

        assert metrics["models_used"] == ["gemini-2.0-flash", "gpt-4"]
        assert metrics["providers_used"] == ["gemini", "openai"]

    def test_an_unpriceable_model_is_reported_as_unknown(self, test_db, db_project, test_org_id):
        trace_id = uuid.uuid4().hex
        project_id = str(db_project.id)
        create_trace_spans(
            test_db,
            [span(trace_id, uuid.uuid4().hex[:16], project_id, operation="agent.invoke")],
            organization_id=test_org_id,
        )
        mark_trace_processed(test_db, trace_id, legacy_enrichment_blob(["self-hosted-7b"]))

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["models_used"] == ["self-hosted-7b"]
        assert metrics["providers_used"] == ["unknown"]

    def test_a_project_with_no_llm_spans_reports_empty_lists(
        self, test_db, db_project, test_org_id
    ):
        """Empty, not ['unknown'] -- there is nothing to attribute."""
        trace_id = uuid.uuid4().hex
        project_id = str(db_project.id)
        create_trace_spans(
            test_db,
            [span(trace_id, uuid.uuid4().hex[:16], project_id, operation="tool.invoke")],
            organization_id=test_org_id,
        )

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["models_used"] == []
        assert metrics["providers_used"] == []


def blob_without_token_rollup(models):
    """A breakdown with no trace-level token totals at all.

    Older than legacy_enrichment_blob: this predates total_tokens too, which is the
    shape 1681 of the span rows on the dev instance are actually in.
    """
    blob = legacy_enrichment_blob(models)
    for key in ("total_tokens", "total_input_tokens", "total_output_tokens"):
        blob["costs"].pop(key)
    return blob


@pytest.mark.integration
class TestTokensForBlobsWithNoTokenRollup:
    """Tokens have to come off the breakdown when the trace-level totals are absent.

    The raw fallback sums llm.invoke spans, which is fine project-wide but reports zero
    under test-run scope: test_run_id is stamped on the root span only, so the spans it
    would sum are not in scope. trace_usage_totals already derives these in Python, so
    without the same derivation in SQL the two disagree.
    """

    def test_derives_tokens_from_the_breakdown_under_run_scope(
        self, test_db, db_project, test_org_id, db_test_run
    ):
        """The undercount: one root span in scope, all the tokens in the blob."""
        trace_id = uuid.uuid4().hex
        project_id = str(db_project.id)
        create_trace_spans(
            test_db,
            [run_span(trace_id, project_id, db_test_run.id, operation="function.invoke")],
            organization_id=test_org_id,
        )
        mark_trace_processed(test_db, trace_id, blob_without_token_rollup(["gpt-4"]))

        metrics = get_trace_metrics_aggregated(
            test_db,
            organization_id=test_org_id,
            project_id=project_id,
            test_run_id=str(db_test_run.id),
        )

        assert metrics["total_tokens"] == 300
        assert metrics["total_input_tokens"] == 200
        assert metrics["total_output_tokens"] == 100

    def test_agrees_with_the_python_accessor(self, test_db, db_project, test_org_id):
        """The two paths must report the same trace identically."""
        from rhesis.backend.app.services.telemetry.token_totals import trace_usage_totals

        trace_id = uuid.uuid4().hex
        project_id = str(db_project.id)
        blob = blob_without_token_rollup(["gpt-4", "gemini-2.0-flash"])
        create_trace_spans(
            test_db,
            [span(trace_id, uuid.uuid4().hex[:16], project_id, operation="agent.invoke")],
            organization_id=test_org_id,
        )
        mark_trace_processed(test_db, trace_id, blob)

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )
        in_python = trace_usage_totals(blob)

        assert metrics["total_tokens"] == in_python.total_tokens
        assert metrics["total_input_tokens"] == in_python.input_tokens
        assert metrics["total_output_tokens"] == in_python.output_tokens

    def test_an_unenriched_trace_still_uses_the_raw_span_sum(
        self, test_db, db_project, test_org_id
    ):
        """The trap in the fix: a breakdown sum of nothing is unknown, not zero.

        Coalescing an empty breakdown to 0 instead of NULL would swallow the raw
        fallback and report a freshly ingested trace as having spent nothing.
        """
        trace_id = uuid.uuid4().hex
        project_id = str(db_project.id)
        create_trace_spans(
            test_db,
            [
                span(
                    trace_id,
                    uuid.uuid4().hex[:16],
                    project_id,
                    operation="llm.invoke",
                    tokens=(40, 20, 60),
                )
            ],
            organization_id=test_org_id,
        )

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["total_tokens"] == 60
        assert metrics["total_input_tokens"] == 40
        assert metrics["total_output_tokens"] == 20

    def test_a_breakdown_entry_without_its_own_total_falls_back_to_input_plus_output(
        self, test_db, db_project, test_org_id
    ):
        trace_id = uuid.uuid4().hex
        project_id = str(db_project.id)
        blob = blob_without_token_rollup(["gpt-4"])
        for entry in blob["costs"]["breakdown"]:
            entry.pop("total_tokens")
        create_trace_spans(
            test_db,
            [span(trace_id, uuid.uuid4().hex[:16], project_id, operation="agent.invoke")],
            organization_id=test_org_id,
        )
        mark_trace_processed(test_db, trace_id, blob)

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["total_tokens"] == 300


@pytest.mark.integration
class TestCostTotalDerivedFromBreakdown:
    """The total cost gets the same breakdown fallback its two halves already have.

    Without it a blob carrying a breakdown but no trace-level total_cost_usd reports a
    total of zero beside a non-zero input and output cost -- three figures from one trace
    that do not add up, on the same row.
    """

    def _trace_with(self, test_db, db_project, test_org_id, costs):
        trace_id = uuid.uuid4().hex
        project_id = str(db_project.id)
        create_trace_spans(
            test_db,
            [span(trace_id, uuid.uuid4().hex[:16], project_id, operation="agent.invoke")],
            organization_id=test_org_id,
        )
        mark_trace_processed(test_db, trace_id, {"costs": costs})
        return project_id

    def test_sums_the_breakdown_when_the_total_is_absent(self, test_db, db_project, test_org_id):
        project_id = self._trace_with(
            test_db,
            db_project,
            test_org_id,
            {
                "breakdown": [
                    {
                        "span_id": uuid.uuid4().hex[:16],
                        "model_name": "gpt-4",
                        "input_tokens": 200,
                        "output_tokens": 100,
                        "total_tokens": 300,
                        "input_cost_usd": 0.02,
                        "output_cost_usd": 0.01,
                        "total_cost_usd": 0.03,
                    }
                ]
            },
        )

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["total_cost_usd"] == pytest.approx(0.03)

    def test_the_three_cost_figures_agree(self, test_db, db_project, test_org_id):
        """The point of the fallback: input + output must not exceed a zeroed total."""
        project_id = self._trace_with(
            test_db,
            db_project,
            test_org_id,
            {
                "breakdown": [
                    {
                        "span_id": uuid.uuid4().hex[:16],
                        "model_name": "gpt-4",
                        "input_tokens": 200,
                        "output_tokens": 100,
                        "input_cost_usd": 0.02,
                        "output_cost_usd": 0.01,
                        "total_cost_usd": 0.03,
                    }
                ]
            },
        )

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["total_input_cost_usd"] + metrics["total_output_cost_usd"] == pytest.approx(
            metrics["total_cost_usd"]
        )

    def test_an_unenriched_trace_still_reports_no_cost(self, test_db, db_project, test_org_id):
        """Cost has no span-attribute fallback, so a trace with no blob stays at zero."""
        trace_id = uuid.uuid4().hex
        project_id = str(db_project.id)
        create_trace_spans(
            test_db,
            [
                span(
                    trace_id,
                    uuid.uuid4().hex[:16],
                    project_id,
                    operation="llm.invoke",
                    tokens=(10, 5, 15),
                )
            ],
            organization_id=test_org_id,
        )

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["total_cost_usd"] == 0.0
        assert metrics["total_tokens"] == 15


@pytest.mark.integration
class TestPricingProgressSignals:
    """Two counts that say what a total cost of zero actually means.

    ``total_cost_usd`` bottoms out at 0.0 for a trace nobody has priced, for one whose
    model LiteLLM does not know, and for one that genuinely cost nothing. On its own it
    cannot tell a caller which, so the card reading it could neither decide when to stop
    waiting nor whether to show ``$0.00`` or a dash.
    """

    def _metrics(self, db, project_id, org_id):
        return get_trace_metrics_aggregated(db, organization_id=org_id, project_id=project_id)

    def test_an_enriched_priced_trace_counts_as_both(self, test_db, six_span_trace, test_org_id):
        _, project_id = six_span_trace

        metrics = self._metrics(test_db, project_id, test_org_id)

        assert metrics["total_traces"] == 1
        assert metrics["enriched_traces"] == 1
        assert metrics["priced_traces"] == 1

    def test_an_unenriched_trace_counts_as_neither(self, test_db, db_project, test_org_id):
        """Nothing has run over it yet, so its zero cost means nothing at all."""
        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        create_trace_spans(
            test_db,
            [
                span(
                    trace_id,
                    uuid.uuid4().hex[:16],
                    project_id,
                    operation="llm.invoke",
                    tokens=(10, 5, 15),
                )
            ],
            organization_id=test_org_id,
        )

        metrics = self._metrics(test_db, project_id, test_org_id)

        assert metrics["total_traces"] == 1
        assert metrics["enriched_traces"] == 0
        assert metrics["priced_traces"] == 0
        assert metrics["total_cost_usd"] == 0

    def test_an_enriched_trace_with_no_cost_figure_is_not_priced(
        self, test_db, db_project, test_org_id
    ):
        """Enrichment ran and found nothing to price: the zero is real but unknown.

        This is the case that separates the two counts. Without ``priced_traces`` it is
        indistinguishable from a trace that cost nothing.
        """
        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        create_trace_spans(
            test_db,
            [
                span(
                    trace_id,
                    uuid.uuid4().hex[:16],
                    project_id,
                    operation="llm.invoke",
                    tokens=(10, 5, 15),
                )
            ],
            organization_id=test_org_id,
        )
        mark_trace_processed(test_db, trace_id, {"costs": {"total_tokens": 15, "breakdown": []}})

        metrics = self._metrics(test_db, project_id, test_org_id)

        assert metrics["enriched_traces"] == 1
        assert metrics["priced_traces"] == 0
        assert metrics["total_cost_usd"] == 0

    def test_a_trace_whose_models_could_not_be_priced_is_not_priced(
        self, test_db, db_project, test_org_id
    ):
        """A self-hosted model: tokens and a model name, but no rate anywhere.

        Enrichment leaves the cost keys off the breakdown entry rather than writing a
        zero, so ``known_cost_usd`` stays NULL and the run does not read as free.
        """
        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        create_trace_spans(
            test_db,
            [
                span(
                    trace_id,
                    uuid.uuid4().hex[:16],
                    project_id,
                    operation="llm.invoke",
                    tokens=(10, 5, 15),
                )
            ],
            organization_id=test_org_id,
        )
        mark_trace_processed(
            test_db,
            trace_id,
            {
                "costs": {
                    "total_tokens": 15,
                    "breakdown": [
                        {
                            "span_id": uuid.uuid4().hex[:16],
                            "model_name": "my-self-hosted-llama",
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "total_tokens": 15,
                        }
                    ],
                }
            },
        )

        metrics = self._metrics(test_db, project_id, test_org_id)

        assert metrics["enriched_traces"] == 1
        assert metrics["priced_traces"] == 0
        # The model is still counted, so the Models card has something to show.
        assert "my-self-hosted-llama" in metrics["models_used"]

    def test_a_trace_whose_tokens_we_could_not_read_is_not_priced(
        self, test_db, db_project, test_org_id
    ):
        """A priceable model, but no tokens to price.

        LiteLLM returns 0.0 for zero tokens without complaining, so enrichment used to
        record a real zero here and the run read as free. It now records no cost, which
        keeps known_cost_usd NULL and priced_traces at zero, exactly like a model with
        no published rate.
        """
        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        create_trace_spans(
            test_db,
            [
                span(
                    trace_id,
                    uuid.uuid4().hex[:16],
                    project_id,
                    operation="llm.invoke",
                    tokens=(0, 0, 0),
                )
            ],
            organization_id=test_org_id,
        )
        mark_trace_processed(
            test_db,
            trace_id,
            {
                "costs": {
                    "total_tokens": 0,
                    "breakdown": [
                        {
                            "span_id": uuid.uuid4().hex[:16],
                            "model_name": "gpt-4",
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "total_tokens": 0,
                        }
                    ],
                }
            },
        )

        metrics = self._metrics(test_db, project_id, test_org_id)

        assert metrics["enriched_traces"] == 1
        assert metrics["priced_traces"] == 0

    def test_a_trace_priced_at_zero_is_priced(self, test_db, db_project, test_org_id):
        """A free model costs a knowable nothing, and must not read as unknown."""
        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        create_trace_spans(
            test_db,
            [
                span(
                    trace_id,
                    uuid.uuid4().hex[:16],
                    project_id,
                    operation="llm.invoke",
                    tokens=(10, 5, 15),
                )
            ],
            organization_id=test_org_id,
        )
        mark_trace_processed(test_db, trace_id, enrichment_blob(cost_usd=0.0))

        metrics = self._metrics(test_db, project_id, test_org_id)

        assert metrics["enriched_traces"] == 1
        assert metrics["priced_traces"] == 1
        assert metrics["total_cost_usd"] == 0

    def test_a_trace_priced_only_through_its_breakdown_is_priced(
        self, test_db, db_project, test_org_id
    ):
        """Every trace already in the database predates the trace-level cost keys."""
        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        create_trace_spans(
            test_db,
            [
                span(
                    trace_id,
                    uuid.uuid4().hex[:16],
                    project_id,
                    operation="llm.invoke",
                    tokens=(10, 5, 15),
                )
            ],
            organization_id=test_org_id,
        )
        mark_trace_processed(
            test_db,
            trace_id,
            {
                "costs": {
                    "breakdown": [
                        {"model_name": "gpt-4", "total_cost_usd": 0.004, "total_tokens": 15}
                    ]
                }
            },
        )

        metrics = self._metrics(test_db, project_id, test_org_id)

        assert metrics["priced_traces"] == 1
        assert metrics["total_cost_usd"] == pytest.approx(0.004)

    def test_counts_are_per_trace_not_per_span(self, test_db, six_span_trace, test_org_id):
        """The trap this whole module exists for: the blob is on all six span rows."""
        _, project_id = six_span_trace

        metrics = self._metrics(test_db, project_id, test_org_id)

        assert metrics["total_spans"] == 6
        assert metrics["enriched_traces"] == 1
        assert metrics["priced_traces"] == 1

    def test_a_partly_enriched_scope_reports_the_shortfall(
        self, test_db, db_project, test_org_id, six_span_trace
    ):
        """What tells a caller enrichment is still working rather than finished."""
        project_id = str(db_project.id)
        pending = uuid.uuid4().hex
        create_trace_spans(
            test_db,
            [
                span(
                    pending,
                    uuid.uuid4().hex[:16],
                    project_id,
                    operation="llm.invoke",
                    tokens=(10, 5, 15),
                )
            ],
            organization_id=test_org_id,
        )

        metrics = self._metrics(test_db, project_id, test_org_id)

        assert metrics["total_traces"] == 2
        assert metrics["enriched_traces"] == 1


@pytest.mark.integration
class TestErrorCountIsSentNotDerived:
    """The exact failed-span count, because the rounded rate cannot rebuild it.

    ``error_rate`` is rounded to four places, so a caller multiplying it back by
    the span count gets a different integer for most inputs -- 3 errors in 11,667
    spans rounds to 0.0003, which reads back as 4.
    """

    def test_counts_the_failed_spans(self, test_db, db_project, test_org_id):
        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        spans = [
            span(trace_id, uuid.uuid4().hex[:16], project_id, operation="agent.invoke"),
            span(trace_id, uuid.uuid4().hex[:16], project_id, operation="llm.invoke", error=True),
            span(trace_id, uuid.uuid4().hex[:16], project_id, operation="llm.invoke", error=True),
        ]
        create_trace_spans(test_db, spans, organization_id=test_org_id)

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["total_spans"] == 3
        assert metrics["error_spans"] == 2
        assert metrics["error_rate"] == pytest.approx(0.6667, abs=1e-4)

    def test_is_zero_when_nothing_failed(self, test_db, six_span_trace, test_org_id):
        _, project_id = six_span_trace

        metrics = get_trace_metrics_aggregated(
            test_db, organization_id=test_org_id, project_id=project_id
        )

        assert metrics["error_spans"] == 0
        assert metrics["error_rate"] == 0
