"""trace.agent_path and trace.is_root, kept at ingest and on span moves.

``agent_path`` must name exactly the agents the SDK's tree walk (``targets._walk``) puts
around a span, since ``within`` matches on it in SQL; ``is_root`` must mark exactly the roots
of the SDK's span tree, since turns and runs are read from them. The migration's backfill
carries its own copy of the SQL, so it is held to the same traces.
"""

import importlib.util
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.schemas import SpanKind, StatusCode

from rhesis.backend.app import models
from rhesis.backend.app.constants import REPORTED_SPAN_SOURCE, AISpanAttributes
from rhesis.backend.app.crud.telemetry import (
    create_trace_spans,
    get_trace_by_id,
    move_spans_to_trace,
)
from rhesis.backend.app.schemas.telemetry import OTELSpanCreate
from rhesis.backend.app.services.telemetry.evaluation_trace import _from_rows, _trace
from rhesis.sdk.metrics.targets import _walk

BASE_TIME = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)

_MIGRATION_PATH = (
    Path(__file__).parents[3]
    / "apps/backend/src/rhesis/backend/alembic/versions/1924e6ab1c6f_add_trace_agent_path.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("agent_path_migration", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _span(trace_id, project_id, span_id, name, *, parent=None, offset_s=0, **attributes):
    start = BASE_TIME + timedelta(seconds=offset_s)
    return OTELSpanCreate(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent,
        project_id=project_id,
        environment="development",
        span_name=name,
        span_kind=SpanKind.INTERNAL,
        start_time=start,
        end_time=start + timedelta(seconds=1),
        status_code=StatusCode.OK,
        attributes=attributes,
    )


def _agent(trace_id, project_id, span_id, name, *, agent=None, **kwargs):
    attributes = {AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_AGENT_INVOKE}
    if agent is not None:
        attributes[AIAttributes.AGENT_NAME] = agent
    return _span(trace_id, project_id, span_id, name, **attributes, **kwargs)


def _tool(trace_id, project_id, span_id, tool, **kwargs):
    attributes = {
        AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_TOOL_INVOKE,
        AIAttributes.TOOL_NAME: tool,
    }
    return _span(trace_id, project_id, span_id, "ai.tool.invoke", **attributes, **kwargs)


def _sid() -> str:
    return uuid.uuid4().hex[:16]


def _paths(db, trace_id) -> dict:
    rows = db.execute(
        sa.select(models.Trace.span_id, models.Trace.agent_path).where(
            models.Trace.trace_id == trace_id
        )
    ).all()
    return {row.span_id: row.agent_path for row in rows}


def _roots(db, trace_id) -> dict:
    rows = db.execute(
        sa.select(models.Trace.span_id, models.Trace.is_root).where(
            models.Trace.trace_id == trace_id
        )
    ).all()
    return {row.span_id: row.is_root for row in rows}


def _stored(db, *trace_ids) -> dict:
    return {trace_id: (_paths(db, trace_id), _roots(db, trace_id)) for trace_id in trace_ids}


@pytest.fixture
def project_id(db_project):
    return str(db_project.id)


@pytest.fixture
def nested_trace(test_db, test_org_id, project_id):
    """Agents inside agents, a handoff through a tool, reported spans and odd names.

    planner (root)
      llm
      function.researcher (agent span with no agent name)
        search (tool)
          billing_agent (handed off to, inside the tool)
            issue_refund (tool)
            issue_refund (reported)
      handoff_to_support (agent span whose ai.tool.name outranks ai.agent.name)
        llm
      function.numbered (agent span with a non-string agent name)
        lookup (tool)
    orphan (its parent is never stored)
    planner (a second root, the next turn)
      reply (reported tool)
    """
    trace_id = uuid.uuid4().hex
    ids = {key: _sid() for key in ("planner", "llm", "researcher", "search", "billing")}
    ids |= {key: _sid() for key in ("refund", "reported_refund", "support", "support_llm")}
    ids |= {key: _sid() for key in ("numbered", "lookup", "orphan", "planner2", "reply")}
    t, p = trace_id, project_id
    llm_attrs = {
        AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
        AIAttributes.MODEL_NAME: "gpt-4o",
    }
    reported = {AISpanAttributes.SPAN_SOURCE: REPORTED_SPAN_SOURCE}
    spans = [
        _agent(t, p, ids["planner"], "ai.agent.invoke", agent="planner"),
        _span(t, p, ids["llm"], "ai.llm.invoke", parent=ids["planner"], offset_s=1, **llm_attrs),
        _agent(t, p, ids["researcher"], "function.researcher", parent=ids["planner"], offset_s=2),
        _tool(t, p, ids["search"], "search", parent=ids["researcher"], offset_s=3),
        _agent(
            t, p, ids["billing"], "ai.agent.invoke", agent="billing_agent", parent=ids["search"]
        ),
        _tool(t, p, ids["refund"], "issue_refund", parent=ids["billing"], offset_s=4),
        _span(
            t,
            p,
            ids["reported_refund"],
            "ai.tool.invoke",
            parent=ids["billing"],
            offset_s=5,
            **{
                AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_TOOL_INVOKE,
                AIAttributes.TOOL_NAME: "issue_refund",
                **reported,
            },
        ),
        _span(
            t,
            p,
            ids["support"],
            "ai.agent.invoke",
            parent=ids["planner"],
            offset_s=6,
            **{
                AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_AGENT_INVOKE,
                AIAttributes.AGENT_NAME: "support",
                AIAttributes.TOOL_NAME: "handoff_to_support",
            },
        ),
        _span(t, p, ids["support_llm"], "ai.llm.invoke", parent=ids["support"], **llm_attrs),
        _agent(
            t, p, ids["numbered"], "function.numbered", agent=7, parent=ids["planner"], offset_s=7
        ),
        _tool(t, p, ids["lookup"], "lookup", parent=ids["numbered"], offset_s=8),
        _tool(t, p, ids["orphan"], "orphan", parent=_sid(), offset_s=9),
        _agent(t, p, ids["planner2"], "ai.agent.invoke", agent="planner", offset_s=10),
        _span(
            t,
            p,
            ids["reply"],
            "ai.tool.invoke",
            parent=ids["planner2"],
            offset_s=11,
            **{AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_TOOL_INVOKE, **reported},
        ),
    ]
    create_trace_spans(test_db, spans, organization_id=test_org_id)
    return trace_id, ids


@pytest.mark.integration
class TestIngest:
    def test_fills_paths(self, test_db, nested_trace):
        trace_id, ids = nested_trace

        paths = _paths(test_db, trace_id)

        assert paths[ids["planner"]] == []
        assert paths[ids["llm"]] == ["planner"]
        assert paths[ids["researcher"]] == ["planner"]
        assert paths[ids["search"]] == ["planner", "function.researcher"]
        assert paths[ids["billing"]] == ["planner", "function.researcher"]
        assert paths[ids["refund"]] == ["planner", "function.researcher", "billing_agent"]
        assert paths[ids["reported_refund"]] == ["planner", "function.researcher", "billing_agent"]
        assert paths[ids["support_llm"]] == ["planner", "handoff_to_support"]
        assert paths[ids["lookup"]] == ["planner", "function.numbered"]
        assert paths[ids["orphan"]] == []
        assert paths[ids["reply"]] == ["planner"]

    def test_marks_roots(self, test_db, nested_trace):
        trace_id, ids = nested_trace

        roots = _roots(test_db, trace_id)

        assert {span_id for span_id, is_root in roots.items() if is_root} == {
            ids["planner"],
            ids["orphan"],
            ids["planner2"],
        }
        assert None not in roots.values()

    def test_child_stored_before_its_parent(self, test_db, test_org_id, project_id):
        trace_id = uuid.uuid4().hex
        root, agent, tool = _sid(), _sid(), _sid()
        create_trace_spans(
            test_db,
            [_tool(trace_id, project_id, tool, "issue_refund", parent=agent, offset_s=2)],
            organization_id=test_org_id,
        )
        assert _paths(test_db, trace_id) == {tool: []}
        assert _roots(test_db, trace_id) == {tool: True}

        create_trace_spans(
            test_db,
            [_agent(trace_id, project_id, agent, "ai.agent.invoke", agent="billing", parent=root)],
            organization_id=test_org_id,
        )
        assert _paths(test_db, trace_id) == {agent: [], tool: ["billing"]}
        assert _roots(test_db, trace_id) == {agent: True, tool: False}

        create_trace_spans(
            test_db,
            [_agent(trace_id, project_id, root, "ai.agent.invoke", agent="planner")],
            organization_id=test_org_id,
        )
        assert _paths(test_db, trace_id) == {
            root: [],
            agent: ["planner"],
            tool: ["planner", "billing"],
        }
        assert _roots(test_db, trace_id) == {root: True, agent: False, tool: False}


@pytest.mark.integration
class TestMatchesSdkWalk:
    def test_column_equals_the_sdk_walk(self, test_db, test_org_id, project_id, nested_trace):
        trace_id, _ = nested_trace
        rows = get_trace_by_id(test_db, trace_id, project_id, test_org_id)
        trace = _trace(trace_id, project_id, _from_rows(rows))

        walked = {span.id: list(agents) for span, agents in _walk(trace.root_spans)}
        stored = {str(row.id): row.agent_path for row in rows}

        assert len(walked) == len(rows)
        assert stored == walked

    def test_roots_equal_the_sdk_tree(self, test_db, test_org_id, project_id, nested_trace):
        trace_id, _ = nested_trace
        rows = get_trace_by_id(test_db, trace_id, project_id, test_org_id)
        trace = _trace(trace_id, project_id, _from_rows(rows))

        assert {str(row.id) for row in rows if row.is_root} == {
            span.id for span in trace.root_spans
        }


@pytest.mark.integration
class TestMoves:
    def test_moved_spans_take_the_target_trace_paths(self, test_db, test_org_id, project_id):
        target, source = uuid.uuid4().hex, uuid.uuid4().hex
        planner, tool, inner = _sid(), _sid(), _sid()
        create_trace_spans(
            test_db,
            [_agent(target, project_id, planner, "ai.agent.invoke", agent="planner")],
            organization_id=test_org_id,
        )
        # Its parent lives in the other trace, so until the move it is a root.
        create_trace_spans(
            test_db,
            [
                _agent(
                    source, project_id, tool, "ai.agent.invoke", agent="billing", parent=planner
                ),
                _tool(source, project_id, inner, "issue_refund", parent=tool, offset_s=1),
            ],
            organization_id=test_org_id,
        )
        assert _paths(test_db, source) == {tool: [], inner: ["billing"]}
        assert _roots(test_db, source) == {tool: True, inner: False}

        move_spans_to_trace(test_db, source, target, None, AISpanAttributes.SOURCE_TRACE_ID)

        assert _paths(test_db, source) == {}
        assert _paths(test_db, target) == {
            planner: [],
            tool: ["planner"],
            inner: ["planner", "billing"],
        }
        assert _roots(test_db, target) == {planner: True, tool: False, inner: False}


@pytest.mark.integration
class TestBackfill:
    def test_batches_fill_what_ingest_would(self, test_db, test_org_id, project_id, nested_trace):
        trace_id, _ = nested_trace
        other = uuid.uuid4().hex
        planner, tool = _sid(), _sid()
        create_trace_spans(
            test_db,
            [
                _agent(other, project_id, planner, "ai.agent.invoke", agent="planner"),
                _tool(other, project_id, tool, "lookup", parent=planner, offset_s=1),
            ],
            organization_id=test_org_id,
        )
        expected = _stored(test_db, trace_id, other)
        # One trace lacks both values; the other only its roots, as after a partial backfill.
        test_db.execute(
            sa.update(models.Trace)
            .where(models.Trace.trace_id == trace_id)
            .values(agent_path=None, is_root=None)
        )
        test_db.execute(
            sa.update(models.Trace).where(models.Trace.trace_id == other).values(is_root=None)
        )

        written = _load_migration()._backfill_scope(
            test_db.connection(), test_org_id, project_id, batch_size=1
        )

        assert written == sum(len(paths) for paths, _ in expected.values())
        assert _stored(test_db, trace_id, other) == expected
