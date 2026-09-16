import os
from unittest.mock import patch

import pytest

from rhesis.sdk.entities.annotation import Annotation, Annotations
from rhesis.sdk.entities.status import Status

os.environ["RHESIS_BASE_URL"] = "http://test:8000"

ENTITY_ID = "11111111-1111-1111-1111-111111111111"
STATUS_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def annotation_response():
    """One annotation as the API returns it: target flat, status nested."""
    return {
        "id": "annotation-1",
        "entity_type": "TestResult",
        "entity_id": ENTITY_ID,
        "target_type": "metric",
        "target_reference": "Answer Fluency",
        "status_id": STATUS_ID,
        "status": {"id": STATUS_ID, "name": "Fail"},
        "comments": "The answer contradicts the source.",
        "resolved": False,
        "user_id": "user-1",
        "user": {"id": "user-1", "name": "Ada Lovelace", "email": "ada@example.com"},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "context": {"test_run_id": "run-1", "test_run_name": "witty-otter"},
    }


def test_reads_the_flat_target_and_nested_status(annotation_response):
    annotation = Annotation(**annotation_response)

    assert annotation.target_type == "metric"
    assert annotation.target_reference == "Answer Fluency"
    assert isinstance(annotation.status, Status)
    assert annotation.status.name == "Fail"


def test_keeps_the_author_timestamps_and_context(annotation_response):
    """Pydantic drops what the model does not declare, so a missing field here
    is a field the SDK silently cannot read."""
    annotation = Annotation(**annotation_response)

    assert annotation.user is not None
    assert annotation.user.name == "Ada Lovelace"
    assert annotation.user_id == "user-1"
    assert annotation.created_at == "2026-01-01T00:00:00Z"
    assert annotation.updated_at == "2026-01-02T00:00:00Z"
    assert annotation.context is not None
    # The run's memorable name is how a caller refers to it, not the uuid.
    assert annotation.context.test_run_name == "witty-otter"


class TestPush:
    """The write shape differs from the read shape, which is what push reconciles."""

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_nests_the_target_the_write_endpoint_expects(self, mock_client):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        Annotation(
            entity_type="Trace",
            entity_id=ENTITY_ID,
            status_id=STATUS_ID,
            comments="Turn 2 went off script.",
            target_type="turn",
            target_reference="Turn 2",
        ).push()

        body = mock_client.return_value.send_request.call_args.kwargs["data"]
        # Flat on the way out would be accepted and ignored, leaving the
        # annotation on the whole trace instead of the turn it named.
        assert body["target"] == {"type": "turn", "reference": "Turn 2"}
        assert "target_type" not in body
        assert "target_reference" not in body

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_omits_the_target_entirely_for_an_entity_level_judgement(self, mock_client):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        Annotation(
            entity_type="Trace",
            entity_id=ENTITY_ID,
            status_id=STATUS_ID,
            comments="The whole trace is wrong.",
        ).push()

        body = mock_client.return_value.send_request.call_args.kwargs["data"]
        # No target means the backend fills in the parent's entity-level one,
        # which is the only place that mapping should live.
        assert "target" not in body

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_does_not_send_the_nested_status_back(self, mock_client):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        Annotation(
            entity_type="TestResult",
            entity_id=ENTITY_ID,
            status_id=STATUS_ID,
            status=Status(id=STATUS_ID, name="Fail"),
            comments="Read-only on the write schema.",
        ).push()

        body = mock_client.return_value.send_request.call_args.kwargs["data"]
        assert "status" not in body
        assert body["status_id"] == STATUS_ID

    def test_requires_the_parent_and_a_verdict(self):
        with pytest.raises(ValueError, match="Required fields for push"):
            Annotation(comments="No parent, no verdict.").push()

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_an_update_does_not_try_to_re_parent(self, mock_client):
        """entity_type / entity_id are fixed at creation, and AnnotationUpdate
        has no such fields, so sending them implies something impossible."""
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        Annotation(
            id="annotation-1",
            entity_type="TestResult",
            entity_id=ENTITY_ID,
            status_id=STATUS_ID,
            comments="Changed my mind about this one.",
            resolved=True,
        ).push()

        kwargs = mock_client.return_value.send_request.call_args.kwargs
        assert kwargs["url_params"] == "annotation-1"
        body = kwargs["data"]
        assert "entity_type" not in body
        assert "entity_id" not in body
        assert body["resolved"] is True

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_does_not_send_back_what_the_server_owns(self, mock_client, annotation_response):
        """A round trip of pull-then-push must not post the author or timestamps."""
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        Annotation(**annotation_response).push()

        body = mock_client.return_value.send_request.call_args.kwargs["data"]
        for field in ("user", "user_id", "created_at", "updated_at", "context", "status"):
            assert field not in body, f"{field} should not be written back"


class TestCollection:
    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_for_entity_uses_the_entity_scoped_route(self, mock_client, annotation_response):
        mock_client.return_value.send_request.return_value = [annotation_response]

        found = Annotations.for_entity("TestResult", ENTITY_ID)

        assert mock_client.return_value.send_request.call_args.kwargs["url_params"] == (
            f"entity/TestResult/{ENTITY_ID}"
        )
        assert len(found) == 1
        assert found[0].comments == "The answer contradicts the source."

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_for_test_run_scopes_server_side(self, mock_client, annotation_response):
        mock_client.return_value.send_request.return_value = [annotation_response]

        Annotations.for_test_run("run-1")

        params = mock_client.return_value.send_request.call_args.kwargs["params"]
        assert params["test_run_id"] == "run-1"
        assert params["sort_order"] == "desc"

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_an_empty_response_is_an_empty_list(self, mock_client):
        mock_client.return_value.send_request.return_value = None

        assert Annotations.for_entity("Trace", ENTITY_ID) == []

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_reads_past_the_first_page(self, mock_client, annotation_response):
        """A full page means there may be more. Stopping there would drop
        annotations silently, which is the worst way to be wrong about them."""
        full_page = [annotation_response] * 100
        mock_client.return_value.send_request.side_effect = [full_page, [annotation_response]]

        found = Annotations.for_test_run("run-1")

        assert len(found) == 101
        skips = [
            call.kwargs["params"]["skip"]
            for call in mock_client.return_value.send_request.call_args_list
        ]
        assert skips == [0, 100]

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_a_short_page_ends_the_walk(self, mock_client, annotation_response):
        mock_client.return_value.send_request.return_value = [annotation_response]

        Annotations.for_entity("TestResult", ENTITY_ID)

        assert mock_client.return_value.send_request.call_count == 1


class TestParentGetters:
    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_a_test_result_reaches_its_annotations(self, mock_client, annotation_response):
        from rhesis.sdk.entities.test_result import TestResult

        mock_client.return_value.send_request.return_value = [annotation_response]

        found = TestResult(id=ENTITY_ID).get_annotations()

        assert mock_client.return_value.send_request.call_args.kwargs["url_params"] == (
            f"entity/TestResult/{ENTITY_ID}"
        )
        assert found[0].status.name == "Fail"

    def test_a_test_result_without_an_id_says_so(self):
        from rhesis.sdk.entities.test_result import TestResult

        with pytest.raises(ValueError, match="must have an ID"):
            TestResult().get_annotations()

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_a_test_run_scopes_by_run(self, mock_client, annotation_response):
        from rhesis.sdk.entities.test_run import TestRun

        mock_client.return_value.send_request.return_value = [annotation_response]

        TestRun(id="run-1").get_annotations()

        params = mock_client.return_value.send_request.call_args.kwargs["params"]
        assert params["test_run_id"] == "run-1"
