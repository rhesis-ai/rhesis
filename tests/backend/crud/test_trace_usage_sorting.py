"""Tests for the traces list's usage columns and the ordering behind them.

The sort expressions must produce the same figure the row shows. That is not automatic
here: no trace in the database carries the trace-level input/output cost keys, so an
expression that read them directly would order every row as NULL while the row beside it
displayed a real number derived from the breakdown.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.schemas import SpanKind, StatusCode

from rhesis.backend.app.crud.telemetry import (
    TRACE_SORT_FIELDS,
    create_trace_spans,
    mark_trace_processed,
    query_traces,
)
from rhesis.backend.app.schemas.telemetry import OTELSpanCreate
from rhesis.backend.app.services.telemetry.token_totals import trace_summary_usage


def root_span(trace_id, project_id, *, minutes_ago=0):
    now = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return OTELSpanCreate(
        trace_id=trace_id,
        span_id=uuid.uuid4().hex[:16],
        parent_span_id=None,
        project_id=project_id,
        environment="development",
        span_name="ai.agent.invoke",
        span_kind=SpanKind.CLIENT,
        start_time=now,
        end_time=now + timedelta(seconds=1),
        status_code=StatusCode.OK,
        attributes={AIAttributes.OPERATION_TYPE: "agent.invoke"},
    )


def legacy_blob(model, input_tokens, output_tokens, input_cost, output_cost):
    """The shape every already-enriched trace is in: a breakdown, nothing rolled up.

    No total_input_cost_usd, no total_output_cost_usd, no models_used -- the keys the
    new columns and sorts are named after. All 4199 span rows on the dev instance look
    like this, so this is the only shape that matters for whether the feature works.
    """
    return {
        "costs": {
            "total_cost_usd": input_cost + output_cost,
            "total_cost_eur": (input_cost + output_cost) * 0.9,
            "breakdown": [
                {
                    "span_id": uuid.uuid4().hex[:16],
                    "model_name": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "input_cost_usd": input_cost,
                    "output_cost_usd": output_cost,
                    "total_cost_usd": input_cost + output_cost,
                    "input_cost_eur": input_cost * 0.9,
                    "output_cost_eur": output_cost * 0.9,
                    "total_cost_eur": (input_cost + output_cost) * 0.9,
                }
            ],
        }
    }


def priced_trace(db, project_id, org_id, *, model, tokens, costs, minutes_ago=0):
    trace_id = uuid.uuid4().hex
    create_trace_spans(
        db, [root_span(trace_id, project_id, minutes_ago=minutes_ago)], organization_id=org_id
    )
    mark_trace_processed(db, trace_id, legacy_blob(model, tokens[0], tokens[1], costs[0], costs[1]))
    return trace_id


@pytest.fixture
def three_traces(test_db, db_project, test_org_id):
    """Cheap, middling and expensive, arranged to fight every fallback ordering.

    Spend runs opposite to age: the expensive trace is the oldest. Ordering falls back to
    start_time descending whenever the sort expression cannot tell rows apart -- which is
    exactly what happens if one of these expressions reads a rolled-up key that no trace
    carries. Created cheapest-first, that fallback would hand back the expected order and
    every assertion here would pass against a sort that does nothing.

    The models sort in a third order again, so a model sort cannot ride on either.
    """
    project_id = str(db_project.id)
    return project_id, {
        "cheap": priced_trace(
            test_db,
            project_id,
            test_org_id,
            model="zeta",
            tokens=(10, 5),
            costs=(0.001, 0.0005),
            minutes_ago=0,
        ),
        "middle": priced_trace(
            test_db,
            project_id,
            test_org_id,
            model="alpha",
            tokens=(100, 200),
            costs=(0.01, 0.2),
            minutes_ago=30,
        ),
        "expensive": priced_trace(
            test_db,
            project_id,
            test_org_id,
            model="mu",
            tokens=(900, 50),
            costs=(0.9, 0.005),
            minutes_ago=60,
        ),
    }


def ordered_trace_ids(db, org_id, project_id, sort_by, sort_order="desc"):
    rows = query_traces(
        db,
        organization_id=org_id,
        project_id=project_id,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=100,
    )
    return [row.trace.trace_id for row in rows]


@pytest.mark.integration
class TestNewSortFields:
    """Each new field orders by itself, not by a neighbour."""

    def test_input_and_output_cost_order_independently(self, test_db, test_org_id, three_traces):
        """The expensive trace leads on input, the middling one on output.

        Built so a sort that quietly fell back to total cost would fail: the trace with
        the highest output cost is not the one with the highest total.
        """
        project_id, traces = three_traces

        by_input = ordered_trace_ids(test_db, test_org_id, project_id, "total_input_cost_usd")
        by_output = ordered_trace_ids(test_db, test_org_id, project_id, "total_output_cost_usd")

        assert by_input[0] == traces["expensive"]
        assert by_output[0] == traces["middle"]

    def test_input_and_output_tokens_order_independently(self, test_db, test_org_id, three_traces):
        project_id, traces = three_traces

        by_input = ordered_trace_ids(test_db, test_org_id, project_id, "total_input_tokens")
        by_output = ordered_trace_ids(test_db, test_org_id, project_id, "total_output_tokens")

        assert by_input[0] == traces["expensive"]
        assert by_output[0] == traces["middle"]

    def test_orders_by_model_name(self, test_db, test_org_id, three_traces):
        project_id, traces = three_traces

        ascending = ordered_trace_ids(test_db, test_org_id, project_id, "model", "asc")

        assert ascending[0] == traces["middle"]  # alpha
        assert ascending[-1] == traces["cheap"]  # zeta

    def test_both_directions_differ(self, test_db, test_org_id, three_traces):
        project_id, _ = three_traces

        descending = ordered_trace_ids(test_db, test_org_id, project_id, "total_cost_usd", "desc")
        ascending = ordered_trace_ids(test_db, test_org_id, project_id, "total_cost_usd", "asc")

        assert ascending == list(reversed(descending))

    def test_an_unknown_sort_field_is_a_400(self, test_db, test_org_id, db_project):
        with pytest.raises(HTTPException) as caught:
            query_traces(
                test_db,
                organization_id=test_org_id,
                project_id=str(db_project.id),
                sort_by="total_profit",
            )

        assert caught.value.status_code == 400

    def test_every_new_field_is_accepted(self, test_db, test_org_id, db_project):
        for field in (
            "total_input_tokens",
            "total_output_tokens",
            "total_input_cost_usd",
            "total_output_cost_usd",
            "model",
        ):
            assert field in TRACE_SORT_FIELDS
            query_traces(
                test_db,
                organization_id=test_org_id,
                project_id=str(db_project.id),
                sort_by=field,
                limit=1,
            )


@pytest.mark.integration
class TestSortingMatchesWhatTheRowShows:
    """The ordering expression and the displayed figure must come from one source."""

    def test_sorting_works_on_blobs_that_have_no_rolled_up_keys(
        self, test_db, test_org_id, three_traces
    ):
        """The case that covers the entire existing database.

        Reading costs.total_input_cost_usd directly would make every row NULL here, and
        the sort would degenerate into the start_time tiebreaker while the column beside
        it displayed real numbers.
        """
        project_id, traces = three_traces

        ordered = ordered_trace_ids(test_db, test_org_id, project_id, "total_input_cost_usd")

        assert ordered[:3] == [traces["expensive"], traces["middle"], traces["cheap"]]

    def test_the_order_matches_the_displayed_values(self, test_db, test_org_id, three_traces):
        """Walk the sorted rows and check the numbers really do descend."""
        project_id, _ = three_traces

        rows = query_traces(
            test_db,
            organization_id=test_org_id,
            project_id=project_id,
            sort_by="total_input_cost_usd",
            sort_order="desc",
            limit=100,
        )
        shown = [
            trace_summary_usage(row.trace.enriched_data, row.llm_tokens)["total_input_cost_usd"]
            for row in rows
        ]
        priced = [value for value in shown if value is not None]

        assert priced == sorted(priced, reverse=True)
        assert len(priced) >= 3

    def test_an_unpriced_trace_sorts_last_in_both_directions(
        self, test_db, db_project, test_org_id, three_traces
    ):
        """It shows a dash, so it must read as unknown rather than as costing nothing."""
        project_id, _ = three_traces
        bare = uuid.uuid4().hex
        create_trace_spans(test_db, [root_span(bare, project_id)], organization_id=test_org_id)

        descending = ordered_trace_ids(test_db, test_org_id, project_id, "total_cost_usd", "desc")
        ascending = ordered_trace_ids(test_db, test_org_id, project_id, "total_cost_usd", "asc")

        assert descending[-1] == bare
        assert ascending[-1] == bare


@pytest.mark.integration
class TestSummaryUsageFields:
    """What the row carries, shared by the traces page and a run's traces tab."""

    def test_reports_the_split_and_the_models(self, test_db, test_org_id, three_traces):
        project_id, traces = three_traces

        rows = query_traces(test_db, organization_id=test_org_id, project_id=project_id, limit=100)
        by_id = {row.trace.trace_id: row for row in rows}
        usage = trace_summary_usage(
            by_id[traces["middle"]].trace.enriched_data, by_id[traces["middle"]].llm_tokens
        )

        assert usage["total_input_tokens"] == 100
        assert usage["total_output_tokens"] == 200
        assert usage["total_input_cost_usd"] == pytest.approx(0.01)
        assert usage["total_output_cost_usd"] == pytest.approx(0.2)
        assert usage["models"] == ["alpha"]
        assert usage["providers"] == ["unknown"]

    def test_an_unpriced_trace_reports_nothing_rather_than_zero(
        self, test_db, db_project, test_org_id
    ):
        project_id = str(db_project.id)
        bare = uuid.uuid4().hex
        create_trace_spans(test_db, [root_span(bare, project_id)], organization_id=test_org_id)

        rows = query_traces(test_db, organization_id=test_org_id, project_id=project_id, limit=100)
        row = next(r for r in rows if r.trace.trace_id == bare)
        usage = trace_summary_usage(row.trace.enriched_data, row.llm_tokens)

        assert usage["total_cost_usd"] is None
        assert usage["total_input_cost_usd"] is None
        assert usage["models"] == []
