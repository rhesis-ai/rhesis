"""Tests for the spans list and its facets (crud + service).

The trap these guard: test ids sit on root spans only, and multi-turn traces can have
roots without a conversation_id. Trace-level filters must still reach every child span.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.schemas import SpanKind, StatusCode

from rhesis.backend.app.constants import TestExecutionContext
from rhesis.backend.app.crud.project import create_project
from rhesis.backend.app.crud.telemetry import create_trace_spans, mark_trace_processed
from rhesis.backend.app.schemas.telemetry import (
    OTELSpanCreate,
    SpanFilters,
    TraceSource,
    TraceType,
)
from rhesis.backend.app.services.telemetry.span_list import get_span_facets, list_spans
from tests.backend.fixtures.rls import as_project

BASE_TIME = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def make_span(
    trace_id,
    project_id,
    *,
    name,
    parent=None,
    operation=None,
    offset_s=0,
    duration_s=1,
    model=None,
    provider=None,
    tokens=None,
    error=False,
    conversation_id=None,
    test_run_id=None,
    span_id=None,
):
    attributes = {}
    if operation:
        attributes[AIAttributes.OPERATION_TYPE] = operation
    if model:
        attributes[AIAttributes.MODEL_NAME] = model
    if provider:
        attributes[AIAttributes.MODEL_PROVIDER] = provider
    if tokens:
        attributes[AIAttributes.LLM_TOKENS_INPUT] = tokens[0]
        attributes[AIAttributes.LLM_TOKENS_OUTPUT] = tokens[1]
    if test_run_id:
        attributes[TestExecutionContext.SpanAttributes.TEST_RUN_ID] = str(test_run_id)
    start = BASE_TIME + timedelta(seconds=offset_s)
    return OTELSpanCreate(
        trace_id=trace_id,
        span_id=span_id or uuid.uuid4().hex[:16],
        parent_span_id=parent,
        project_id=project_id,
        environment="development",
        span_name=name,
        span_kind=SpanKind.INTERNAL,
        start_time=start,
        end_time=start + timedelta(seconds=duration_s),
        status_code=StatusCode.ERROR if error else StatusCode.OK,
        attributes=attributes,
        conversation_id=conversation_id,
    )


def priced(span_id, model, cost, provider=None):
    entry = {
        "span_id": span_id,
        "model_name": model,
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "total_cost_usd": cost,
    }
    if provider:
        entry["provider"] = provider
    return entry


def blob(*entries):
    return {
        "costs": {
            "total_cost_usd": sum(e["total_cost_usd"] for e in entries),
            "breakdown": list(entries),
        }
    }


@pytest.fixture
def agent_trace(test_db, db_project, test_org_id):
    """root agent -> (llm priced, tool, untyped function span), enriched."""
    project_id = str(db_project.id)
    trace_id = uuid.uuid4().hex
    root, llm, tool, func = (uuid.uuid4().hex[:16] for _ in range(4))
    create_trace_spans(
        test_db,
        [
            make_span(
                trace_id,
                project_id,
                name="ai.agent.invoke",
                operation="agent.invoke",
                span_id=root,
                duration_s=10,
            ),
            make_span(
                trace_id,
                project_id,
                name="ai.llm.invoke",
                operation="llm.invoke",
                parent=root,
                span_id=llm,
                offset_s=1,
                model="gpt-4",
                provider="openai",
                tokens=(100, 50),
                duration_s=3,
            ),
            make_span(
                trace_id,
                project_id,
                name="ai.tool.invoke",
                operation="tool.invoke",
                parent=root,
                span_id=tool,
                offset_s=2,
                error=True,
            ),
            make_span(
                trace_id,
                project_id,
                name="function.haystack.step",
                parent=root,
                span_id=func,
                offset_s=3,
                duration_s=5,
            ),
        ],
        organization_id=test_org_id,
    )
    mark_trace_processed(test_db, trace_id, blob(priced(llm, "gpt-4", 0.02)))
    return project_id, trace_id, {"root": root, "llm": llm, "tool": tool, "func": func}


def spans(db, org_id, project_id, filters=None, **kwargs):
    kwargs.setdefault("sort_by", None)
    kwargs.setdefault("sort_order", "desc")
    kwargs.setdefault("limit", 100)
    kwargs.setdefault("offset", 0)
    return list_spans(db, org_id, project_id, filters or SpanFilters(), **kwargs)


def ids(response):
    return {span.span_id for span in response.spans}


@pytest.mark.integration
class TestSpanRows:
    def test_one_row_per_span(self, test_db, test_org_id, agent_trace):
        project_id, _, span_ids = agent_trace

        response = spans(test_db, test_org_id, project_id)

        assert ids(response) == set(span_ids.values())
        assert response.total == 4

    def test_root_detection_and_trace_name(self, test_db, test_org_id, agent_trace):
        project_id, _, span_ids = agent_trace

        by_id = {s.span_id: s for s in spans(test_db, test_org_id, project_id).spans}

        assert by_id[span_ids["root"]].is_root
        assert not by_id[span_ids["tool"]].is_root
        assert {s.trace_name for s in by_id.values()} == {"ai.agent.invoke"}

    def test_span_types(self, test_db, test_org_id, agent_trace):
        project_id, _, span_ids = agent_trace

        by_id = {s.span_id: s for s in spans(test_db, test_org_id, project_id).spans}

        assert by_id[span_ids["llm"]].span_type == "llm.invoke"
        assert by_id[span_ids["func"]].span_type == "span"

    def test_cost_model_and_tokens_of_the_priced_span(self, test_db, test_org_id, agent_trace):
        project_id, _, span_ids = agent_trace

        by_id = {s.span_id: s for s in spans(test_db, test_org_id, project_id).spans}
        llm = by_id[span_ids["llm"]]

        assert llm.cost_usd == pytest.approx(0.02)
        assert llm.model == "gpt-4"
        assert llm.provider == "openai"
        assert (llm.input_tokens, llm.output_tokens, llm.total_tokens) == (100, 50, 150)

    def test_other_spans_have_no_cost_model_or_tokens(self, test_db, test_org_id, agent_trace):
        project_id, _, span_ids = agent_trace

        by_id = {s.span_id: s for s in spans(test_db, test_org_id, project_id).spans}
        tool = by_id[span_ids["tool"]]

        assert tool.cost_usd is None
        assert tool.model is None and tool.provider is None
        assert tool.total_tokens is None

    def test_unenriched_llm_span_uses_its_own_attributes(self, test_db, db_project, test_org_id):
        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        create_trace_spans(
            test_db,
            [
                make_span(
                    trace_id,
                    project_id,
                    name="ai.llm.invoke",
                    operation="llm.invoke",
                    model="claude-sonnet-4",
                    tokens=(7, 3),
                )
            ],
            organization_id=test_org_id,
        )

        (row,) = spans(test_db, test_org_id, project_id).spans

        assert row.model == "claude-sonnet-4"
        assert row.cost_usd is None
        assert row.total_tokens == 10

    def test_breakdown_beats_a_stamped_provider(self, test_db, db_project, test_org_id):
        """The span stamps openai on a gemini call; the row follows the breakdown."""
        project_id = str(db_project.id)
        trace_id, llm = uuid.uuid4().hex, uuid.uuid4().hex[:16]
        create_trace_spans(
            test_db,
            [
                make_span(
                    trace_id,
                    project_id,
                    name="ai.llm.invoke",
                    operation="llm.invoke",
                    span_id=llm,
                    model="gemini-2.0-flash",
                    provider="openai",
                )
            ],
            organization_id=test_org_id,
        )
        mark_trace_processed(test_db, trace_id, blob(priced(llm, "gemini-2.0-flash", 0.01)))

        (row,) = spans(test_db, test_org_id, project_id).spans
        assert row.provider != "openai"
        assert (
            ids(spans(test_db, test_org_id, project_id, SpanFilters(providers=["openai"]))) == set()
        )
        assert ids(
            spans(test_db, test_org_id, project_id, SpanFilters(providers=[row.provider]))
        ) == {llm}


@pytest.mark.integration
class TestRowFilters:
    @pytest.mark.parametrize(
        "filters, expected",
        [
            (SpanFilters(span_types=["tool.invoke"]), {"tool"}),
            (SpanFilters(span_types=["tool.invoke", "span"]), {"tool", "func"}),
            (SpanFilters(span_names=["ai.llm.invoke"]), {"llm"}),
            (SpanFilters(search="HAYSTACK"), {"func"}),
            (SpanFilters(is_root=True), {"root"}),
            (SpanFilters(is_root=False), {"llm", "tool", "func"}),
            (SpanFilters(status_code="ERROR"), {"tool"}),
            (SpanFilters(duration_min_ms=4000), {"root", "func"}),
            (SpanFilters(duration_max_ms=1000), {"tool"}),
            (SpanFilters(start_time_after=BASE_TIME + timedelta(seconds=2)), {"tool", "func"}),
            (SpanFilters(start_time_before=BASE_TIME), {"root"}),
            (SpanFilters(models=["gpt-4"]), {"llm"}),
            (SpanFilters(providers=["openai"]), {"llm"}),
            (SpanFilters(environment="production"), set()),
        ],
    )
    def test_filter(self, test_db, test_org_id, agent_trace, filters, expected):
        project_id, _, span_ids = agent_trace

        response = spans(test_db, test_org_id, project_id, filters)

        assert ids(response) == {span_ids[key] for key in expected}
        assert response.total == len(expected)

    def test_search_escapes_like_wildcards(self, test_db, test_org_id, agent_trace):
        project_id, _, _ = agent_trace

        assert spans(test_db, test_org_id, project_id, SpanFilters(search="%")).total == 0


@pytest.mark.integration
class TestTraceLevelFilters:
    @pytest.fixture
    def run_and_chat(self, test_db, db_project, test_org_id, db_test_run):
        """A test-run trace (run id on the root only) and a two-turn chat trace
        whose first root has no conversation_id."""
        project_id = str(db_project.id)
        run_trace, run_root, run_child = (
            uuid.uuid4().hex,
            uuid.uuid4().hex[:16],
            uuid.uuid4().hex[:16],
        )
        chat_trace = uuid.uuid4().hex
        turn1, turn1_child, turn2 = (uuid.uuid4().hex[:16] for _ in range(3))
        create_trace_spans(
            test_db,
            [
                make_span(
                    run_trace,
                    project_id,
                    name="function.run_root",
                    span_id=run_root,
                    test_run_id=db_test_run.id,
                ),
                make_span(
                    run_trace,
                    project_id,
                    name="function.run_child",
                    span_id=run_child,
                    parent=run_root,
                    offset_s=1,
                ),
                make_span(chat_trace, project_id, name="function.chat_turn", span_id=turn1),
                make_span(
                    chat_trace,
                    project_id,
                    name="function.chat_step",
                    span_id=turn1_child,
                    parent=turn1,
                    offset_s=1,
                ),
                make_span(
                    chat_trace,
                    project_id,
                    name="function.chat_turn",
                    span_id=turn2,
                    offset_s=10,
                    conversation_id="conv-1",
                ),
            ],
            organization_id=test_org_id,
        )
        return (
            project_id,
            str(db_test_run.id),
            {
                "run": {run_root, run_child},
                "chat": {turn1, turn1_child, turn2},
            },
        )

    def test_test_run_reaches_child_spans(self, test_db, test_org_id, run_and_chat):
        project_id, run_id, traces = run_and_chat

        response = spans(test_db, test_org_id, project_id, SpanFilters(test_run_id=run_id))

        assert ids(response) == traces["run"]
        assert {s.test_run_id for s in response.spans} == {run_id}

    def test_trace_source(self, test_db, test_org_id, run_and_chat):
        project_id, _, traces = run_and_chat

        test = spans(test_db, test_org_id, project_id, SpanFilters(trace_source=TraceSource.TEST))
        operation = spans(
            test_db, test_org_id, project_id, SpanFilters(trace_source=TraceSource.OPERATION)
        )

        assert ids(test) == traces["run"]
        assert ids(operation) == traces["chat"]

    def test_trace_type_is_decided_per_trace(self, test_db, test_org_id, run_and_chat):
        project_id, _, traces = run_and_chat

        multi = spans(
            test_db, test_org_id, project_id, SpanFilters(trace_type=TraceType.MULTI_TURN)
        )
        single = spans(
            test_db, test_org_id, project_id, SpanFilters(trace_type=TraceType.SINGLE_TURN)
        )

        assert ids(multi) == traces["chat"]
        assert ids(single) == traces["run"]
        assert {s.conversation_id for s in multi.spans} == {"conv-1"}

    def test_trace_name_is_the_first_root(self, test_db, test_org_id, run_and_chat):
        project_id, _, traces = run_and_chat

        response = spans(
            test_db, test_org_id, project_id, SpanFilters(span_names=["function.chat_step"])
        )

        assert [s.trace_name for s in response.spans] == ["function.chat_turn"]

    def test_row_ids_agree_with_the_filter_when_the_first_root_has_none(
        self, test_db, db_project, test_org_id, db_test_run
    ):
        """Only the later root carries the run: the filter matches the whole trace, so
        every row must report the run too, not the first root's null."""
        project_id = str(db_project.id)
        trace_id, first, later = uuid.uuid4().hex, uuid.uuid4().hex[:16], uuid.uuid4().hex[:16]
        create_trace_spans(
            test_db,
            [
                make_span(trace_id, project_id, name="function.first_turn", span_id=first),
                make_span(
                    trace_id,
                    project_id,
                    name="function.later_turn",
                    span_id=later,
                    offset_s=10,
                    test_run_id=db_test_run.id,
                ),
            ],
            organization_id=test_org_id,
        )

        response = spans(
            test_db, test_org_id, project_id, SpanFilters(test_run_id=str(db_test_run.id))
        )

        assert ids(response) == {first, later}
        assert {s.test_run_id for s in response.spans} == {str(db_test_run.id)}
        assert {s.trace_name for s in response.spans} == {"function.first_turn"}


@pytest.mark.integration
class TestSorting:
    def test_cost_desc_puts_priced_spans_first(self, test_db, test_org_id, agent_trace):
        project_id, _, span_ids = agent_trace

        for order in ("desc", "asc"):
            response = spans(test_db, test_org_id, project_id, sort_by="cost_usd", sort_order=order)
            assert response.spans[0].span_id == span_ids["llm"]

    def test_duration(self, test_db, test_org_id, agent_trace):
        project_id, _, span_ids = agent_trace

        response = spans(test_db, test_org_id, project_id, sort_by="duration_ms", sort_order="desc")

        assert [s.span_id for s in response.spans][:2] == [span_ids["root"], span_ids["func"]]

    def test_default_is_newest_first(self, test_db, test_org_id, agent_trace):
        project_id, _, span_ids = agent_trace

        response = spans(test_db, test_org_id, project_id)

        assert response.spans[0].span_id == span_ids["func"]

    def test_name_and_tokens_sort(self, test_db, test_org_id, agent_trace):
        project_id, _, span_ids = agent_trace

        by_name = spans(test_db, test_org_id, project_id, sort_by="span_name", sort_order="asc")
        by_tokens = spans(test_db, test_org_id, project_id, sort_by="total_tokens")

        assert by_name.spans[0].span_name == "ai.agent.invoke"
        assert by_tokens.spans[0].span_id == span_ids["llm"]

    def test_pages_do_not_overlap(self, test_db, test_org_id, agent_trace):
        project_id, _, span_ids = agent_trace

        seen = []
        for offset in range(4):
            page = spans(
                test_db, test_org_id, project_id, sort_by="cost_usd", limit=1, offset=offset
            )
            assert page.total == 4
            seen += [s.span_id for s in page.spans]

        assert sorted(seen) == sorted(span_ids.values())

    def test_total_past_the_last_page(self, test_db, test_org_id, agent_trace):
        project_id, _, _ = agent_trace

        response = spans(test_db, test_org_id, project_id, offset=50)

        assert response.spans == [] and response.total == 4

    def test_unknown_sort_field_is_a_400(self, test_db, test_org_id, agent_trace):
        project_id, _, _ = agent_trace

        with pytest.raises(HTTPException) as error:
            spans(test_db, test_org_id, project_id, sort_by="attributes")
        assert error.value.status_code == 400


@pytest.mark.integration
class TestFacets:
    def facets(self, db, org_id, project_id, filters=None, name_limit=100):
        return get_span_facets(db, org_id, project_id, filters or SpanFilters(), name_limit)

    def test_counts(self, test_db, test_org_id, agent_trace):
        project_id, _, _ = agent_trace

        facets = self.facets(test_db, test_org_id, project_id)

        assert {f.value: f.count for f in facets.span_types} == {
            "agent.invoke": 1,
            "llm.invoke": 1,
            "tool.invoke": 1,
            "span": 1,
        }
        assert len(facets.span_names) == 4
        assert {f.value: f.count for f in facets.models} == {"gpt-4": 1}

    def test_each_facet_ignores_its_own_filter(self, test_db, test_org_id, agent_trace):
        project_id, _, _ = agent_trace

        facets = self.facets(
            test_db, test_org_id, project_id, SpanFilters(span_types=["tool.invoke"])
        )

        assert len(facets.span_types) == 4
        assert [f.value for f in facets.span_names] == ["ai.tool.invoke"]
        assert facets.models == []

    def test_other_filters_apply(self, test_db, test_org_id, agent_trace):
        project_id, _, _ = agent_trace

        facets = self.facets(test_db, test_org_id, project_id, SpanFilters(is_root=True))

        assert {f.value for f in facets.span_types} == {"agent.invoke"}

    def test_name_cap(self, test_db, test_org_id, agent_trace):
        project_id, _, _ = agent_trace

        facets = self.facets(test_db, test_org_id, project_id, name_limit=2)

        assert len(facets.span_names) == 2
        assert facets.span_names_truncated


@pytest.mark.integration
class TestProjectIsolation:
    def test_other_projects_spans_are_not_listed(
        self, test_db, test_org_id, authenticated_user_id, agent_trace
    ):
        project_id, _, span_ids = agent_trace
        other = create_project(
            test_db,
            {"name": f"Other {uuid.uuid4()}", "description": "isolation"},
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        other_trace = uuid.uuid4().hex
        with as_project(test_db, other.id):
            create_trace_spans(
                test_db,
                [
                    make_span(
                        other_trace, str(other.id), name="ai.tool.invoke", operation="tool.invoke"
                    )
                ],
                organization_id=test_org_id,
            )

        mine = spans(test_db, test_org_id, project_id)
        facets = get_span_facets(test_db, test_org_id, project_id, SpanFilters(), 100)

        assert ids(mine) == set(span_ids.values())
        assert sum(f.count for f in facets.span_types) == 4
