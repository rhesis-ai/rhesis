"""Tests for per-run token and cost totals, and for ordering the list by them.

Two things are being guarded. The rollup has to collapse each trace before summing it
per run, the same trap the project-level rollup has. And the sort has to order the whole
organization's runs rather than the page it was handed -- a "most expensive first" list
that only reshuffles the newest page is worse than no sort at all, because it looks right.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.schemas import SpanKind, StatusCode

from rhesis.backend.app.constants import TestExecutionContext
from rhesis.backend.app.crud.telemetry import create_trace_spans, mark_trace_processed
from rhesis.backend.app.crud.test_run import (
    get_test_runs,
    get_usage_statistics_for_runs,
)
from rhesis.backend.app.schemas.telemetry import OTELSpanCreate


def run_root_span(trace_id, project_id, test_run_id, *, span_id=None):
    """A run's root span, which is the only span test_run_id is stamped on."""
    now = datetime.now(timezone.utc)
    return OTELSpanCreate(
        trace_id=trace_id,
        span_id=span_id or uuid.uuid4().hex[:16],
        parent_span_id=None,
        project_id=project_id,
        environment="development",
        span_name="function.invoke",
        span_kind=SpanKind.SERVER,
        start_time=now,
        end_time=now + timedelta(seconds=1),
        status_code=StatusCode.OK,
        attributes={
            AIAttributes.OPERATION_TYPE: "function.invoke",
            TestExecutionContext.SpanAttributes.TEST_RUN_ID: str(test_run_id),
        },
    )


def blob(model, input_tokens, output_tokens, input_cost, output_cost):
    return {
        "costs": {
            "total_cost_usd": input_cost + output_cost,
            "total_cost_eur": (input_cost + output_cost) * 0.9,
            "total_input_cost_usd": input_cost,
            "total_output_cost_usd": output_cost,
            "total_input_tokens": input_tokens,
            "total_output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "models_used": [model],
            "providers_used": ["openai" if model.startswith("gpt") else "gemini"],
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


def trace_for_run(db, project_id, run_id, org_id, *, model, tokens, costs, roots=1):
    """One priced trace attributed to a run, optionally with several root spans."""
    trace_id = uuid.uuid4().hex
    create_trace_spans(
        db,
        [run_root_span(trace_id, project_id, run_id) for _ in range(roots)],
        organization_id=org_id,
    )
    mark_trace_processed(db, trace_id, blob(model, tokens[0], tokens[1], costs[0], costs[1]))
    return trace_id


@pytest.mark.integration
class TestUsageStatisticsForRuns:
    """The per-run rollup behind the grid's usage columns."""

    def test_sums_a_run_s_traces(self, test_db, db_project, test_org_id, db_test_run):
        project_id = str(db_project.id)
        for _ in range(3):
            trace_for_run(
                test_db,
                project_id,
                db_test_run.id,
                test_org_id,
                model="gpt-4",
                tokens=(100, 50),
                costs=(0.01, 0.005),
            )

        stats = get_usage_statistics_for_runs(
            test_db, [db_test_run.id], organization_id=test_org_id
        )[str(db_test_run.id)]

        assert stats["total_tokens"] == 450
        assert stats["total_input_tokens"] == 300
        assert stats["total_output_tokens"] == 150
        assert stats["total_cost_usd"] == pytest.approx(0.045)
        assert stats["total_input_cost_usd"] == pytest.approx(0.03)
        assert stats["total_output_cost_usd"] == pytest.approx(0.015)

    def test_a_multi_root_trace_is_counted_once(
        self, test_db, db_project, test_org_id, db_test_run
    ):
        """A multi-turn conversation has one root span per turn under one trace_id.

        Every one of them carries the same enrichment blob, so summing the rows instead
        of collapsing the trace first would report three times the real cost. 28 traces
        in the database already have this shape.
        """
        trace_for_run(
            test_db,
            str(db_project.id),
            db_test_run.id,
            test_org_id,
            model="gpt-4",
            tokens=(100, 50),
            costs=(0.01, 0.005),
            roots=3,
        )

        stats = get_usage_statistics_for_runs(
            test_db, [db_test_run.id], organization_id=test_org_id
        )[str(db_test_run.id)]

        assert stats["total_tokens"] == 150
        assert stats["total_cost_usd"] == pytest.approx(0.015)

    def test_another_run_does_not_leak_in(
        self, test_db, db_project, test_org_id, db_test_run, db_test_run_running
    ):
        project_id = str(db_project.id)
        trace_for_run(
            test_db,
            project_id,
            db_test_run.id,
            test_org_id,
            model="gpt-4",
            tokens=(100, 50),
            costs=(0.01, 0.005),
        )
        trace_for_run(
            test_db,
            project_id,
            db_test_run_running.id,
            test_org_id,
            model="gpt-4",
            tokens=(900, 100),
            costs=(0.9, 0.1),
        )

        stats = get_usage_statistics_for_runs(
            test_db, [db_test_run.id, db_test_run_running.id], organization_id=test_org_id
        )

        assert stats[str(db_test_run.id)]["total_tokens"] == 150
        assert stats[str(db_test_run_running.id)]["total_tokens"] == 1000

    def test_a_run_with_no_traces_is_zero_filled(self, test_db, test_org_id, db_test_run):
        """So the caller can index unconditionally rather than guarding every read."""
        stats = get_usage_statistics_for_runs(
            test_db, [db_test_run.id], organization_id=test_org_id
        )[str(db_test_run.id)]

        assert stats["total_tokens"] == 0
        assert stats["total_cost_usd"] == 0
        assert stats["models"] == []
        assert stats["providers"] == []

    def test_collects_the_models_and_providers(self, test_db, db_project, test_org_id, db_test_run):
        project_id = str(db_project.id)
        for model in ("gpt-4", "gemini-2.0-flash", "gpt-4"):
            trace_for_run(
                test_db,
                project_id,
                db_test_run.id,
                test_org_id,
                model=model,
                tokens=(10, 5),
                costs=(0.001, 0.0005),
            )

        stats = get_usage_statistics_for_runs(
            test_db, [db_test_run.id], organization_id=test_org_id
        )[str(db_test_run.id)]

        assert stats["models"] == ["gemini-2.0-flash", "gpt-4"]
        assert stats["providers"] == ["gemini", "openai"]

    def test_no_run_ids_is_not_a_query(self, test_db, test_org_id):
        assert get_usage_statistics_for_runs(test_db, [], organization_id=test_org_id) == {}


@pytest.mark.integration
class TestSortingByUsage:
    """Ordering the whole organization's runs, not the page."""

    @pytest.fixture
    def three_priced_runs(self, test_db, db_project, test_org_id, db_test_run, db_test_run_running):
        """Two runs with very different spend, arranged so recency disagrees with cost.

        The expensive run is made the *older* of the two on purpose, so "ordered by what
        it spent" and "ordered by when it ran" give opposite answers. Without that, a
        regression where the usage sort silently fell back to the list's created_at
        default would still satisfy every assertion below.
        """
        project_id = str(db_project.id)
        cheap, expensive = db_test_run, db_test_run_running
        expensive.created_at = datetime.now(timezone.utc) - timedelta(days=7)
        cheap.created_at = datetime.now(timezone.utc)
        test_db.flush()

        trace_for_run(
            test_db,
            project_id,
            cheap.id,
            test_org_id,
            model="gpt-4",
            tokens=(100, 50),
            costs=(0.01, 0.005),
        )
        trace_for_run(
            test_db,
            project_id,
            expensive.id,
            test_org_id,
            model="alpha-model",
            tokens=(900, 100),
            costs=(0.9, 0.1),
        )
        return str(cheap.id), str(expensive.id)

    def _ordered_ids(self, db, org_id, sort_by, sort_order):
        runs = get_test_runs(
            db, skip=0, limit=100, sort_by=sort_by, sort_order=sort_order, organization_id=org_id
        )
        return [str(run.id) for run in runs]

    def test_orders_by_cost_descending(self, test_db, test_org_id, three_priced_runs):
        cheap, expensive = three_priced_runs

        ordered = self._ordered_ids(test_db, test_org_id, "total_cost_usd", "desc")

        assert ordered.index(expensive) < ordered.index(cheap)

    def test_orders_by_cost_ascending(self, test_db, test_org_id, three_priced_runs):
        cheap, expensive = three_priced_runs

        ordered = self._ordered_ids(test_db, test_org_id, "total_cost_usd", "asc")

        assert ordered.index(cheap) < ordered.index(expensive)

    def test_ascending_is_not_just_the_default_order_reversed(
        self, test_db, test_org_id, three_priced_runs
    ):
        """Guards the pair above: the two directions must actually differ."""
        ascending = self._ordered_ids(test_db, test_org_id, "total_cost_usd", "asc")
        descending = self._ordered_ids(test_db, test_org_id, "total_cost_usd", "desc")

        assert ascending == list(reversed(descending))

    def test_orders_by_tokens(self, test_db, test_org_id, three_priced_runs):
        fewer, more = three_priced_runs

        ordered = self._ordered_ids(test_db, test_org_id, "total_tokens", "desc")

        assert ordered.index(more) < ordered.index(fewer)

    def test_orders_by_the_input_output_split_independently(
        self, test_db, test_org_id, three_priced_runs
    ):
        cheap, expensive = three_priced_runs

        by_input = self._ordered_ids(test_db, test_org_id, "total_input_cost_usd", "desc")
        by_output = self._ordered_ids(test_db, test_org_id, "total_output_cost_usd", "desc")

        assert by_input.index(expensive) < by_input.index(cheap)
        assert by_output.index(expensive) < by_output.index(cheap)

    def test_orders_by_model_name(self, test_db, test_org_id, three_priced_runs):
        gpt_run, alpha_run = three_priced_runs

        ordered = self._ordered_ids(test_db, test_org_id, "model", "asc")

        assert ordered.index(alpha_run) < ordered.index(gpt_run)

    def test_a_run_with_no_traces_sorts_last_either_way(
        self, test_db, test_org_id, three_priced_runs, db_test_configuration, db_user, db_status
    ):
        """nullslast: an unpriced run must not head a 'most expensive first' list."""
        from rhesis.backend.app.models.test_run import TestRun

        untraced = TestRun(
            name="no traces at all",
            user_id=db_user.id,
            organization_id=uuid.UUID(test_org_id),
            status_id=db_status.id,
            test_configuration_id=db_test_configuration.id,
            attributes={},
        )
        test_db.add(untraced)
        test_db.flush()

        descending = self._ordered_ids(test_db, test_org_id, "total_cost_usd", "desc")
        ascending = self._ordered_ids(test_db, test_org_id, "total_cost_usd", "asc")

        assert descending[-1] == str(untraced.id)
        assert ascending[-1] == str(untraced.id)

    def test_the_sort_covers_runs_outside_the_first_page(
        self, test_db, test_org_id, three_priced_runs
    ):
        """The whole point: page one of a cost sort is the top of the org, not of a page.

        The expensive run is the oldest here, so a sort that only reordered the default
        newest-first page would leave it out of a one-row page entirely.
        """
        _, expensive = three_priced_runs

        first_page = get_test_runs(
            test_db,
            skip=0,
            limit=1,
            sort_by="total_cost_usd",
            sort_order="desc",
            organization_id=test_org_id,
        )

        assert [str(run.id) for run in first_page] == [expensive]


@pytest.mark.integration
class TestUnpricedRunsSortConsistently:
    """A run whose traces carry no cost must sort the same way in every cost column.

    cost_usd is read straight off the enrichment blob and is NULL for a trace nothing has
    priced, while the input/output halves go through enriched_cost_expr, which ends at
    zero. Left alone, the same run sorts last by Cost and among the zeros by Input cost --
    two columns on one row disagreeing about whether it is "unknown" or "nothing".
    """

    @pytest.fixture
    def three_runs(
        self,
        test_db,
        db_project,
        test_org_id,
        db_test_run,
        db_test_run_running,
        db_test_configuration,
        db_user,
        db_status,
    ):
        """A priced run, a traced-but-unpriced run, and a run with no traces at all.

        The untraced run is given the lowest possible id on purpose. Ordering falls back
        to id for ties, so while the unpriced run's cost is NULL it lands *below* the
        untraced one -- which is what makes the assertions below fail without the fix
        rather than pass on whichever UUID happened to be generated.
        """
        from rhesis.backend.app.models.test_run import TestRun

        project_id = str(db_project.id)
        unpriced, priced = db_test_run, db_test_run_running

        trace_id = uuid.uuid4().hex
        create_trace_spans(
            test_db,
            [run_root_span(trace_id, project_id, unpriced.id)],
            organization_id=test_org_id,
        )  # deliberately not marked processed: no enrichment blob at all

        trace_for_run(
            test_db,
            project_id,
            priced.id,
            test_org_id,
            model="gpt-4",
            tokens=(100, 50),
            costs=(0.01, 0.005),
        )

        untraced = TestRun(
            id=uuid.UUID(int=0),
            name="no traces at all",
            user_id=db_user.id,
            organization_id=uuid.UUID(test_org_id),
            status_id=db_status.id,
            test_configuration_id=db_test_configuration.id,
            attributes={},
        )
        test_db.add(untraced)
        test_db.flush()
        return str(unpriced.id), str(priced.id), str(untraced.id)

    def _ordered_ids(self, db, org_id, sort_by, sort_order):
        runs = get_test_runs(
            db, skip=0, limit=100, sort_by=sort_by, sort_order=sort_order, organization_id=org_id
        )
        return [str(run.id) for run in runs]

    def test_every_cost_column_agrees_on_where_an_unpriced_run_goes(
        self, test_db, test_org_id, three_runs
    ):
        unpriced, _, _ = three_runs

        positions = {
            field: self._ordered_ids(test_db, test_org_id, field, "desc").index(unpriced)
            for field in ("total_cost_usd", "total_input_cost_usd", "total_output_cost_usd")
        }

        assert len(set(positions.values())) == 1, (
            f"the same run lands in different places per cost column: {positions}"
        )

    def test_a_run_with_traces_outranks_one_with_none(self, test_db, test_org_id, three_runs):
        """Zero is a number; no traces at all is not. The first must sort above it."""
        unpriced, _, untraced = three_runs

        ordered = self._ordered_ids(test_db, test_org_id, "total_cost_usd", "desc")

        assert ordered.index(unpriced) < ordered.index(untraced)
