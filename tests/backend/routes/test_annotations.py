"""Tests for GET /annotations — flattened review list."""

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.models.behavior import Behavior
from rhesis.backend.app.models.status import Status
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_result import TestResult
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.scope import RequestScope
from tests.backend.routes.fixtures.data_factories import TraceDataFactory


@contextmanager
def _project_scope(test_db, organization_id, user_id, project_id):
    """Bind ambient project scope for the request, then restore prior scope.

    Route tests override ``get_tenant_db_session`` with the plain test session,
    so ``X-Project-Id`` never reaches the real dependency that binds scope.
    Always restore afterward so auto-stamp cannot leak project_id onto later
    tests' org-level rows (e.g. Status).
    """
    previous = test_db.info.get("_scope")
    test_db.info["_scope"] = RequestScope(
        organization_id=str(organization_id),
        user_id=str(user_id),
        project_id=str(project_id) if project_id else None,
    )
    try:
        yield
    finally:
        if previous is None:
            test_db.info.pop("_scope", None)
        else:
            test_db.info["_scope"] = previous


def _ensure_pass_fail_statuses(test_db, test_organization, test_type_lookup, db_user):
    # Statuses are org-scoped (project_id NULL). Clear any ambient project so
    # auto-stamp does not project-stamp them while annotation tests run.
    previous = test_db.info.get("_scope")
    if previous is not None:
        test_db.info["_scope"] = RequestScope(
            organization_id=previous.organization_id,
            user_id=previous.user_id,
            project_id=None,
        )
    try:
        pass_status = (
            test_db.query(Status)
            .filter(
                Status.name == "Pass",
                Status.organization_id == test_organization.id,
            )
            .first()
        )
        fail_status = (
            test_db.query(Status)
            .filter(
                Status.name == "Fail",
                Status.organization_id == test_organization.id,
            )
            .first()
        )
        if pass_status and fail_status:
            return pass_status, fail_status

        if not pass_status:
            pass_status = Status(
                name="Pass",
                description="Passed evaluation",
                entity_type_id=test_type_lookup.id,
                organization_id=test_organization.id,
                user_id=db_user.id,
            )
            test_db.add(pass_status)
        if not fail_status:
            fail_status = Status(
                name="Fail",
                description="Failed evaluation",
                entity_type_id=test_type_lookup.id,
                organization_id=test_organization.id,
                user_id=db_user.id,
            )
            test_db.add(fail_status)
        test_db.commit()
        test_db.refresh(pass_status)
        test_db.refresh(fail_status)
        return pass_status, fail_status
    finally:
        if previous is None:
            test_db.info.pop("_scope", None)
        else:
            test_db.info["_scope"] = previous


def _review_payload(status_id, user_id, user_name="Test User", target_type="test_result"):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "review_id": str(uuid.uuid4()),
        "status": {"status_id": str(status_id), "name": "Pass"},
        "user": {"user_id": str(user_id), "name": user_name},
        "comments": "Looks good after human review.",
        "created_at": now,
        "updated_at": now,
        "target": {"type": target_type, "reference": None},
    }


def _seed_annotated_run(
    test_db,
    *,
    organization_id,
    user_id,
    project_id,
    endpoint_id,
    status_id,
    marker,
):
    """Seed one test run with an annotated result and an annotated trace.

    The trace is linked to both the run and the result via ``test_run_id`` /
    ``test_result_id``, which is how real execution traces are stored — that
    linkage is what lets ``?test_run_id=`` span both sources.

    Returns ``(test_run, test_result, trace, result_review, trace_review)``.
    """
    test_config = TestConfiguration(
        endpoint_id=endpoint_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    test_db.add(test_config)
    test_db.flush()

    test_run = TestRun(
        test_configuration_id=test_config.id,
        organization_id=organization_id,
        user_id=user_id,
    )
    test_db.add(test_run)
    test_db.flush()

    result_review = _review_payload(status_id, user_id)
    result_review["comments"] = f"{marker}-result"
    test_result = TestResult(
        organization_id=organization_id,
        user_id=user_id,
        project_id=project_id,
        test_configuration_id=test_config.id,
        test_run_id=test_run.id,
        test_reviews={"metadata": {"total_reviews": 1}, "reviews": [result_review]},
    )
    test_db.add(test_result)
    test_db.flush()

    now = datetime.now(timezone.utc)
    trace_review = _review_payload(status_id, user_id, target_type="trace")
    trace_review["comments"] = f"{marker}-trace"
    trace = Trace(
        trace_id=uuid.uuid4().hex,
        span_id=uuid.uuid4().hex[:16],
        project_id=project_id,
        organization_id=organization_id,
        environment="development",
        span_name="ai.llm.invoke",
        span_kind="CLIENT",
        start_time=now,
        end_time=now + timedelta(seconds=1),
        duration_ms=1000.0,
        status_code="OK",
        attributes={},
        events=[],
        links=[],
        resource={},
        test_run_id=test_run.id,
        test_result_id=test_result.id,
        trace_reviews={"metadata": {"total_reviews": 1}, "reviews": [trace_review]},
    )
    test_db.add(trace)
    test_db.commit()
    test_db.refresh(test_run)
    test_db.refresh(test_result)
    test_db.refresh(trace)
    return test_run, test_result, trace, result_review, trace_review


@pytest.mark.integration
class TestListAnnotations:
    def test_list_empty(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        authenticated_user,
        db_project,
    ):
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            response = authenticated_client.get("/annotations/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
        assert response.headers.get("X-Total-Count") == "0"

    def test_requires_project_scope(self, authenticated_client: TestClient, test_db):
        test_db.info.pop("_scope", None)
        with patch(
            "rhesis.backend.app.routers.annotations.project_id_from_scope",
            return_value=None,
        ):
            response = authenticated_client.get("/annotations/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "project_id is required" in response.json()["detail"]

    def test_list_test_result_and_trace_reviews(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
    ):
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )

        # Seed a test result with a review linked to a behavior via test
        review = _review_payload(pass_status.id, authenticated_user.id)
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            behavior = Behavior(
                name="Annotation Hub Behavior",
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
            )
            test_db.add(behavior)
            test_db.flush()
            linked_test = Test(
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
                behavior_id=behavior.id,
            )
            test_db.add(linked_test)
            test_db.flush()
            test_result = TestResult(
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
                test_id=linked_test.id,
                test_reviews={
                    "metadata": {"total_reviews": 1},
                    "reviews": [review],
                },
            )
            test_db.add(test_result)
            test_db.commit()
            test_db.refresh(test_result)

            # Seed a trace with a review via ingest + direct JSONB update
            span_data = TraceDataFactory.sample_data(project_id=str(db_project.id))
            ingest = authenticated_client.post(
                "/telemetry/traces",
                json={"spans": [span_data]},
            )
            assert ingest.status_code == status.HTTP_200_OK

            detail = authenticated_client.get(
                f"/telemetry/traces/{span_data['trace_id']}?project_id={db_project.id}"
            )
            assert detail.status_code == status.HTTP_200_OK
            root = detail.json()["root_spans"][0]
            trace_db_id = root["id"]

            trace = test_db.query(Trace).filter(Trace.id == uuid.UUID(trace_db_id)).first()
            assert trace is not None
            trace_review = _review_payload(
                pass_status.id, authenticated_user.id, target_type="trace"
            )
            trace.trace_reviews = {
                "metadata": {"total_reviews": 1},
                "reviews": [trace_review],
            }
            flag_modified(trace, "trace_reviews")
            test_db.commit()

            response = authenticated_client.get("/annotations/")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) >= 2
            assert int(response.headers.get("X-Total-Count", "0")) >= 2

            sources = {item["source"] for item in data}
            assert "test_result" in sources
            assert "trace" in sources

            tr_item = next(i for i in data if i["review_id"] == review["review_id"])
            assert tr_item["test_result_id"] == str(test_result.id)
            assert tr_item["status"]["name"] == "Pass"
            assert tr_item["behavior_id"] == str(behavior.id)
            assert tr_item["behavior_name"] == "Annotation Hub Behavior"

            search_behavior = authenticated_client.get(
                "/annotations/?search=Annotation%20Hub%20Behavior"
            )
            assert search_behavior.status_code == status.HTTP_200_OK
            assert any(i["review_id"] == review["review_id"] for i in search_behavior.json())

            filter_tr = authenticated_client.get("/annotations/?source=test_result")
            assert filter_tr.status_code == status.HTTP_200_OK
            assert all(i["source"] == "test_result" for i in filter_tr.json())

            filter_trace = authenticated_client.get("/annotations/?source=trace")
            assert filter_trace.status_code == status.HTTP_200_OK
            assert all(i["source"] == "trace" for i in filter_trace.json())
            assert all(i.get("behavior_name") is None for i in filter_trace.json())

    def test_list_includes_resolved_flag(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
    ):
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        review = _review_payload(pass_status.id, authenticated_user.id)
        review["resolved"] = True
        review["resolved_at"] = review["updated_at"]
        legacy_open = _review_payload(pass_status.id, authenticated_user.id)
        legacy_open["resolved"] = "false"
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            test_result = TestResult(
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
                test_reviews={
                    "metadata": {"total_reviews": 2},
                    "reviews": [review, legacy_open],
                },
            )
            test_db.add(test_result)
            test_db.commit()

            response = authenticated_client.get("/annotations/?source=test_result")
            assert response.status_code == status.HTTP_200_OK
            by_id = {i["review_id"]: i for i in response.json()}
            assert by_id[review["review_id"]]["resolved"] is True
            assert by_id[legacy_open["review_id"]]["resolved"] is False

    def test_search_and_filters(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
    ):
        pass_status, fail_status = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        open_review = _review_payload(pass_status.id, authenticated_user.id)
        open_review["comments"] = "unique-open-annotation-marker"
        resolved_review = _review_payload(fail_status.id, authenticated_user.id)
        resolved_review["comments"] = "unique-resolved-annotation-marker"
        resolved_review["resolved"] = True
        resolved_review["status"] = {
            "status_id": str(fail_status.id),
            "name": "Fail",
        }

        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            test_result = TestResult(
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
                test_reviews={
                    "metadata": {"total_reviews": 2},
                    "reviews": [open_review, resolved_review],
                },
            )
            test_db.add(test_result)
            test_db.commit()

            search = authenticated_client.get("/annotations/?search=unique-open-annotation-marker")
            assert search.status_code == status.HTTP_200_OK
            search_ids = {i["review_id"] for i in search.json()}
            assert open_review["review_id"] in search_ids
            assert resolved_review["review_id"] not in search_ids

            resolved = authenticated_client.get("/annotations/?resolved=true")
            assert resolved.status_code == status.HTTP_200_OK
            resolved_ids = {i["review_id"] for i in resolved.json()}
            assert resolved_review["review_id"] in resolved_ids
            assert open_review["review_id"] not in resolved_ids

            failed = authenticated_client.get("/annotations/?rating=Fail")
            assert failed.status_code == status.HTTP_200_OK
            fail_ids = {i["review_id"] for i in failed.json()}
            assert resolved_review["review_id"] in fail_ids
            assert open_review["review_id"] not in fail_ids


@pytest.mark.integration
class TestAnnotationScoping:
    """Scoping annotations to a test run, test result, or trace."""

    @pytest.fixture
    def two_runs(
        self,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        db_endpoint,
    ):
        """Two independent annotated runs, so filters can be shown to exclude."""
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            target = _seed_annotated_run(
                test_db,
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
                endpoint_id=db_endpoint.id,
                status_id=pass_status.id,
                marker="scoped-run",
            )
            other = _seed_annotated_run(
                test_db,
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
                endpoint_id=db_endpoint.id,
                status_id=pass_status.id,
                marker="other-run",
            )
            yield target, other

    def test_scope_by_test_run_id_spans_results_and_traces(
        self,
        authenticated_client: TestClient,
        two_runs,
    ):
        target, other = two_runs
        test_run, test_result, trace, result_review, trace_review = target
        _, _, _, other_result_review, other_trace_review = other

        response = authenticated_client.get(f"/annotations/?test_run_id={test_run.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        ids = {i["review_id"] for i in data}
        assert result_review["review_id"] in ids
        assert trace_review["review_id"] in ids
        assert other_result_review["review_id"] not in ids
        assert other_trace_review["review_id"] not in ids

        # Both sources come back from a single run-scoped call.
        assert {i["source"] for i in data} == {"test_result", "trace"}
        assert response.headers.get("X-Total-Count") == "2"

        by_id = {i["review_id"]: i for i in data}
        assert by_id[result_review["review_id"]]["test_result_id"] == str(test_result.id)
        assert by_id[trace_review["review_id"]]["trace_id"] == trace.trace_id

        # A trace annotation carries the run/result it belongs to, so the
        # agent can walk back to the run it was filtered by.
        trace_item = by_id[trace_review["review_id"]]
        assert trace_item["test_run_id"] == str(test_run.id)
        assert trace_item["test_result_id"] == str(test_result.id)

    def test_org_level_rows_without_a_project_are_visible(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        db_endpoint,
    ):
        """Reviews on test results with a NULL project_id must still be listed.

        A run whose test configuration carries no project produces test
        results stamped with a NULL project_id. Those rows are org-level: the
        ORM auto-filter and the ``project_isolation`` RLS policy both admit
        them under any active project, and the test run page shows their
        reviews. Strict ``project_id = :project_id`` here hid them, so the
        architect reported "no annotations" on runs that visibly had them.

        Traces need no equivalent case — ``trace.project_id`` is NOT NULL.
        """
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        review = _review_payload(pass_status.id, authenticated_user.id)
        review["comments"] = "null-project-result"

        # No ambient project → auto-stamp leaves project_id NULL.
        with _project_scope(test_db, test_organization.id, authenticated_user.id, None):
            test_config = TestConfiguration(
                endpoint_id=db_endpoint.id,
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
            )
            test_db.add(test_config)
            test_db.flush()
            test_run = TestRun(
                test_configuration_id=test_config.id,
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
            )
            test_db.add(test_run)
            test_db.flush()
            test_result = TestResult(
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                test_configuration_id=test_config.id,
                test_run_id=test_run.id,
                test_reviews={"metadata": {"total_reviews": 1}, "reviews": [review]},
            )
            test_db.add(test_result)
            test_db.commit()
            test_db.refresh(test_result)

        assert test_result.project_id is None

        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            response = authenticated_client.get(f"/annotations/?test_run_id={test_run.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert {i["review_id"] for i in data} == {review["review_id"]}
        assert data[0]["comments"] == "null-project-result"

    def test_operation_trace_annotation_has_null_run_and_result(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
    ):
        """A trace outside a test run has no run/result ids to report."""
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        review = _review_payload(pass_status.id, authenticated_user.id, target_type="trace")
        now = datetime.now(timezone.utc)
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            trace = Trace(
                trace_id=uuid.uuid4().hex,
                span_id=uuid.uuid4().hex[:16],
                project_id=db_project.id,
                organization_id=test_organization.id,
                environment="development",
                span_name="ai.llm.invoke",
                span_kind="CLIENT",
                start_time=now,
                end_time=now + timedelta(seconds=1),
                duration_ms=1000.0,
                status_code="OK",
                attributes={},
                events=[],
                links=[],
                resource={},
                trace_reviews={"metadata": {"total_reviews": 1}, "reviews": [review]},
            )
            test_db.add(trace)
            test_db.commit()

            response = authenticated_client.get(f"/annotations/?trace_id={trace.trace_id}")

        assert response.status_code == status.HTTP_200_OK
        item = next(i for i in response.json() if i["review_id"] == review["review_id"])
        assert item["test_run_id"] is None
        assert item["test_result_id"] is None

    def test_scope_by_test_result_id_includes_linked_traces(
        self,
        authenticated_client: TestClient,
        two_runs,
    ):
        target, other = two_runs
        _, test_result, _, result_review, trace_review = target
        _, _, _, other_result_review, _ = other

        response = authenticated_client.get(f"/annotations/?test_result_id={test_result.id}")
        assert response.status_code == status.HTTP_200_OK
        ids = {i["review_id"] for i in response.json()}
        assert ids == {result_review["review_id"], trace_review["review_id"]}
        assert other_result_review["review_id"] not in ids

    def test_scope_by_trace_id_returns_traces_only(
        self,
        authenticated_client: TestClient,
        two_runs,
    ):
        target, _ = two_runs
        _, _, trace, result_review, trace_review = target

        response = authenticated_client.get(f"/annotations/?trace_id={trace.trace_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert [i["review_id"] for i in data] == [trace_review["review_id"]]
        assert all(i["source"] == "trace" for i in data)
        # The sibling test-result review is on the same run but is not a trace.
        assert result_review["review_id"] not in {i["review_id"] for i in data}

    def test_scope_by_trace_db_id_returns_traces_only(
        self,
        authenticated_client: TestClient,
        two_runs,
    ):
        target, _ = two_runs
        _, _, trace, _, trace_review = target

        response = authenticated_client.get(f"/annotations/?trace_db_id={trace.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert [i["review_id"] for i in data] == [trace_review["review_id"]]
        assert data[0]["trace_db_id"] == str(trace.id)

    def test_scope_composes_with_source_filter(
        self,
        authenticated_client: TestClient,
        two_runs,
    ):
        target, _ = two_runs
        test_run, _, _, result_review, trace_review = target

        response = authenticated_client.get(
            f"/annotations/?test_run_id={test_run.id}&source=test_result"
        )
        assert response.status_code == status.HTTP_200_OK
        ids = {i["review_id"] for i in response.json()}
        assert ids == {result_review["review_id"]}
        assert trace_review["review_id"] not in ids

    def test_scope_composes_with_resolved_filter(
        self,
        authenticated_client: TestClient,
        test_db,
        two_runs,
    ):
        target, _ = two_runs
        test_run, _, trace, result_review, trace_review = target

        trace.trace_reviews["reviews"][0]["resolved"] = True
        flag_modified(trace, "trace_reviews")
        test_db.commit()

        open_items = authenticated_client.get(
            f"/annotations/?test_run_id={test_run.id}&resolved=false"
        )
        assert open_items.status_code == status.HTTP_200_OK
        assert {i["review_id"] for i in open_items.json()} == {result_review["review_id"]}

        resolved_items = authenticated_client.get(
            f"/annotations/?test_run_id={test_run.id}&resolved=true"
        )
        assert resolved_items.status_code == status.HTTP_200_OK
        assert {i["review_id"] for i in resolved_items.json()} == {trace_review["review_id"]}

    def test_contradictory_trace_and_source_filters_return_empty(
        self,
        authenticated_client: TestClient,
        two_runs,
    ):
        target, _ = two_runs
        _, _, trace, _, _ = target

        response = authenticated_client.get(
            f"/annotations/?trace_id={trace.trace_id}&source=test_result"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


@pytest.mark.integration
class TestAnnotationsDualGateAuth:
    """Negative tests for the in-handler dual-gate on GET /annotations."""

    def test_forbidden_without_either_read_permission(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        authenticated_user,
        db_project,
    ):
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            with patch(
                "rhesis.backend.app.routers.annotations.authorize",
                return_value=False,
            ):
                response = authenticated_client.get("/annotations/")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        accepted = response.headers.get("X-Accepted-Permissions", "")
        assert str(Permission.TestResult.READ) in accepted
        assert str(Permission.Telemetry.READ) in accepted

    def test_forbidden_source_trace_without_telemetry_read(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        authenticated_user,
        db_project,
    ):
        def _authorize(_principal, permission, **_kwargs):
            return str(permission) == str(Permission.TestResult.READ)

        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            with patch(
                "rhesis.backend.app.routers.annotations.authorize",
                side_effect=_authorize,
            ):
                response = authenticated_client.get("/annotations/?source=trace")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.headers.get("X-Accepted-Permissions") == str(Permission.Telemetry.READ)

    @pytest.mark.parametrize(
        "query",
        [
            "trace_id=0123456789abcdef0123456789abcdef",
            "trace_db_id=11111111-1111-1111-1111-111111111111",
        ],
    )
    def test_forbidden_trace_scoped_filter_without_telemetry_read(
        self,
        query,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        authenticated_user,
        db_project,
    ):
        """Trace-only filters must 403, not silently return an empty list."""

        def _authorize(_principal, permission, **_kwargs):
            return str(permission) == str(Permission.TestResult.READ)

        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            with patch(
                "rhesis.backend.app.routers.annotations.authorize",
                side_effect=_authorize,
            ):
                response = authenticated_client.get(f"/annotations/?{query}")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.headers.get("X-Accepted-Permissions") == str(Permission.Telemetry.READ)

    def test_run_scoped_filter_with_only_telemetry_read_returns_trace_side(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        db_endpoint,
    ):
        """test_run_id spans both sources, so it degrades rather than 403s."""
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )

        def _authorize(_principal, permission, **_kwargs):
            return str(permission) == str(Permission.Telemetry.READ)

        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            test_run, _, _, result_review, trace_review = _seed_annotated_run(
                test_db,
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
                endpoint_id=db_endpoint.id,
                status_id=pass_status.id,
                marker="telemetry-only",
            )
            with patch(
                "rhesis.backend.app.routers.annotations.authorize",
                side_effect=_authorize,
            ):
                response = authenticated_client.get(f"/annotations/?test_run_id={test_run.id}")

        assert response.status_code == status.HTTP_200_OK
        ids = {i["review_id"] for i in response.json()}
        assert ids == {trace_review["review_id"]}
        assert result_review["review_id"] not in ids
