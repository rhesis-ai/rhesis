"""Integration tests for the Trace and Span entities.

These cover what unit tests cannot: that the field names, the two ids and the
filters match what the live routes actually return. Traces are ingested through
the OTEL route, which is the only way one comes into being.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from rhesis.sdk.clients import APIClient, Endpoints, Methods
from rhesis.sdk.entities.trace import Spans, Trace, Traces

TEST_PROJECT_ID = "12340000-0000-4000-8000-000000001234"


def ingest_trace(
    *,
    root_name: str,
    conversation_id=None,
    duration_ms: int = 1200,
    root_status: str = "OK",
) -> str:
    """Record one two-span trace and return its OpenTelemetry trace id.

    A root server span with one failing LLM call underneath it, which is the
    shape the span-level assertions need.
    """
    client = APIClient()
    trace_id = uuid.uuid4().hex
    root_span_id = uuid.uuid4().hex[:16]
    child_span_id = uuid.uuid4().hex[:16]
    start = datetime.now(timezone.utc) - timedelta(seconds=5)

    def span(span_id, name, kind, offset, length, status, parent=None):
        return {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent,
            "project_id": TEST_PROJECT_ID,
            "environment": "development",
            "conversation_id": conversation_id,
            "span_name": name,
            "span_kind": kind,
            "start_time": (start + timedelta(milliseconds=offset)).isoformat(),
            "end_time": (start + timedelta(milliseconds=offset + length)).isoformat(),
            "status_code": status,
            "attributes": {"rhesis.conversation.input": "What is the refund window?"},
        }

    client.send_request(
        Endpoints.TELEMETRY_TRACES,
        Methods.POST,
        data={
            "spans": [
                span(root_span_id, root_name, "SERVER", 0, duration_ms, root_status),
                span(
                    child_span_id,
                    "ai.llm.invoke",
                    "CLIENT",
                    50,
                    duration_ms - 100,
                    "ERROR",
                    parent=root_span_id,
                ),
            ]
        },
    )
    return trace_id


@pytest.fixture(scope="module")
def verdict_statuses(docker_compose_test_env):
    """Seed the Pass/Fail statuses an annotation's verdict points at.

    The test organization is created with raw SQL, so it never went through the
    seeding that gives a real organization its statuses.
    """
    client = APIClient()
    existing = {
        row["name"]: row["id"]
        for row in client.send_request(
            Endpoints.STATUSES, Methods.GET, params={"entity_type": "TestResult"}
        )
        or []
    }
    if "Pass" in existing and "Fail" in existing:
        return existing

    entity_type = client.send_request(
        Endpoints.TYPE_LOOKUPS,
        Methods.POST,
        data={"type_name": "EntityType", "type_value": "TestResult"},
    )
    for name in ("Pass", "Fail"):
        if name not in existing:
            created = client.send_request(
                Endpoints.STATUSES,
                Methods.POST,
                data={"name": name, "entity_type_id": entity_type["id"]},
            )
            existing[name] = created["id"]
    return existing


@pytest.fixture
def unique_name():
    """A root span name unique to one test, since traces are never truncated.

    The ingest route validates span names against the ``ai.<domain>.<action>``
    and ``function.<name>`` convention, so the unique part goes in the name.
    """
    return f"function.probe_{uuid.uuid4().hex[:12]}"


class TestListingAndDetail:
    def test_a_listed_trace_carries_the_fields_the_model_declares(self, unique_name):
        ingest_trace(root_name=unique_name)

        found = Traces.query(project_id=TEST_PROJECT_ID, span_name=unique_name)

        assert len(found) == 1
        trace = found[0]
        assert trace.root_operation == unique_name
        assert trace.environment == "development"
        assert trace.span_count == 2
        assert trace.duration_ms == 1200.0
        assert trace.status_code == "OK"
        assert trace.conversation_input == "What is the refund window?"
        assert trace.project_id == TEST_PROJECT_ID
        # A listing carries no spans at all, which is what db_id has to work around.
        assert trace.root_spans == []

    def test_the_detail_carries_the_span_tree(self, unique_name):
        trace_id = ingest_trace(root_name=unique_name)

        trace = Traces.pull(trace_id, project_id=TEST_PROJECT_ID)

        assert trace.trace_id == trace_id
        assert trace.span_count == 2
        assert trace.error_count == 1
        assert [span.span_name for span in trace.spans()] == [unique_name, "ai.llm.invoke"]
        # Filled in from the root span, which is the only place the detail route
        # says either of them.
        assert trace.root_operation == unique_name
        assert trace.status_code == "OK"

    def test_a_named_span_is_found_in_the_tree(self, unique_name):
        trace_id = ingest_trace(root_name=unique_name)

        span = Traces.pull(trace_id, project_id=TEST_PROJECT_ID).span("ai.llm.invoke")

        assert span is not None
        assert span.span_kind == "CLIENT"
        assert span.status_code == "ERROR"
        assert span.id is not None

    def test_pull_without_a_project_says_so(self, unique_name, monkeypatch):
        monkeypatch.delenv("RHESIS_PROJECT_ID", raising=False)
        trace_id = ingest_trace(root_name=unique_name)

        with pytest.raises(ValueError, match="RHESIS_PROJECT_ID"):
            Trace(trace_id=trace_id).spans()


class TestTheTwoIds:
    """The row id is never in a listing, and only the row id addresses a trace."""

    def test_a_listed_trace_resolves_its_row_id(self, unique_name):
        trace_id = ingest_trace(root_name=unique_name)

        listed = Traces.query(project_id=TEST_PROJECT_ID, span_name=unique_name)[0]
        detail = Traces.pull(trace_id, project_id=TEST_PROJECT_ID)

        assert listed.db_id == detail.root_spans[0].id
        assert listed.db_id != trace_id

    def test_a_row_id_resolves_back_to_its_trace(self, unique_name):
        trace_id = ingest_trace(root_name=unique_name)
        row_id = Traces.pull(trace_id, project_id=TEST_PROJECT_ID).db_id

        resolved = Spans.lookup(row_id)

        assert resolved["trace_id"] == trace_id
        assert resolved["project_id"] == TEST_PROJECT_ID
        assert Spans.trace_for(row_id).trace_id == trace_id

    def test_a_child_span_is_reachable_by_its_own_row_id(self, unique_name):
        """Spans.pull walks the tree, so a span that is not the root still resolves."""
        trace_id = ingest_trace(root_name=unique_name)
        child = Traces.pull(trace_id, project_id=TEST_PROJECT_ID).span("ai.llm.invoke")

        span = Spans.pull(child.id)

        assert span.id == child.id
        assert span.span_name == "ai.llm.invoke"

    def test_a_row_id_that_names_nothing_does_not_exist(self):
        assert Spans.exists(str(uuid.uuid4())) is False


class TestFilters:
    """A wrong parameter name would be ignored server-side rather than refused,
    so each one is checked against a trace it should and should not match."""

    def test_root_spans_only_false_returns_every_span(self, unique_name):
        trace_id = ingest_trace(root_name=unique_name)

        roots = Traces.query(project_id=TEST_PROJECT_ID, search=trace_id)
        every = Traces.query(project_id=TEST_PROJECT_ID, search=trace_id, root_spans_only=False)

        # The falsy-filter case, against the real route: dropping the False as
        # "not passed" would silently return one row instead of two.
        assert len(roots) == 1
        assert len(every) == 2
        assert {t.root_operation for t in every} == {unique_name, "ai.llm.invoke"}

    def test_status_code_matches_the_failing_span(self, unique_name):
        trace_id = ingest_trace(root_name=unique_name)

        failing = Traces.query(
            project_id=TEST_PROJECT_ID,
            search=trace_id,
            root_spans_only=False,
            status_code="ERROR",
        )

        assert [t.root_operation for t in failing] == ["ai.llm.invoke"]

    def test_a_duration_range_excludes_a_faster_trace(self, unique_name):
        slow = ingest_trace(root_name=unique_name, duration_ms=4000)
        ingest_trace(root_name=unique_name, duration_ms=100)

        found = Traces.query(
            project_id=TEST_PROJECT_ID, span_name=unique_name, duration_min_ms=2000
        )

        assert [t.trace_id for t in found] == [slow]

    def test_a_zero_minimum_keeps_everything(self, unique_name):
        ingest_trace(root_name=unique_name, duration_ms=100)

        found = Traces.query(project_id=TEST_PROJECT_ID, span_name=unique_name, duration_min_ms=0)

        # The other falsy filter: 0 must reach the route as a real bound.
        assert len(found) == 1

    def test_a_time_range_excludes_what_is_outside_it(self, unique_name):
        ingest_trace(root_name=unique_name)
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)

        assert (
            Traces.query(
                project_id=TEST_PROJECT_ID, span_name=unique_name, start_time_after=tomorrow
            )
            == []
        )
        assert (
            len(
                Traces.query(
                    project_id=TEST_PROJECT_ID,
                    span_name=unique_name,
                    start_time_before=tomorrow,
                )
            )
            == 1
        )

    def test_a_conversation_is_reachable_by_its_id(self, unique_name):
        conversation_id = str(uuid.uuid4())
        ingest_trace(root_name=unique_name, conversation_id=conversation_id)
        ingest_trace(root_name=unique_name)

        found = Traces.for_conversation(conversation_id)

        assert [t.conversation_id for t in found] == [conversation_id]

    def test_an_environment_that_matches_nothing_is_empty(self, unique_name):
        ingest_trace(root_name=unique_name)

        assert (
            Traces.query(
                project_id=TEST_PROJECT_ID, span_name=unique_name, environment="production"
            )
            == []
        )

    def test_slower_than_sorts_and_filters(self, unique_name):
        ingest_trace(root_name=unique_name, duration_ms=3000)
        ingest_trace(root_name=unique_name, duration_ms=5000)
        ingest_trace(root_name=unique_name, duration_ms=100)

        found = Traces.slower_than(1000, span_name=unique_name, project_id=TEST_PROJECT_ID)

        assert [t.duration_ms for t in found] == [5000.0, 3000.0]

    def test_providers_is_a_list_the_filter_would_accept(self):
        assert isinstance(Traces.providers(project_id=TEST_PROJECT_ID), list)


class TestPaging:
    def test_a_limit_stops_early_and_no_limit_reads_everything(self, unique_name):
        for _ in range(3):
            ingest_trace(root_name=unique_name)

        capped = Traces.query(project_id=TEST_PROJECT_ID, span_name=unique_name, limit=2)
        everything = Traces.query(project_id=TEST_PROJECT_ID, span_name=unique_name)

        assert len(capped) == 2
        assert len(everything) == 3

    def test_reads_past_a_page_smaller_than_the_result_set(self, unique_name, monkeypatch):
        """Ingesting a hundred traces to cross the real page size would be slow,
        so the page size is lowered instead. The walk is the thing under test."""
        from rhesis.sdk.entities import trace as trace_module

        for _ in range(3):
            ingest_trace(root_name=unique_name)
        monkeypatch.setattr(trace_module, "_PAGE_SIZE", 2)

        found = Traces.query(project_id=TEST_PROJECT_ID, span_name=unique_name)

        assert len(found) == 3

    def test_first_returns_one_trace(self, unique_name):
        ingest_trace(root_name=unique_name)

        assert Traces.first() is not None


class TestAnnotating:
    def test_annotating_a_trace_overrides_its_verdict(self, unique_name, verdict_statuses):
        trace_id = ingest_trace(root_name=unique_name)
        trace = Traces.pull(trace_id, project_id=TEST_PROJECT_ID)
        assert trace.verdict is None

        annotation = trace.annotate("fail", "Answered from the wrong document.")

        assert annotation.id is not None
        # Addressed by the row id: the hex would have been a 404 or, worse, a
        # different entity entirely.
        assert annotation.entity_id == trace.db_id
        after = Traces.pull(trace_id, project_id=TEST_PROJECT_ID)
        assert after.verdict == "fail"
        assert after.last_annotation["comments"] == "Answered from the wrong document."

    def test_a_trace_reads_back_its_own_annotations(self, unique_name, verdict_statuses):
        trace_id = ingest_trace(root_name=unique_name)
        trace = Traces.pull(trace_id, project_id=TEST_PROJECT_ID)
        trace.annotate("fail", "Wrong document.")

        found = trace.get_annotations()

        assert [a.comments for a in found] == ["Wrong document."]
        assert found[0].status.name == "Fail"

    def test_one_span_can_be_annotated_on_its_own(self, unique_name, verdict_statuses):
        trace_id = ingest_trace(root_name=unique_name)
        span = Traces.pull(trace_id, project_id=TEST_PROJECT_ID).span("ai.llm.invoke")

        span.annotate("fail", "Ignored the retrieved context.")

        assert [a.comments for a in span.get_annotations()] == ["Ignored the retrieved context."]

    def test_a_metric_can_be_targeted(self, unique_name, verdict_statuses):
        trace_id = ingest_trace(root_name=unique_name)
        trace = Traces.pull(trace_id, project_id=TEST_PROJECT_ID)

        trace.annotate("pass", "Grounded after all.", metric="Groundedness")

        annotation = trace.get_annotations()[0]
        assert annotation.target_type == "metric"
        assert annotation.target_reference == "Groundedness"

    def test_a_turn_reference_is_normalised_on_the_way_in(self, unique_name, verdict_statuses):
        trace_id = ingest_trace(root_name=unique_name)
        trace = Traces.pull(trace_id, project_id=TEST_PROJECT_ID)

        trace.annotate("fail", "Off script.", turn=2)

        annotation = trace.get_annotations()[0]
        # "2" would have become a second entry for the same turn in
        # annotation_summary, and the override would have applied either way.
        assert annotation.target_reference == "Turn 2"


class TestTracesAreNotWritable:
    def test_push_and_delete_point_at_the_instrumentation(self, unique_name):
        trace_id = ingest_trace(root_name=unique_name)
        trace = Traces.pull(trace_id, project_id=TEST_PROJECT_ID)

        with pytest.raises(NotImplementedError, match="rhesis.sdk.telemetry"):
            trace.push()
        with pytest.raises(NotImplementedError, match="rhesis.sdk.telemetry"):
            trace.delete()

    def test_all_refuses_an_odata_filter(self):
        with pytest.raises(ValueError, match="Traces.query"):
            Traces.all(filter="status_code eq 'ERROR'")
