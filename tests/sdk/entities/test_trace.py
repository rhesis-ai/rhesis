import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from rhesis.sdk.entities import trace as trace_module
from rhesis.sdk.entities.trace import Span, Spans, Trace, Traces
from rhesis.sdk.errors import RhesisAPIError

os.environ["RHESIS_BASE_URL"] = "http://test:8000"

TRACE_ID = "a" * 32
ROOT_ROW_ID = "11111111-1111-1111-1111-111111111111"
LLM_ROW_ID = "22222222-2222-2222-2222-222222222222"
PROJECT_ID = "33333333-3333-3333-3333-333333333333"
STATUS_ID = "44444444-4444-4444-4444-444444444444"


def span_payload(row_id, name, children=None, **overrides):
    payload = {
        "id": row_id,
        "span_id": "b" * 16,
        "span_name": name,
        "span_kind": "SERVER",
        "start_time": "2026-09-01T10:00:00Z",
        "end_time": "2026-09-01T10:00:01Z",
        "duration_ms": 1000.0,
        "status_code": "OK",
        "status_message": None,
        "attributes": {},
        "events": [],
        "children": children or [],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def summary_payload():
    """One trace as the list route returns it: relations flat, no spans."""
    return {
        "trace_id": TRACE_ID,
        "project_id": PROJECT_ID,
        "environment": "development",
        "conversation_id": None,
        "conversation_input": "What is the refund window?",
        "start_time": "2026-09-01T10:00:00Z",
        "duration_ms": 1200.0,
        "span_count": 3,
        "root_operation": "ai.chat",
        "status_code": "OK",
        "has_errors": False,
        "total_tokens": 900,
        "total_cost_usd": 0.004,
        "models": ["gpt-4o"],
        "providers": ["openai"],
        "test_run_id": "run-1",
        "test_result_id": "result-1",
        "test_id": "test-1",
        "endpoint_id": "endpoint-1",
        "endpoint_name": "Support Chatbot",
        "trace_metrics_status": "Pass",
        "execution": "completed",
        "verdict": "pass",
        "has_annotations": False,
        "matches_annotation": True,
        "tags_count": 0,
        "comments_count": 0,
    }


@pytest.fixture
def detail_payload():
    """The same trace as the detail route returns it: relations nested, spans present."""
    return {
        "trace_id": TRACE_ID,
        "project_id": PROJECT_ID,
        "environment": "development",
        "start_time": "2026-09-01T10:00:00Z",
        "end_time": "2026-09-01T10:00:01Z",
        "duration_ms": 1200.0,
        "span_count": 2,
        "error_count": 1,
        "total_tokens": 900,
        "total_input_tokens": 700,
        "total_output_tokens": 200,
        "total_cost_usd": 0.004,
        "root_spans": [
            span_payload(
                ROOT_ROW_ID,
                "ai.chat",
                status_code="ERROR",
                children=[span_payload(LLM_ROW_ID, "ai.llm.invoke", span_kind="CLIENT")],
            )
        ],
        "project": {"id": PROJECT_ID, "name": "Support"},
        "endpoint": {"id": "endpoint-1", "name": "Support Chatbot", "connection_type": "REST"},
        "test_run": {"id": "run-1", "name": "witty-otter", "status": {"name": "Completed"}},
        "test_result": {"id": "result-1"},
        "test": {"id": "test-1"},
    }


class TestReadsBothResponseShapes:
    """One class has to absorb two payloads, which is where fields go missing."""

    def test_reads_a_listing_row(self, summary_payload):
        trace = Trace.model_validate(summary_payload)

        assert trace.trace_id == TRACE_ID
        assert trace.root_operation == "ai.chat"
        assert trace.span_count == 3
        assert trace.models == ["gpt-4o"]
        assert trace.total_cost_usd == 0.004
        assert trace.trace_metrics_status == "Pass"
        assert trace.conversation_input == "What is the refund window?"
        assert trace.tags_count == 0
        # Parsed, not left as a string, because time arithmetic is the point of a trace.
        assert trace.start_time == datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)

    def test_reads_a_detail_row(self, detail_payload):
        trace = Trace.model_validate(detail_payload)

        assert trace.error_count == 1
        assert trace.total_input_tokens == 700
        assert len(trace.root_spans) == 1
        assert trace.root_spans[0].children[0].span_name == "ai.llm.invoke"
        assert trace.test_run is not None
        assert trace.test_run.name == "witty-otter"

    def test_a_detail_row_gets_the_ids_a_listing_would_have_given(self, detail_payload):
        """The detail route returns the relations as objects and no ids at all, so
        without this every id is None on exactly the call that has the most data."""
        trace = Trace.model_validate(detail_payload)

        assert trace.endpoint_id == "endpoint-1"
        assert trace.endpoint_name == "Support Chatbot"
        assert trace.test_run_id == "run-1"
        assert trace.test_result_id == "result-1"
        assert trace.test_id == "test-1"
        assert trace.project_id == PROJECT_ID

    def test_a_detail_row_gets_the_root_operation_and_status(self, detail_payload):
        """Both are per-span on the detail route and top-level on a listing."""
        trace = Trace.model_validate(detail_payload)

        assert trace.root_operation == "ai.chat"
        assert trace.status_code == "ERROR"
        assert trace.has_errors is True

    def test_does_not_overwrite_what_the_payload_already_says(self, detail_payload):
        detail_payload["endpoint_id"] = "the-one-the-server-sent"
        detail_payload["has_errors"] = False

        trace = Trace.model_validate(detail_payload)

        assert trace.endpoint_id == "the-one-the-server-sent"
        assert trace.has_errors is False

    def test_has_errors_follows_the_root_span_not_the_span_count(self):
        """The list route defines has_errors as the root span's status, so the
        detail route has to mean the same thing by it.

        A trace whose inner LLM call failed under a root that returned OK is
        the common shape, and error_count is what reports that.
        """
        trace = Trace.model_validate(
            {
                "trace_id": TRACE_ID,
                "project_id": PROJECT_ID,
                "error_count": 1,
                "root_spans": [
                    span_payload(
                        ROOT_ROW_ID,
                        "ai.chat",
                        status_code="OK",
                        children=[
                            span_payload(LLM_ROW_ID, "ai.llm.invoke", status_code="ERROR")
                        ],
                    )
                ],
            }
        )

        assert trace.status_code == "OK"
        assert trace.has_errors is False
        assert trace.error_count == 1

    @patch("rhesis.sdk.entities.trace.APIClient")
    def test_has_errors_does_not_flip_when_the_detail_loads(self, mock_client, summary_payload):
        """Deriving it from error_count made the same attribute mean one thing
        on a listed trace and another once its spans were read, changing under
        a caller who only asked for the spans."""
        mock_client.return_value.send_request.return_value = {
            "trace_id": TRACE_ID,
            "project_id": PROJECT_ID,
            "error_count": 1,
            "root_spans": [
                span_payload(
                    ROOT_ROW_ID,
                    "ai.chat",
                    status_code="OK",
                    children=[span_payload(LLM_ROW_ID, "ai.llm.invoke", status_code="ERROR")],
                )
            ],
        }
        trace = Trace.model_validate({**summary_payload, "status_code": "OK", "has_errors": False})

        trace.spans()

        assert trace.has_errors is False
        assert trace.error_count == 1


class TestTheTwoIds:
    """A trace has an OTEL hex id and a root span row id, and only the row id
    addresses it in the platform. Confusing them is the trap this entity exists
    to remove."""

    def test_a_detail_trace_already_knows_its_row_id(self, detail_payload):
        with patch("rhesis.sdk.entities.trace.APIClient") as client:
            assert Trace.model_validate(detail_payload).db_id == ROOT_ROW_ID
            client.assert_not_called()

    @patch("rhesis.sdk.entities.trace.APIClient")
    def test_a_listing_trace_fetches_the_detail_for_it(
        self, mock_client, summary_payload, detail_payload
    ):
        mock_client.return_value.send_request.return_value = detail_payload

        assert Trace.model_validate(summary_payload).db_id == ROOT_ROW_ID

        kwargs = mock_client.return_value.send_request.call_args.kwargs
        # The hex addresses the detail route; the project is required there and
        # comes off the trace the listing produced.
        assert kwargs["url_params"] == TRACE_ID
        assert kwargs["params"] == {"project_id": PROJECT_ID}

    @patch("rhesis.sdk.entities.trace.APIClient")
    def test_the_detail_is_fetched_once(self, mock_client, summary_payload, detail_payload):
        mock_client.return_value.send_request.return_value = detail_payload
        trace = Trace.model_validate(summary_payload)

        assert trace.db_id == ROOT_ROW_ID
        assert trace.db_id == ROOT_ROW_ID
        trace.spans()

        assert mock_client.return_value.send_request.call_count == 1

    @patch("rhesis.sdk.entities.trace.APIClient")
    def test_a_trace_with_no_spans_says_so_rather_than_refetching(
        self, mock_client, detail_payload
    ):
        """The row id is the annotation's entity_id. Returning None here would
        file the annotation against nothing at all."""
        detail_payload["root_spans"] = []
        mock_client.return_value.send_request.return_value = detail_payload
        trace = Trace.model_validate({"trace_id": TRACE_ID, "project_id": PROJECT_ID})

        for _ in range(2):
            with pytest.raises(ValueError, match="no root span row id"):
                assert trace.db_id

        # _detail_loaded, not the empty list, is what stops the second lookup.
        assert mock_client.return_value.send_request.call_count == 1

    def test_a_root_span_without_a_row_id_says_so(self, detail_payload):
        detail_payload["root_spans"][0]["id"] = None

        with pytest.raises(ValueError, match="no root span row id"):
            assert Trace.model_validate(detail_payload).db_id

    def test_a_trace_with_no_project_names_both_ways_to_give_one(self, monkeypatch):
        monkeypatch.delenv("RHESIS_PROJECT_ID", raising=False)
        trace = Trace(trace_id=TRACE_ID)

        with pytest.raises(ValueError, match="RHESIS_PROJECT_ID"):
            assert trace.db_id

    @patch("rhesis.sdk.entities.trace.APIClient")
    def test_falls_back_to_the_environment_for_the_project(
        self, mock_client, detail_payload, monkeypatch
    ):
        monkeypatch.setenv("RHESIS_PROJECT_ID", "project-from-env")
        mock_client.return_value.send_request.return_value = detail_payload

        Trace(trace_id=TRACE_ID).spans()

        params = mock_client.return_value.send_request.call_args.kwargs["params"]
        assert params == {"project_id": "project-from-env"}

    def test_a_trace_with_no_trace_id_says_so(self):
        with pytest.raises(ValueError, match="no trace_id"):
            Trace(project_id=PROJECT_ID).spans()


class TestSpans:
    def test_flattens_the_tree_depth_first(self):
        trace = Trace.model_validate(
            {
                "trace_id": TRACE_ID,
                "project_id": PROJECT_ID,
                "root_spans": [
                    span_payload(
                        "root",
                        "ai.chat",
                        children=[
                            span_payload(
                                "a", "retrieve", children=[span_payload("a1", "vector.search")]
                            ),
                            span_payload("b", "ai.llm.invoke"),
                        ],
                    )
                ],
            }
        )

        assert [s.span_name for s in trace.spans()] == [
            "ai.chat",
            "retrieve",
            "vector.search",
            "ai.llm.invoke",
        ]

    def test_filtering_by_name_still_descends_past_a_non_match(self):
        """The interesting span is usually a leaf under a parent you do not want."""
        trace = Trace.model_validate(
            {
                "trace_id": TRACE_ID,
                "project_id": PROJECT_ID,
                "root_spans": [
                    span_payload(
                        "root",
                        "ai.chat",
                        children=[
                            span_payload("a", "retrieve", children=[span_payload("a1", "hit")])
                        ],
                    )
                ],
            }
        )

        assert [s.id for s in trace.spans(name="hit")] == ["a1"]

    def test_the_named_span_is_the_first_one_found(self, detail_payload):
        trace = Trace.model_validate(detail_payload)

        assert trace.span("ai.llm.invoke").id == LLM_ROW_ID

    def test_a_span_that_is_not_there_is_none(self, detail_payload):
        assert Trace.model_validate(detail_payload).span("ai.rerank") is None

    @patch("rhesis.sdk.entities.trace.APIClient")
    def test_a_listing_trace_fetches_its_spans(self, mock_client, summary_payload, detail_payload):
        mock_client.return_value.send_request.return_value = detail_payload

        spans = Trace.model_validate(summary_payload).spans()

        assert [s.span_name for s in spans] == ["ai.chat", "ai.llm.invoke"]

    @patch("rhesis.sdk.entities.trace.APIClient")
    def test_a_re_pull_does_not_keep_spans_the_server_no_longer_reports(
        self, mock_client, detail_payload
    ):
        """Merging on the value rather than on what the response said would
        leave the old tree in place and report a row id that is no longer
        there."""
        trace = Trace.model_validate(detail_payload)
        assert trace.spans() != []
        emptied = {**detail_payload, "root_spans": [], "span_count": 0}
        mock_client.return_value.send_request.return_value = emptied

        trace.pull()

        assert trace.root_spans == []
        assert trace.span_count == 0

    @patch("rhesis.sdk.entities.trace.APIClient")
    def test_a_re_pull_still_keeps_what_only_a_listing_reports(
        self, mock_client, summary_payload, detail_payload
    ):
        """The other half of the same rule: absent is not the same as empty."""
        trace = Trace.model_validate(summary_payload)
        mock_client.return_value.send_request.return_value = detail_payload

        trace.pull()

        # The detail route never mentions these, so they are not the server
        # saying they are empty.
        assert trace.models == ["gpt-4o"]
        assert trace.providers == ["openai"]
        assert trace.tags_count == 0

    @patch("rhesis.sdk.entities.trace.APIClient")
    def test_the_detail_does_not_blank_what_only_a_listing_carries(
        self, mock_client, summary_payload, detail_payload
    ):
        """Merging the detail in must not drop the listing's own fields, which the
        detail route has no equivalent for."""
        mock_client.return_value.send_request.return_value = detail_payload
        trace = Trace.model_validate(summary_payload)

        trace.spans()

        assert trace.models == ["gpt-4o"]
        assert trace.trace_metrics_status == "Pass"
        assert trace.conversation_input == "What is the refund window?"
        # And it does pick up what only the detail has.
        assert trace.error_count == 1


class TestAnnotating:
    @patch("rhesis.sdk.entities.annotation.resolve_verdict", return_value=STATUS_ID)
    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_a_trace_is_annotated_by_its_row_id_not_its_hex(
        self, mock_client, _verdict, detail_payload
    ):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        Trace.model_validate(detail_payload).annotate("fail", "Answered from the wrong document.")

        body = mock_client.return_value.send_request.call_args.kwargs["data"]
        assert body["entity_type"] == "Trace"
        assert body["entity_id"] == ROOT_ROW_ID
        assert body["entity_id"] != TRACE_ID
        assert body["comments"] == "Answered from the wrong document."
        assert "target" not in body

    @patch("rhesis.sdk.entities.annotation.resolve_verdict", return_value=STATUS_ID)
    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_one_span_can_be_annotated_on_its_own(self, mock_client, _verdict, detail_payload):
        """The UI annotates whichever span is selected, so the SDK has to be able to."""
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}
        trace = Trace.model_validate(detail_payload)

        trace.span("ai.llm.invoke").annotate("fail", "Ignored the retrieved context.")

        body = mock_client.return_value.send_request.call_args.kwargs["data"]
        assert body["entity_id"] == LLM_ROW_ID

    @patch("rhesis.sdk.entities.annotation.resolve_verdict", return_value=STATUS_ID)
    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_a_trace_metric_can_be_targeted(self, mock_client, _verdict, detail_payload):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        Trace.model_validate(detail_payload).annotate(
            "pass", "Grounded after all.", metric="Groundedness"
        )

        body = mock_client.return_value.send_request.call_args.kwargs["data"]
        assert body["target"] == {"type": "metric", "reference": "Groundedness"}

    @patch("rhesis.sdk.entities.annotation.resolve_verdict", return_value=STATUS_ID)
    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_a_turn_can_be_targeted(self, mock_client, _verdict, detail_payload):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        Trace.model_validate(detail_payload).annotate("fail", "Off script.", turn=2)

        body = mock_client.return_value.send_request.call_args.kwargs["data"]
        assert body["target"] == {"type": "turn", "reference": "Turn 2"}

    def test_a_span_with_no_row_id_says_so(self):
        with pytest.raises(ValueError, match="carries no row id"):
            Span(span_name="ai.chat").annotate("fail")

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_a_trace_reads_its_annotations_by_row_id(self, mock_client, detail_payload):
        mock_client.return_value.send_request.return_value = []

        Trace.model_validate(detail_payload).get_annotations()

        kwargs = mock_client.return_value.send_request.call_args.kwargs
        assert kwargs["url_params"] == f"entity/Trace/{ROOT_ROW_ID}"

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_a_span_reads_its_own_annotations(self, mock_client, detail_payload):
        mock_client.return_value.send_request.return_value = []

        Trace.model_validate(detail_payload).span("ai.llm.invoke").get_annotations()

        kwargs = mock_client.return_value.send_request.call_args.kwargs
        assert kwargs["url_params"] == f"entity/Trace/{LLM_ROW_ID}"


class TestTracesAreNotWritable:
    """The only write is ingestion, so the inherited push and delete would send
    requests the API cannot honour."""

    def test_push_points_at_the_instrumentation(self, summary_payload):
        with pytest.raises(NotImplementedError, match="rhesis.sdk.telemetry"):
            Trace.model_validate(summary_payload).push()

    def test_delete_points_at_the_instrumentation(self, summary_payload):
        with pytest.raises(NotImplementedError, match="rhesis.sdk.telemetry"):
            Trace.model_validate(summary_payload).delete()


@patch("rhesis.sdk.entities.trace.APIClient")
class TestQueryFilters:
    """Named filters, because this route has no OData and would ignore one."""

    def _params(self, mock_client):
        return mock_client.return_value.send_request.call_args.kwargs["params"]

    def _empty(self, mock_client):
        mock_client.return_value.send_request.return_value = {
            "traces": [],
            "total": 0,
            "limit": 100,
            "offset": 0,
        }

    def test_sends_only_what_the_caller_passed(self, mock_client):
        self._empty(mock_client)

        Traces.query()

        # Nothing but paging: the route's own defaults stay in charge rather than
        # being shadowed by a copy of them here that then drifts.
        assert self._params(mock_client) == {"offset": 0, "limit": 100}

    def test_passes_the_filters_through_under_the_names_the_route_uses(self, mock_client):
        self._empty(mock_client)

        Traces.query(
            project_id=PROJECT_ID,
            test_run_id="run-1",
            status_code="ERROR",
            trace_metrics_status="Fail",
            span_name="ai.llm.invoke",
            search="refund",
            environment="production",
            trace_source="test",
            trace_type="Multi-Turn",
            sort_by="duration_ms",
            sort_order="asc",
        )

        assert self._params(mock_client) == {
            "project_id": PROJECT_ID,
            "test_run_id": "run-1",
            "status_code": "ERROR",
            "trace_metrics_status": "Fail",
            "span_name": "ai.llm.invoke",
            "search": "refund",
            "environment": "production",
            "trace_source": "test",
            "trace_type": "Multi-Turn",
            "sort_by": "duration_ms",
            "sort_order": "asc",
            "offset": 0,
            "limit": 100,
        }

    def test_a_false_filter_is_still_a_filter(self, mock_client):
        """root_spans_only=False is how you ask for every span. Dropping it as
        falsy would quietly return one row per trace instead."""
        self._empty(mock_client)

        Traces.query(root_spans_only=False)

        assert self._params(mock_client)["root_spans_only"] is False

    def test_a_zero_filter_is_still_a_filter(self, mock_client):
        self._empty(mock_client)

        Traces.query(duration_min_ms=0)

        assert self._params(mock_client)["duration_min_ms"] == 0

    def test_a_datetime_is_sent_as_a_timestamp(self, mock_client):
        self._empty(mock_client)

        Traces.query(start_time_after=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc))

        assert self._params(mock_client)["start_time_after"] == "2026-09-01T10:00:00+00:00"

    def test_a_string_time_is_passed_as_given(self, mock_client):
        self._empty(mock_client)

        Traces.query(start_time_before="2026-09-01")

        assert self._params(mock_client)["start_time_before"] == "2026-09-01"

    def test_one_provider_is_not_split_into_letters(self, mock_client):
        """provider is repeatable, so a bare string would otherwise become
        ['o','p','e','n','a','i'] and match nothing."""
        self._empty(mock_client)

        Traces.query(provider="openai")

        assert self._params(mock_client)["provider"] == ["openai"]

    def test_several_providers_are_passed_as_a_list(self, mock_client):
        self._empty(mock_client)

        Traces.query(provider=["openai", "anthropic"])

        assert self._params(mock_client)["provider"] == ["openai", "anthropic"]


@patch("rhesis.sdk.entities.trace.APIClient")
class TestPaging:
    def _page(self, count, total, summary_payload):
        return {
            "traces": [summary_payload] * count,
            "total": total,
            "limit": 100,
            "offset": 0,
        }

    def _skips(self, mock_client):
        return [
            call.kwargs["params"]["offset"]
            for call in mock_client.return_value.send_request.call_args_list
        ]

    def test_reads_past_the_first_page(self, mock_client, summary_payload):
        size = trace_module._PAGE_SIZE
        mock_client.return_value.send_request.side_effect = [
            self._page(size, size + 1, summary_payload),
            self._page(1, size + 1, summary_payload),
        ]

        found = Traces.query()

        assert len(found) == size + 1
        assert self._skips(mock_client) == [0, size]

    def test_a_short_page_ends_the_walk(self, mock_client, summary_payload):
        mock_client.return_value.send_request.return_value = self._page(3, 3, summary_payload)

        assert len(Traces.query()) == 3
        assert mock_client.return_value.send_request.call_count == 1

    def test_an_empty_page_ends_the_walk(self, mock_client, summary_payload):
        """A full page whose successor is empty. Without the short-page break the
        offset would stop advancing and this would spin forever."""
        size = trace_module._PAGE_SIZE
        mock_client.return_value.send_request.side_effect = [
            self._page(size, 500, summary_payload),
            self._page(0, 500, summary_payload),
        ]

        assert len(Traces.query()) == size
        assert mock_client.return_value.send_request.call_count == 2

    def test_stops_once_the_total_is_reached(self, mock_client, summary_payload):
        """A full page that is also the last one, which a short-page check alone
        cannot tell apart from a page with more behind it."""
        size = trace_module._PAGE_SIZE
        mock_client.return_value.send_request.side_effect = [
            self._page(size, size, summary_payload),
            self._page(size, size, summary_payload),
        ]

        assert len(Traces.query()) == size
        assert mock_client.return_value.send_request.call_count == 1

    def test_a_missing_total_still_terminates(self, mock_client, summary_payload):
        size = trace_module._PAGE_SIZE
        page = self._page(size, size, summary_payload)
        page.pop("total")
        mock_client.return_value.send_request.side_effect = [
            page,
            self._page(2, 0, summary_payload),
        ]

        assert len(Traces.query()) == size + 2

    def test_a_limit_caps_the_total_and_the_last_request(self, mock_client, summary_payload):
        size = trace_module._PAGE_SIZE
        mock_client.return_value.send_request.side_effect = [
            self._page(size, 500, summary_payload),
            self._page(20, 500, summary_payload),
        ]

        found = Traces.query(limit=size + 20)

        assert len(found) == size + 20
        limits = [
            call.kwargs["params"]["limit"]
            for call in mock_client.return_value.send_request.call_args_list
        ]
        # The second request asks for exactly what is left, rather than a full
        # page that would then be thrown away.
        assert limits == [size, 20]

    def test_a_limit_under_one_page_is_a_single_request(self, mock_client, summary_payload):
        mock_client.return_value.send_request.return_value = self._page(5, 500, summary_payload)

        found = Traces.query(limit=5)

        assert len(found) == 5
        assert self._params_limit(mock_client) == 5
        assert mock_client.return_value.send_request.call_count == 1

    def _params_limit(self, mock_client):
        return mock_client.return_value.send_request.call_args.kwargs["params"]["limit"]

    def test_a_limit_of_zero_asks_for_nothing(self, mock_client):
        """The route rejects limit=0, so the request must not be made at all."""
        assert Traces.query(limit=0) == []
        mock_client.return_value.send_request.assert_not_called()

    def test_an_empty_response_body_is_an_empty_list(self, mock_client):
        mock_client.return_value.send_request.return_value = None

        assert Traces.query() == []


@patch("rhesis.sdk.entities.trace.APIClient")
class TestCollectionSurface:
    """The inherited collection methods assume a bare list and a row id, and this
    route has neither."""

    def _empty(self, mock_client):
        mock_client.return_value.send_request.return_value = {"traces": [], "total": 0}

    def test_all_refuses_an_odata_filter_instead_of_ignoring_it(self, mock_client):
        with pytest.raises(ValueError, match="Traces.query"):
            Traces.all(filter="status_code eq 'ERROR'")

        mock_client.return_value.send_request.assert_not_called()

    def test_all_without_a_filter_lists(self, mock_client, summary_payload):
        mock_client.return_value.send_request.return_value = {
            "traces": [summary_payload],
            "total": 1,
        }

        assert len(Traces.all()) == 1

    def test_first_asks_for_one(self, mock_client, summary_payload):
        mock_client.return_value.send_request.return_value = {
            "traces": [summary_payload],
            "total": 9,
        }

        first = Traces.first()

        assert first.trace_id == TRACE_ID
        assert mock_client.return_value.send_request.call_args.kwargs["params"]["limit"] == 1

    def test_first_is_none_when_there_are_none(self, mock_client):
        self._empty(mock_client)

        assert Traces.first() is None

    def test_pull_takes_the_hex_and_the_project(self, mock_client, detail_payload):
        mock_client.return_value.send_request.return_value = detail_payload

        trace = Traces.pull(TRACE_ID, project_id=PROJECT_ID)

        kwargs = mock_client.return_value.send_request.call_args.kwargs
        assert kwargs["url_params"] == TRACE_ID
        assert kwargs["params"] == {"project_id": PROJECT_ID}
        assert trace.db_id == ROOT_ROW_ID

    def test_exists_is_false_for_a_trace_that_was_never_ingested(self, mock_client):
        mock_client.return_value.send_request.side_effect = _http_error(404)

        assert Traces.exists(TRACE_ID, project_id=PROJECT_ID) is False

    def test_exists_does_not_swallow_a_real_failure(self, mock_client):
        mock_client.return_value.send_request.side_effect = _http_error(500)

        with pytest.raises(RhesisAPIError):
            Traces.exists(TRACE_ID, project_id=PROJECT_ID)

    def test_for_test_run_uses_the_runs_own_route(self, mock_client, summary_payload):
        """That route resolves the project from the run. Filtering the trace list
        by test_run_id needs the caller scoped to the right project first, and
        answers with an empty list rather than an error when they are not."""
        mock_client.return_value.send_request.return_value = {
            "traces": [summary_payload],
            "total": 1,
        }

        Traces.for_test_run("run-1")

        kwargs = mock_client.return_value.send_request.call_args.kwargs
        assert kwargs["endpoint"].value == "test_runs"
        assert kwargs["url_params"] == "run-1/traces"

    def test_for_test_result_filters_the_list(self, mock_client):
        self._empty(mock_client)

        Traces.for_test_result("result-1")

        params = mock_client.return_value.send_request.call_args.kwargs["params"]
        assert params["test_result_id"] == "result-1"

    def test_for_endpoint_filters_the_list(self, mock_client):
        self._empty(mock_client)

        Traces.for_endpoint("endpoint-1")

        assert (
            mock_client.return_value.send_request.call_args.kwargs["params"]["endpoint_id"]
            == "endpoint-1"
        )

    def test_for_conversation_filters_the_list(self, mock_client):
        self._empty(mock_client)

        Traces.for_conversation("conversation-1")

        assert (
            mock_client.return_value.send_request.call_args.kwargs["params"]["conversation_id"]
            == "conversation-1"
        )

    def test_with_errors_filters_on_the_span_status(self, mock_client):
        self._empty(mock_client)

        Traces.with_errors(test_run_id="run-1")

        params = mock_client.return_value.send_request.call_args.kwargs["params"]
        assert params["status_code"] == "ERROR"
        assert params["test_run_id"] == "run-1"

    def test_slower_than_sorts_by_duration(self, mock_client):
        self._empty(mock_client)

        Traces.slower_than(5000)

        params = mock_client.return_value.send_request.call_args.kwargs["params"]
        assert params["duration_min_ms"] == 5000
        assert params["sort_by"] == "duration_ms"
        assert params["sort_order"] == "desc"


@patch("rhesis.sdk.entities.trace.APIClient")
class TestSpansCollection:
    """The way back from a row id, which is the only id an annotation, comment or
    platform link to a trace carries."""

    def test_lookup_resolves_a_row_id_to_the_ids_the_trace_routes_take(self, mock_client):
        mock_client.return_value.send_request.return_value = {
            "trace_id": TRACE_ID,
            "project_id": PROJECT_ID,
            "span_id": "b" * 16,
        }

        resolved = Spans.lookup(ROOT_ROW_ID)

        kwargs = mock_client.return_value.send_request.call_args.kwargs
        assert kwargs["url_params"] == f"{ROOT_ROW_ID}/lookup"
        assert resolved["trace_id"] == TRACE_ID

    def test_trace_for_loads_the_trace_the_span_belongs_to(self, mock_client, detail_payload):
        mock_client.return_value.send_request.side_effect = [
            {"trace_id": TRACE_ID, "project_id": PROJECT_ID, "span_id": "b" * 16},
            detail_payload,
        ]

        trace = Spans.trace_for(LLM_ROW_ID)

        calls = mock_client.return_value.send_request.call_args_list
        assert calls[0].kwargs["url_params"] == f"{LLM_ROW_ID}/lookup"
        # The detail route takes the hex and the project the lookup just reported.
        assert calls[1].kwargs["url_params"] == TRACE_ID
        assert calls[1].kwargs["params"] == {"project_id": PROJECT_ID}
        assert trace.trace_id == TRACE_ID

    def test_pull_picks_the_span_out_of_its_trace(self, mock_client, detail_payload):
        mock_client.return_value.send_request.side_effect = [
            {"trace_id": TRACE_ID, "project_id": PROJECT_ID, "span_id": "b" * 16},
            detail_payload,
        ]

        span = Spans.pull(LLM_ROW_ID)

        # A child span, so this only works because the tree is walked whole.
        assert span.id == LLM_ROW_ID
        assert span.span_name == "ai.llm.invoke"

    def test_pull_says_so_when_the_span_is_not_in_the_tree(self, mock_client, detail_payload):
        mock_client.return_value.send_request.side_effect = [
            {"trace_id": TRACE_ID, "project_id": PROJECT_ID, "span_id": "b" * 16},
            detail_payload,
        ]

        with pytest.raises(ValueError, match="not in that trace's span tree"):
            Spans.pull("55555555-5555-5555-5555-555555555555")

    def test_exists_is_false_for_a_row_id_that_resolves_to_nothing(self, mock_client):
        mock_client.return_value.send_request.side_effect = _http_error(404)

        assert Spans.exists(ROOT_ROW_ID) is False

    def test_exists_does_not_swallow_a_real_failure(self, mock_client):
        mock_client.return_value.send_request.side_effect = _http_error(403)

        with pytest.raises(RhesisAPIError):
            Spans.exists(ROOT_ROW_ID)

    def test_a_span_reads_its_attached_files(self, mock_client, detail_payload):
        mock_client.return_value.send_request.return_value = [
            {"id": "file-1", "filename": "question.wav", "content_type": "audio/wav"}
        ]

        files = Trace.model_validate(detail_payload).span("ai.llm.invoke").get_files()

        kwargs = mock_client.return_value.send_request.call_args.kwargs
        assert kwargs["url_params"] == f"{LLM_ROW_ID}/files"
        assert files[0].filename == "question.wav"

    def test_no_attached_files_is_an_empty_list(self, mock_client, detail_payload):
        mock_client.return_value.send_request.return_value = None

        assert Trace.model_validate(detail_payload).span("ai.chat").get_files() == []

    def test_spans_cannot_be_listed_and_says_what_to_do_instead(self, mock_client):
        with pytest.raises(NotImplementedError, match="root_spans_only=False"):
            Spans.all()

        with pytest.raises(NotImplementedError, match="no first one"):
            Spans.first()

        mock_client.return_value.send_request.assert_not_called()

    def test_providers_lists_what_the_provider_filter_accepts(self, mock_client):
        mock_client.return_value.send_request.return_value = ["openai", "anthropic", "unknown"]

        assert Traces.providers() == ["openai", "anthropic", "unknown"]

        kwargs = mock_client.return_value.send_request.call_args.kwargs
        assert kwargs["endpoint"].value == "telemetry/providers"
        assert kwargs["params"] is None

    def test_providers_can_be_scoped_to_a_project(self, mock_client):
        mock_client.return_value.send_request.return_value = []

        assert Traces.providers(project_id=PROJECT_ID) == []

        params = mock_client.return_value.send_request.call_args.kwargs["params"]
        assert params == {"project_id": PROJECT_ID}


def _http_error(status_code):
    response = MagicMock()
    response.status_code = status_code
    response.content = b'{"detail": "no"}'
    return requests.exceptions.HTTPError("failed", response=response)


class TestParentAccessors:
    @patch("rhesis.sdk.entities.trace.APIClient")
    def test_a_test_run_reaches_its_traces(self, mock_client, summary_payload):
        from rhesis.sdk.entities.test_run import TestRun

        mock_client.return_value.send_request.return_value = {
            "traces": [summary_payload],
            "total": 1,
        }

        found = TestRun(id="run-1").get_traces()

        kwargs = mock_client.return_value.send_request.call_args.kwargs
        assert kwargs["url_params"] == "run-1/traces"
        assert found[0].trace_id == TRACE_ID

    def test_a_test_run_without_an_id_says_so(self):
        from rhesis.sdk.entities.test_run import TestRun

        with pytest.raises(ValueError, match="Test run ID is required"):
            TestRun().get_traces()

    @patch("rhesis.sdk.entities.trace.APIClient")
    def test_a_test_result_reaches_its_traces(self, mock_client):
        from rhesis.sdk.entities.test_result import TestResult

        mock_client.return_value.send_request.return_value = {"traces": [], "total": 0}

        TestResult(id="result-1").get_traces()

        params = mock_client.return_value.send_request.call_args.kwargs["params"]
        assert params["test_result_id"] == "result-1"

    def test_a_test_result_without_an_id_says_so(self):
        from rhesis.sdk.entities.test_result import TestResult

        with pytest.raises(ValueError, match="must have an ID to get traces"):
            TestResult().get_traces()

    def test_a_trace_with_no_endpoint_has_none(self, summary_payload):
        summary_payload["endpoint_id"] = None

        assert Trace.model_validate(summary_payload).get_endpoint() is None

    @patch("rhesis.sdk.entities.base_collection.APIClient")
    def test_a_trace_reaches_its_endpoint(self, mock_client, summary_payload):
        mock_client.return_value.send_request.return_value = {
            "id": "endpoint-1",
            "name": "Support Chatbot",
        }

        endpoint = Trace.model_validate(summary_payload).get_endpoint()

        assert endpoint.name == "Support Chatbot"
