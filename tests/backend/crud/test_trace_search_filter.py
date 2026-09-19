"""Tests for the traces `search` filter, and what it does to `span_name`.

Two behaviours the MCP tool descriptions promise, pinned here rather than in
prose. `search` collects the trace ids whose spans match and then returns those
whole traces, so it reaches inside a trace in a way the row-level filters do
not. And `span_name` is applied in an ``elif``, so passing both silently drops
it -- an agent narrowing a search to one operation gets a wider answer than it
asked for, with no error to notice.

If either is ever changed, the tool descriptions in mcp_tools.yaml and the
`list_traces` entry in skills/rhesis/references/tool-catalog.md say the old
behaviour and need updating with it.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from rhesis.telemetry.schemas import SpanKind, StatusCode

from rhesis.backend.app.crud.telemetry import create_trace_spans, query_traces
from rhesis.backend.app.schemas.telemetry import OTELSpanCreate

ROOT_NAME = "function.handle_request"
CHILD_NAME = "ai.llm.invoke"
ERROR_TEXT = "upstream refused the connection"


def span(trace_id, project_id, name, *, parent=None, status=StatusCode.OK, message=None):
    now = datetime.now(timezone.utc)
    return OTELSpanCreate(
        trace_id=trace_id,
        span_id=uuid.uuid4().hex[:16],
        parent_span_id=parent,
        project_id=project_id,
        environment="development",
        span_name=name,
        span_kind=SpanKind.SERVER if parent is None else SpanKind.CLIENT,
        start_time=now,
        end_time=now + timedelta(seconds=1),
        status_code=status,
        status_message=message,
        attributes={},
    )


@pytest.fixture
def trace_with_a_failing_child(test_db, db_project, test_org_id):
    """A healthy root span over an LLM call that failed with a distinctive message."""
    project_id = str(db_project.id)
    trace_id = uuid.uuid4().hex
    root = span(trace_id, project_id, ROOT_NAME)
    child = span(
        trace_id,
        project_id,
        CHILD_NAME,
        parent=root.span_id,
        status=StatusCode.ERROR,
        message=ERROR_TEXT,
    )
    create_trace_spans(test_db, [root, child], organization_id=test_org_id)
    return project_id, trace_id


def found(db, org_id, project_id, **kwargs):
    rows = query_traces(db, organization_id=org_id, project_id=project_id, limit=100, **kwargs)
    return {row.trace.trace_id for row in rows}


@pytest.mark.integration
class TestSearchReachesInsideATrace:
    def test_an_error_message_on_a_child_span_finds_the_whole_trace(
        self, test_db, test_org_id, trace_with_a_failing_child
    ):
        """The default view is one row per trace, and the match is a child span.

        This is what makes search the tool for an error message: status_code
        tests the row, so it misses a trace whose root returned OK.
        """
        project_id, trace_id = trace_with_a_failing_child

        assert trace_id in found(test_db, test_org_id, project_id, search=ERROR_TEXT)

    def test_status_code_alone_misses_that_trace(
        self, test_db, test_org_id, trace_with_a_failing_child
    ):
        """The trap the tool description warns about, pinned."""
        project_id, trace_id = trace_with_a_failing_child

        roots_only = found(test_db, test_org_id, project_id, status_code="ERROR")
        every_span = found(
            test_db, test_org_id, project_id, status_code="ERROR", root_spans_only=False
        )

        assert trace_id not in roots_only
        assert trace_id in every_span


@pytest.mark.integration
class TestSearchOverridesSpanName:
    def test_span_name_alone_narrows(self, test_db, test_org_id, trace_with_a_failing_child):
        """Establishes that span_name does filter, so the next test means something."""
        project_id, trace_id = trace_with_a_failing_child

        assert trace_id in found(test_db, test_org_id, project_id, span_name=ROOT_NAME)
        assert trace_id not in found(test_db, test_org_id, project_id, span_name="function.absent")

    def test_passing_both_drops_span_name(self, test_db, test_org_id, trace_with_a_failing_child):
        """span_name is an elif, so search wins and the narrowing is lost.

        A caller combining them expects an AND and gets the search alone. The
        failure is silent: a wider result set, no error.
        """
        project_id, trace_id = trace_with_a_failing_child

        both = found(
            test_db, test_org_id, project_id, search=ERROR_TEXT, span_name="function.absent"
        )

        # span_name on its own excludes this trace; together with search it does not.
        assert trace_id in both
