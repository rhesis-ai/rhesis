"""Tests for annotation CRUD endpoints: POST/GET/PUT/DELETE /annotations/."""

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.models.status import Status
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_result import TestResult
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.scope import RequestScope


@contextmanager
def _project_scope(test_db, organization_id, user_id, project_id):
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


def _create_annotation(client, entity_type, entity_id, status_id, **kwargs):
    body = {
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "status_id": str(status_id),
        "comments": kwargs.get("comments", "test annotation"),
    }
    target = kwargs.get("target")
    if target:
        body["target"] = target
    resp = client.post("/annotations/", json=body)
    assert resp.status_code == status.HTTP_200_OK, resp.text
    return resp.json()


@pytest.mark.integration
class TestAnnotationCRUD:
    def test_create_and_read(
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
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            result = TestResult(
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
            )
            test_db.add(result)
            test_db.commit()
            test_db.refresh(result)

            created = _create_annotation(
                authenticated_client,
                "TestResult",
                result.id,
                pass_status.id,
                comments="Looks correct",
            )

            assert created["entity_type"] == "TestResult"
            assert created["entity_id"] == str(result.id)
            assert created["status"]["name"] == "Pass"
            assert created["comments"] == "Looks correct"

            detail = authenticated_client.get(f"/annotations/{created['id']}")
            assert detail.status_code == status.HTTP_200_OK
            assert detail.json()["id"] == created["id"]

    def test_update_annotation(
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
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            result = TestResult(
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
            )
            test_db.add(result)
            test_db.commit()
            test_db.refresh(result)

            created = _create_annotation(
                authenticated_client, "TestResult", result.id, pass_status.id
            )

            updated = authenticated_client.put(
                f"/annotations/{created['id']}",
                json={
                    "status_id": str(fail_status.id),
                    "comments": "Actually wrong",
                },
            )
            assert updated.status_code == status.HTTP_200_OK
            body = updated.json()
            assert body["status"]["name"] == "Fail"
            assert body["comments"] == "Actually wrong"

    def test_delete_annotation(
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
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            result = TestResult(
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
            )
            test_db.add(result)
            test_db.commit()
            test_db.refresh(result)

            created = _create_annotation(
                authenticated_client, "TestResult", result.id, pass_status.id
            )

            deleted = authenticated_client.delete(f"/annotations/{created['id']}")
            assert deleted.status_code == status.HTTP_200_OK

            gone = authenticated_client.get(f"/annotations/{created['id']}")
            assert gone.status_code == status.HTTP_410_GONE

    def test_read_nonexistent_annotation_404s(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        authenticated_user,
        db_project,
    ):
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            resp = authenticated_client.get(f"/annotations/{uuid.uuid4()}")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


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

    def test_list_returns_annotations_with_context(
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
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            test_config = TestConfiguration(
                endpoint_id=db_endpoint.id,
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
            )
            test_db.add(test_config)
            test_db.flush()

            test_run = TestRun(
                name="annotation-list-run",
                test_configuration_id=test_config.id,
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
            )
            test_db.add(test_run)
            test_db.flush()

            result = TestResult(
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
                test_configuration_id=test_config.id,
                test_run_id=test_run.id,
            )
            test_db.add(result)
            test_db.commit()
            test_db.refresh(result)

            created = _create_annotation(
                authenticated_client,
                "TestResult",
                result.id,
                pass_status.id,
                comments="context check",
            )

            listing = authenticated_client.get("/annotations/")
            assert listing.status_code == status.HTTP_200_OK
            data = listing.json()
            assert len(data) >= 1
            assert int(listing.headers.get("X-Total-Count", "0")) >= 1

            item = next(i for i in data if i["id"] == created["id"])
            assert item["entity_type"] == "TestResult"
            assert item["context"]["test_run_id"] == str(test_run.id)
            assert item["context"]["test_run_name"] == "annotation-list-run"

    def test_filter_by_rating(
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
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            result = TestResult(
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
            )
            test_db.add(result)
            test_db.commit()
            test_db.refresh(result)

            _create_annotation(
                authenticated_client,
                "TestResult",
                result.id,
                pass_status.id,
                comments="good",
            )
            fail_ann = _create_annotation(
                authenticated_client,
                "TestResult",
                result.id,
                fail_status.id,
                comments="bad",
            )

            fail_only = authenticated_client.get("/annotations/?rating=Fail")
            assert fail_only.status_code == status.HTTP_200_OK
            ids = {i["id"] for i in fail_only.json()}
            assert fail_ann["id"] in ids

    def test_filter_by_resolved(
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
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            result = TestResult(
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
            )
            test_db.add(result)
            test_db.commit()
            test_db.refresh(result)

            open_ann = _create_annotation(
                authenticated_client,
                "TestResult",
                result.id,
                pass_status.id,
                comments="open",
            )

            resolved_ann = _create_annotation(
                authenticated_client,
                "TestResult",
                result.id,
                pass_status.id,
                comments="resolved",
            )
            authenticated_client.put(
                f"/annotations/{resolved_ann['id']}",
                json={"resolved": True},
            )

            open_only = authenticated_client.get("/annotations/?resolved=false")
            assert open_only.status_code == status.HTTP_200_OK
            open_ids = {i["id"] for i in open_only.json()}
            assert open_ann["id"] in open_ids
            assert resolved_ann["id"] not in open_ids

    def test_filter_by_entity_type(
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
        now = datetime.now(timezone.utc)
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            result = TestResult(
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
            )
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
            )
            test_db.add_all([result, trace])
            test_db.commit()
            test_db.refresh(result)
            test_db.refresh(trace)

            result_ann = _create_annotation(
                authenticated_client, "TestResult", result.id, pass_status.id
            )
            trace_ann = _create_annotation(
                authenticated_client,
                "Trace",
                trace.id,
                pass_status.id,
                target={"type": "trace"},
            )

            tr_only = authenticated_client.get("/annotations/?entity_type=TestResult")
            assert tr_only.status_code == status.HTTP_200_OK
            assert all(i["entity_type"] == "TestResult" for i in tr_only.json())

            trace_only = authenticated_client.get("/annotations/?entity_type=Trace")
            assert trace_only.status_code == status.HTTP_200_OK
            assert all(i["entity_type"] == "Trace" for i in trace_only.json())

    def test_search_by_comment(
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
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            result = TestResult(
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
            )
            test_db.add(result)
            test_db.commit()
            test_db.refresh(result)

            marker = f"unique-search-{uuid.uuid4().hex[:8]}"
            created = _create_annotation(
                authenticated_client,
                "TestResult",
                result.id,
                pass_status.id,
                comments=marker,
            )

            found = authenticated_client.get(f"/annotations/?search={marker}")
            assert found.status_code == status.HTTP_200_OK
            assert any(i["id"] == created["id"] for i in found.json())


@pytest.mark.integration
class TestAnnotationScoping:
    @pytest.fixture
    def annotated_run(
        self,
        authenticated_client,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        db_endpoint,
    ):
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        now = datetime.now(timezone.utc)
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            test_config = TestConfiguration(
                endpoint_id=db_endpoint.id,
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
            )
            test_db.add(test_config)
            test_db.flush()

            test_run = TestRun(
                name="scoped-run",
                test_configuration_id=test_config.id,
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
            )
            test_db.add(test_run)
            test_db.flush()

            result = TestResult(
                organization_id=test_organization.id,
                user_id=authenticated_user.id,
                project_id=db_project.id,
                test_configuration_id=test_config.id,
                test_run_id=test_run.id,
            )
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
                test_run_id=test_run.id,
                test_result_id=None,
            )
            test_db.add_all([result, trace])
            test_db.commit()
            test_db.refresh(result)
            test_db.refresh(trace)

            trace.test_result_id = result.id
            test_db.commit()

            result_ann = _create_annotation(
                authenticated_client, "TestResult", result.id, pass_status.id,
                comments="scoped-result",
            )
            trace_ann = _create_annotation(
                authenticated_client, "Trace", trace.id, pass_status.id,
                comments="scoped-trace",
                target={"type": "trace"},
            )

            return {
                "test_run": test_run,
                "result": result,
                "trace": trace,
                "result_ann": result_ann,
                "trace_ann": trace_ann,
                "pass_status": pass_status,
            }

    def test_scope_by_test_run_id(
        self, authenticated_client, annotated_run,
    ):
        run_id = annotated_run["test_run"].id
        response = authenticated_client.get(f"/annotations/?test_run_id={run_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        ids = {i["id"] for i in data}
        assert annotated_run["result_ann"]["id"] in ids
        assert annotated_run["trace_ann"]["id"] in ids

    def test_entity_endpoint(
        self, authenticated_client, annotated_run,
    ):
        result_id = annotated_run["result"].id
        response = authenticated_client.get(f"/annotations/entity/TestResult/{result_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
        assert all(i["entity_type"] == "TestResult" for i in data)
        assert any(i["id"] == annotated_run["result_ann"]["id"] for i in data)
