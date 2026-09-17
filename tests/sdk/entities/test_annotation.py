import os
from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk.entities import annotation as annotation_module
from rhesis.sdk.entities.annotation import (
    Annotation,
    Annotations,
    resolve_verdict,
)
from rhesis.sdk.entities.endpoint import Endpoint
from rhesis.sdk.entities.status import Status
from rhesis.sdk.entities.test import Test
from rhesis.sdk.entities.test_result import TestResult
from rhesis.sdk.entities.test_set import TestSet

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

    def test_requires_the_parent_and_a_verdict_to_create(self):
        with pytest.raises(ValueError, match="Required fields for push"):
            Annotation(comments="No parent, no verdict.").push()

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_resolves_by_id_without_hydrating_the_rest(self, mock_client):
        """Requiring the parent and verdict on an update too would make the
        obvious "resolve this one" call impossible."""
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        Annotation(id="annotation-1", resolved=True).push()

        kwargs = mock_client.return_value.send_request.call_args.kwargs
        assert kwargs["url_params"] == "annotation-1"
        assert kwargs["data"] == {"resolved": True}

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


class TestVerdictResolution:
    """Naming a verdict beats making every caller resolve a status id first."""

    def setup_method(self):
        annotation_module._verdict_cache.clear()

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_resolves_a_named_verdict_against_the_right_entity_type(self, mock_client):
        mock_client.return_value.send_request.return_value = [{"id": STATUS_ID, "name": "Fail"}]

        assert resolve_verdict("fail") == STATUS_ID

        params = mock_client.return_value.send_request.call_args.kwargs["params"]
        # Scoped by entity type, not name alone: Pass/Fail belong to TestResult,
        # and matching on the name would break once another type has a "Fail".
        # The name is matched client-side, so nothing is interpolated into OData.
        assert params == {"entity_type": "TestResult", "skip": 0, "limit": 100}

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_tuning_verdicts_resolve_under_their_own_entity_type(self, mock_client):
        mock_client.return_value.send_request.return_value = [{"id": STATUS_ID, "name": "Rejected"}]

        resolve_verdict("rejected")

        params = mock_client.return_value.send_request.call_args.kwargs["params"]
        assert params["entity_type"] == "Annotation"

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_is_case_and_whitespace_insensitive(self, mock_client):
        mock_client.return_value.send_request.return_value = [{"id": STATUS_ID, "name": "Pass"}]

        assert resolve_verdict("  PASS ") == STATUS_ID

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_looks_a_verdict_up_once(self, mock_client):
        mock_client.return_value.send_request.return_value = [{"id": STATUS_ID, "name": "Fail"}]

        resolve_verdict("fail")
        resolve_verdict("fail")

        assert mock_client.return_value.send_request.call_count == 1

    def test_an_unknown_verdict_names_the_ones_that_exist(self):
        with pytest.raises(ValueError, match="pass, fail, accepted, rejected"):
            resolve_verdict("looks-fine")

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_a_missing_status_row_says_so(self, mock_client):
        mock_client.return_value.send_request.return_value = []

        with pytest.raises(ValueError, match="No 'Fail' status exists"):
            resolve_verdict("fail")


@patch("rhesis.sdk.entities.annotation.resolve_verdict", return_value=STATUS_ID)
class TestAnnotateFromTheParent:
    """The common case: judge the thing you already have in hand.

    Verdict resolution is stubbed: what these assert is the body that goes out,
    and TestVerdictResolution covers the lookup itself.
    """

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_a_result_annotates_itself(self, mock_client, _verdict):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        annotation = TestResult(id=ENTITY_ID).annotate("fail", "Invented a policy.")

        body = mock_client.return_value.send_request.call_args.kwargs["data"]
        assert body["entity_type"] == "TestResult"
        assert body["entity_id"] == ENTITY_ID
        assert body["status_id"] == STATUS_ID
        assert body["comments"] == "Invented a policy."
        assert "target" not in body
        assert annotation.id == "annotation-1"

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_naming_a_metric_targets_only_that_metric(self, mock_client, _verdict):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        TestResult(id=ENTITY_ID).annotate("fail", "Wrong.", metric="Answer Relevancy")

        body = mock_client.return_value.send_request.call_args.kwargs["data"]
        assert body["target"] == {"type": "metric", "reference": "Answer Relevancy"}

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_naming_a_turn_targets_only_that_turn(self, mock_client, _verdict):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        TestResult(id=ENTITY_ID).annotate("fail", "Off script.", turn="Turn 2")

        body = mock_client.return_value.send_request.call_args.kwargs["data"]
        assert body["target"] == {"type": "turn", "reference": "Turn 2"}

    def test_a_metric_and_a_turn_together_is_refused(self, _verdict):
        with pytest.raises(ValueError, match="not both"):
            TestResult(id=ENTITY_ID).annotate("fail", metric="Relevancy", turn="Turn 2")

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_a_test_labels_itself(self, mock_client, _verdict):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        Test(id=ENTITY_ID).annotate("fail", "Not a fair question.")

        body = mock_client.return_value.send_request.call_args.kwargs["data"]
        assert body["entity_type"] == "Test"

    def test_annotating_without_an_id_says_what_is_missing(self, _verdict):
        with pytest.raises(ValueError, match="must have an ID to annotate"):
            TestResult().annotate("fail")


class TestResolveAndReopen:
    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_resolve_sends_only_the_resolved_flag(self, mock_client):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        annotation = Annotation(
            id="annotation-1", entity_type="TestResult", entity_id=ENTITY_ID, comments="keep me"
        )
        annotation.resolve()

        body = mock_client.return_value.send_request.call_args.kwargs["data"]
        # A local edit must not ride along on a resolve.
        assert body["resolved"] is True
        assert "comments" not in body
        assert annotation.resolved is True

    @patch("rhesis.sdk.entities.base_entity.APIClient")
    def test_reopen_clears_it(self, mock_client):
        mock_client.return_value.send_request.return_value = {"id": "annotation-1"}

        annotation = Annotation(id="annotation-1", resolved=True).reopen()

        body = mock_client.return_value.send_request.call_args.kwargs["data"]
        assert body["resolved"] is False
        assert annotation.resolved is False

    def test_resolving_without_an_id_says_so(self):
        with pytest.raises(ValueError, match="must have an id"):
            Annotation(entity_type="TestResult", entity_id=ENTITY_ID).resolve()


class TestParentAccessors:
    """Every parent the collection can filter by reaches its own annotations."""

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_a_trace_is_addressed_by_its_row_id(self, mock_client):
        mock_client.return_value.send_request.return_value = []

        Annotations.for_trace("trace-row-1")

        kwargs = mock_client.return_value.send_request.call_args.kwargs
        assert kwargs["url_params"] == "entity/Trace/trace-row-1"

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_a_test_set_scopes_server_side(self, mock_client):
        mock_client.return_value.send_request.return_value = []

        TestSet(id="set-1").get_annotations()

        params = mock_client.return_value.send_request.call_args.kwargs["params"]
        assert params["test_set_id"] == "set-1"

    @patch("rhesis.sdk.entities.annotation.APIClient")
    def test_an_endpoint_scopes_server_side(self, mock_client):
        mock_client.return_value.send_request.return_value = []

        Endpoint(id="endpoint-1").get_annotations()

        params = mock_client.return_value.send_request.call_args.kwargs["params"]
        assert params["endpoint_id"] == "endpoint-1"


class TestVerdictCacheIsolation:
    """One process can address two organizations, and status ids differ per org."""

    def setup_method(self):
        annotation_module._verdict_cache.clear()

    def _client(self, key, base_url="http://one:8000"):
        client = MagicMock()
        client.api_key = key
        client.base_url = base_url
        return client

    def test_a_second_organization_does_not_inherit_the_first_ones_id(self):
        org_a = self._client("key-a")
        org_a.send_request.return_value = [{"id": "status-a", "name": "Fail"}]
        org_b = self._client("key-b")
        org_b.send_request.return_value = [{"id": "status-b", "name": "Fail"}]

        assert resolve_verdict("fail", client=org_a) == "status-a"
        # api_key is a module-level variable a caller can reassign, so this is a
        # supported flow -- and the cached id would be the wrong organization's.
        assert resolve_verdict("fail", client=org_b) == "status-b"

    def test_the_same_organization_is_still_looked_up_once(self):
        org_a = self._client("key-a")
        org_a.send_request.return_value = [{"id": "status-a", "name": "Fail"}]

        resolve_verdict("fail", client=org_a)
        resolve_verdict("fail", client=org_a)

        assert org_a.send_request.call_count == 1

    def test_the_same_key_against_another_base_url_is_a_different_cache_entry(self):
        one = self._client("key-a", "http://one:8000")
        one.send_request.return_value = [{"id": "status-one", "name": "Pass"}]
        two = self._client("key-a", "http://two:8000")
        two.send_request.return_value = [{"id": "status-two", "name": "Pass"}]

        assert resolve_verdict("pass", client=one) == "status-one"
        assert resolve_verdict("pass", client=two) == "status-two"

    def test_the_cache_does_not_hold_the_api_key(self):
        org_a = self._client("super-secret-key")
        org_a.send_request.return_value = [{"id": "status-a", "name": "Fail"}]

        resolve_verdict("fail", client=org_a)

        assert "super-secret-key" not in repr(annotation_module._verdict_cache)


class TestVerdictResolutionPages:
    """The verdicts are the oldest rows of their entity type, so page one is not enough."""

    def setup_method(self):
        annotation_module._verdict_cache.clear()

    def _client(self):
        client = MagicMock()
        client.api_key = "key"
        client.base_url = "http://one:8000"
        return client

    def test_finds_a_verdict_that_is_not_on_the_first_page(self):
        client = self._client()
        page_size = annotation_module._PAGE_SIZE
        # /statuses/ defaults to ten rows sorted newest first, and Pass/Fail are
        # seeded, so an organization with statuses of its own pushes them back.
        first = [{"id": f"custom-{i}", "name": f"Custom {i}"} for i in range(page_size)]
        second = [{"id": STATUS_ID, "name": "Fail"}]
        client.send_request.side_effect = [first, second]

        assert resolve_verdict("fail", client=client) == STATUS_ID
        assert client.send_request.call_count == 2
        assert client.send_request.call_args.kwargs["params"]["skip"] == page_size

    def test_stops_at_a_short_page(self):
        client = self._client()
        client.send_request.side_effect = [[{"id": STATUS_ID, "name": "Fail"}]]

        resolve_verdict("fail", client=client)

        # A page shorter than the limit is the last one; asking for another
        # would be a wasted round trip on every single lookup.
        assert client.send_request.call_count == 1

    def test_still_reports_a_verdict_that_genuinely_has_no_row(self):
        client = self._client()
        client.send_request.side_effect = [[{"id": "x", "name": "Something else"}]]

        with pytest.raises(ValueError, match="No 'Fail' status exists"):
            resolve_verdict("fail", client=client)
