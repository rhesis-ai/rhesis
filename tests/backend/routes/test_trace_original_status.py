"""The automated verdict a trace annotation is compared against.

``original_status_id`` is snapshotted on the first annotation so
``matches_annotation`` can say whether a human disagreed with automation. A
trace without metrics has no automated verdict: its status is whatever the last
human set, so snapshotting it would record a person's call as the machine's.
"""

import uuid

from fastapi.testclient import TestClient

from rhesis.backend.app.models.trace import Trace
from tests.backend.routes.test_annotations import (
    _create_annotation,
    _ensure_pass_fail_statuses,
    _project_scope,
)
from tests.backend.routes.test_annotations_by_trace_id import _span


def _trace_annotation(client, trace_id, status_id):
    return _create_annotation(client, "Trace", trace_id, status_id, target={"type": "trace"})


class TestTraceOriginalStatus:
    def test_a_trace_without_metrics_keeps_no_automated_verdict(
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
            trace = _span(db_project.id, test_organization.id, trace_id=uuid.uuid4().hex)
            test_db.add(trace)
            test_db.commit()
            test_db.refresh(trace)

            _trace_annotation(authenticated_client, trace.id, pass_status.id)
            _trace_annotation(authenticated_client, trace.id, fail_status.id)

            test_db.expire_all()
            stored = test_db.get(Trace, trace.id)
            assert stored.original_status_id is None
            assert stored.trace_metrics_status_id == fail_status.id

    def test_a_trace_with_metrics_keeps_the_evaluator_verdict(
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
            trace = _span(db_project.id, test_organization.id, trace_id=uuid.uuid4().hex)
            trace.trace_metrics = {
                "turn_metrics": {"metrics": {"relevance": {"is_successful": False}}}
            }
            trace.trace_metrics_status_id = fail_status.id
            test_db.add(trace)
            test_db.commit()
            test_db.refresh(trace)

            _trace_annotation(authenticated_client, trace.id, pass_status.id)
            _trace_annotation(authenticated_client, trace.id, fail_status.id)

            test_db.expire_all()
            stored = test_db.get(Trace, trace.id)
            assert stored.original_status_id == fail_status.id
