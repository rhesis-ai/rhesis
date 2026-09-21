"""Annotating a trace by its OTEL id rather than its span row id.

An application that produced a trace knows the 32-character hex id and nothing
about the row the platform stored it under, so it cannot name the parent the
way the UI does. These tests cover the hex as a parent address on the write
side, and as a scope on the read side.

The trap this guards is quiet: a 32-character hex string also parses as a UUID,
so a trace id sent as ``entity_id`` is accepted by the route and then matches
no row. Keeping the two in separate fields is what makes that impossible.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.models.trace import Trace
from tests.backend.fixtures.rls import scope_to_project
from tests.backend.routes.test_annotations import (
    _ensure_pass_fail_statuses,
    _project_scope,
)


def _span(project_id, organization_id, *, trace_id, parent_span_id=None, name="ai.llm.invoke"):
    now = datetime.now(timezone.utc)
    return Trace(
        trace_id=trace_id,
        span_id=uuid.uuid4().hex[:16],
        parent_span_id=parent_span_id,
        project_id=project_id,
        organization_id=organization_id,
        environment="development",
        span_name=name,
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


class TestAnnotatingATraceByItsOtelId:
    """The write side: trace_id stands in for entity_id on a Trace."""

    def test_the_hex_resolves_to_the_root_span(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
    ):
        """A child span must not be picked: the annotation would hang off an
        inner step of the trace rather than the trace as a whole."""
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        hex_id = uuid.uuid4().hex
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            root = _span(db_project.id, test_organization.id, trace_id=hex_id)
            test_db.add(root)
            test_db.commit()
            test_db.refresh(root)
            child = _span(
                db_project.id,
                test_organization.id,
                trace_id=hex_id,
                parent_span_id=root.span_id,
                name="ai.tool.search",
            )
            test_db.add(child)
            test_db.commit()

            created = authenticated_client.post(
                "/annotations/",
                json={
                    "entity_type": "Trace",
                    "trace_id": hex_id,
                    "status_id": str(pass_status.id),
                    "comments": "Answered from the wrong document.",
                },
            )

            assert created.status_code == status.HTTP_200_OK, created.text
            assert created.json()["entity_id"] == str(root.id)

    def test_a_trace_that_is_not_ingested_yet_says_so(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
    ):
        """Spans arrive asynchronously, so this is usually "too early" rather
        than "wrong id", and retrying is the right response."""
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            response = authenticated_client.post(
                "/annotations/",
                json={
                    "entity_type": "Trace",
                    "trace_id": uuid.uuid4().hex,
                    "status_id": str(pass_status.id),
                },
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "ingested asynchronously" in response.json()["detail"]

    def test_two_root_spans_are_refused_rather_than_guessed(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
    ):
        """Picking one would attach the verdict to an arbitrary half of the trace."""
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        hex_id = uuid.uuid4().hex
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            test_db.add_all(
                [
                    _span(db_project.id, test_organization.id, trace_id=hex_id),
                    _span(db_project.id, test_organization.id, trace_id=hex_id),
                ]
            )
            test_db.commit()

            response = authenticated_client.post(
                "/annotations/",
                json={
                    "entity_type": "Trace",
                    "trace_id": hex_id,
                    "status_id": str(pass_status.id),
                },
            )

            assert response.status_code == status.HTTP_409_CONFLICT
            assert "more than one root span" in response.json()["detail"]

    def test_both_addresses_at_once_is_refused(
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
            response = authenticated_client.post(
                "/annotations/",
                json={
                    "entity_type": "Trace",
                    "entity_id": str(uuid.uuid4()),
                    "trace_id": uuid.uuid4().hex,
                    "status_id": str(pass_status.id),
                },
            )

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_neither_address_is_refused(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
    ):
        """entity_id used to be required outright; dropping that must not make
        a body with no parent at all acceptable."""
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            response = authenticated_client.post(
                "/annotations/",
                json={"entity_type": "Trace", "status_id": str(pass_status.id)},
            )

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_the_hex_is_refused_for_a_parent_that_is_not_a_trace(
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
            response = authenticated_client.post(
                "/annotations/",
                json={
                    "entity_type": "TestResult",
                    "trace_id": uuid.uuid4().hex,
                    "status_id": str(pass_status.id),
                },
            )

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_a_malformed_hex_is_refused(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
    ):
        """A dashed UUID is the likely mistake, and it is not a trace id."""
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            response = authenticated_client.post(
                "/annotations/",
                json={
                    "entity_type": "Trace",
                    "trace_id": str(uuid.uuid4()),
                    "status_id": str(pass_status.id),
                },
            )

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestResolutionCannotReachAnotherProject:
    """The hex is resolved by a query the caller does not scope themselves.

    Everything else about an annotation is addressed by a row id the caller
    already had, so this is the one place a lookup is driven purely by a value
    from outside. Worth pinning rather than assuming the ambient filter covers
    it.
    """

    def test_a_trace_in_another_project_does_not_resolve(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
        db_status,
    ):
        from rhesis.backend.app.models.project import Project

        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        elsewhere = Project(
            name=f"Other project {uuid.uuid4().hex[:8]}",
            organization_id=test_organization.id,
            user_id=authenticated_user.id,
            owner_id=authenticated_user.id,
            status_id=db_status.id,
        )
        test_db.add(elsewhere)
        test_db.commit()
        test_db.refresh(elsewhere)

        hex_id = uuid.uuid4().hex
        # project_isolation is RESTRICTIVE, so the span's own INSERT needs the
        # session on its project before the flush.
        scope_to_project(test_db, elsewhere.id)
        with _project_scope(test_db, test_organization.id, authenticated_user.id, elsewhere.id):
            test_db.add(_span(elsewhere.id, test_organization.id, trace_id=hex_id))
            test_db.commit()

        # Same organization, same hex, different project. Scoping the session is
        # what the next request reads its GUCs from.
        scope_to_project(test_db, db_project.id)
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            response = authenticated_client.post(
                "/annotations/",
                json={
                    "entity_type": "Trace",
                    "trace_id": hex_id,
                    "status_id": str(pass_status.id),
                },
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadingAnnotationsBackByTraceId:
    """The read side: the same hex scopes a listing."""

    def test_the_filter_returns_every_annotation_on_that_trace(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        test_type_lookup,
        db_user,
        authenticated_user,
        db_project,
    ):
        """Including one filed against a child span through the UI -- the
        caller asked about the trace, not about one span of it."""
        pass_status, _ = _ensure_pass_fail_statuses(
            test_db, test_organization, test_type_lookup, db_user
        )
        wanted, other = uuid.uuid4().hex, uuid.uuid4().hex
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            root = _span(db_project.id, test_organization.id, trace_id=wanted)
            elsewhere = _span(db_project.id, test_organization.id, trace_id=other)
            test_db.add_all([root, elsewhere])
            test_db.commit()
            test_db.refresh(root)
            child = _span(
                db_project.id,
                test_organization.id,
                trace_id=wanted,
                parent_span_id=root.span_id,
                name="ai.tool.search",
            )
            test_db.add(child)
            test_db.commit()
            test_db.refresh(child)
            test_db.refresh(elsewhere)

            on_root = authenticated_client.post(
                "/annotations/",
                json={
                    "entity_type": "Trace",
                    "trace_id": wanted,
                    "status_id": str(pass_status.id),
                },
            ).json()
            on_child = authenticated_client.post(
                "/annotations/",
                json={
                    "entity_type": "Trace",
                    "entity_id": str(child.id),
                    "status_id": str(pass_status.id),
                    "target": {"type": "trace"},
                },
            ).json()
            on_other = authenticated_client.post(
                "/annotations/",
                json={
                    "entity_type": "Trace",
                    "entity_id": str(elsewhere.id),
                    "status_id": str(pass_status.id),
                    "target": {"type": "trace"},
                },
            ).json()

            listed = authenticated_client.get(f"/annotations/?trace_id={wanted}")

            assert listed.status_code == status.HTTP_200_OK, listed.text
            found = {item["id"] for item in listed.json()}
            assert {on_root["id"], on_child["id"]} <= found
            assert on_other["id"] not in found

    def test_an_unknown_trace_lists_nothing(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        authenticated_user,
        db_project,
    ):
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            listed = authenticated_client.get(f"/annotations/?trace_id={uuid.uuid4().hex}")

            assert listed.status_code == status.HTTP_200_OK
            assert listed.json() == []

    def test_a_malformed_hex_is_refused_rather_than_listing_everything(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        authenticated_user,
        db_project,
    ):
        """An unvalidated filter that silently drops would return every
        annotation in the project, which reads as a successful answer."""
        with _project_scope(test_db, test_organization.id, authenticated_user.id, db_project.id):
            listed = authenticated_client.get("/annotations/?trace_id=not-a-trace-id")

            assert listed.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
