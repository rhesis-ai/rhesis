"""Recording a verdict on a trace an instrumented application just produced.

The caller has the OTEL trace id and has never seen the span row id the
platform stored the trace under, so these send the hex and let the server
resolve it. The write is otherwise an ordinary annotation, which is what makes
a Pass/Fail override the trace's automated outcome.
"""

from unittest.mock import patch

import pytest

from rhesis.sdk.telemetry import annotate_current_trace, annotate_trace

TRACE_HEX = "4bf92f3577b34da6a3ce929d0e0e4736"


@pytest.fixture(autouse=True)
def _stub_verdict_lookup():
    """A verdict is a status row, resolved over HTTP and cached per process.

    Patched out so these tests are about the annotation being sent, not about
    status resolution, which test_annotation.py already covers.
    """
    with patch("rhesis.sdk.telemetry.annotate.resolve_verdict", return_value="status-fail"):
        yield


def _body(mock_client):
    return mock_client.return_value.send_request.call_args.kwargs["data"]


@pytest.mark.unit
class TestAnnotatingByTraceId:
    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_sends_the_hex_as_the_parent_address(self, mock_client):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        annotate_trace(TRACE_HEX, "fail", "Cited a document that does not exist.")

        body = _body(mock_client)
        assert body["trace_id"] == TRACE_HEX
        assert body["entity_type"] == "Trace"
        assert body["status_id"] == "status-fail"
        assert body["comments"] == "Cited a document that does not exist."

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_never_sends_the_hex_as_entity_id(self, mock_client):
        """A 32-character hex parses as a UUID, so the server would accept it
        there and match no row. The two must not be interchangeable."""
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        annotate_trace(TRACE_HEX, "fail")

        assert "entity_id" not in _body(mock_client)

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_returns_the_annotation_with_its_new_id(self, mock_client):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        annotation = annotate_trace(TRACE_HEX, "fail")

        assert annotation.id == "annotation-1"

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_a_metric_target_is_nested_the_way_the_endpoint_takes_it(self, mock_client):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        annotate_trace(TRACE_HEX, "fail", metric="Answer Relevancy")

        assert _body(mock_client)["target"] == {
            "type": "metric",
            "reference": "Answer Relevancy",
        }

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_a_turn_is_normalised_to_the_stored_reference(self, mock_client):
        """Judgements are grouped by that reference, so a bare "2" would sit
        beside the turn's other annotations instead of superseding them."""
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        annotate_trace(TRACE_HEX, "fail", turn=2)

        assert _body(mock_client)["target"] == {"type": "turn", "reference": "Turn 2"}

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_an_entity_level_verdict_sends_no_target(self, mock_client):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        annotate_trace(TRACE_HEX, "fail")

        assert "target" not in _body(mock_client)

    def test_a_metric_and_a_turn_together_are_refused(self):
        """An annotation judges one thing."""
        with pytest.raises(ValueError, match="metric or a turn"):
            annotate_trace(TRACE_HEX, "fail", metric="Answer Relevancy", turn=2)


@pytest.mark.unit
class TestAnnotatingTheTraceInContext:
    @patch("rhesis.sdk.entities.base_entity.APIClient")
    @patch("rhesis.sdk.telemetry.annotate.get_root_trace_id", return_value=TRACE_HEX)
    def test_takes_the_trace_id_from_the_tracer(self, _root, mock_client):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        annotate_current_trace("fail", "Wrong answer.")

        assert _body(mock_client)["trace_id"] == TRACE_HEX

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    @patch("rhesis.sdk.telemetry.annotate.get_root_trace_id", return_value=TRACE_HEX)
    def test_passes_the_target_through(self, _root, mock_client):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        annotate_current_trace("fail", turn=3)

        assert _body(mock_client)["target"] == {"type": "turn", "reference": "Turn 3"}

    @patch("rhesis.sdk.telemetry.annotate.get_root_trace_id", return_value=None)
    def test_no_trace_in_context_raises_rather_than_doing_nothing(self, _root):
        """Silently skipping would lose the verdict, and guessing a trace would
        file it against the wrong one."""
        with pytest.raises(ValueError, match="No trace in context"):
            annotate_current_trace("fail")
