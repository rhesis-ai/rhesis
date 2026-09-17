"""What `_load_parent` refuses to annotate.

It queries the parent by id alone, with no explicit organization or
``deleted_at`` predicate. That is deliberate: the ambient scope listeners add
both (``models/scope_events.py`` auto-filter, ``models/soft_delete_events.py``
before_compile), and RLS is a third layer underneath. These tests pin the
behaviour so a future relaxation of either listener fails here rather than
silently turning into a cross-tenant read.

Route tests bypass the real ``get_tenant_db_session`` and copy
``test_db.info`` onto the request session instead (``fixtures/client.py``), so
the org scope a real request carries has to be bound explicitly here. Without
that the auto-filter no-ops on an unset scope and the cross-tenant case passes
for the wrong reason.
"""

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rhesis.backend.app.models.status import Status
from rhesis.backend.app.models.test_result import TestResult
from rhesis.backend.app.scope import RequestScope, bypass_tenant_filter
from tests.backend.fixtures.test_setup import create_test_organization


def _pass_status(test_db, organization_id):
    return (
        test_db.query(Status)
        .filter(Status.name == "Pass", Status.organization_id == organization_id)
        .first()
    )


@contextmanager
def _caller_scope(test_db, organization_id, user_id):
    """Bind what a real request would carry, since the client fixture copies this."""
    previous = test_db.info.get("_scope")
    test_db.info["_scope"] = RequestScope(
        organization_id=str(organization_id),
        user_id=str(user_id),
        project_id=None,
    )
    try:
        yield
    finally:
        if previous is None:
            test_db.info.pop("_scope", None)
        else:
            test_db.info["_scope"] = previous


def _annotate(client, entity_id, status_id):
    return client.post(
        "/annotations/",
        json={
            "entity_type": "TestResult",
            "entity_id": str(entity_id),
            "status_id": str(status_id),
            "comments": "should never land",
        },
    )


@pytest.mark.integration
class TestParentIsolation:
    def test_a_parent_in_another_organization_is_not_found(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        authenticated_user,
    ):
        """A result belonging to a different org reads as missing, not forbidden."""
        other_org = create_test_organization(test_db, f"Other Org {uuid.uuid4().hex[:8]}")

        # Written under the other org's scope, so it is a genuine foreign row.
        previous = test_db.info.get("_scope")
        test_db.info["_scope"] = RequestScope(
            organization_id=str(other_org.id),
            user_id=str(authenticated_user.id),
            project_id=None,
        )
        try:
            foreign = TestResult(
                organization_id=other_org.id,
                user_id=authenticated_user.id,
            )
            test_db.add(foreign)
            test_db.commit()
            foreign_id = foreign.id
        finally:
            if previous is None:
                test_db.info.pop("_scope", None)
            else:
                test_db.info["_scope"] = previous

        pass_status = _pass_status(test_db, test_organization.id)
        with _caller_scope(test_db, test_organization.id, authenticated_user.id):
            response = _annotate(authenticated_client, foreign_id, pass_status.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text

        # And nothing was written against it.
        with bypass_tenant_filter():
            from rhesis.backend.app.models.annotation import Annotation

            leaked = test_db.query(Annotation).filter(Annotation.entity_id == foreign_id).count()
        assert leaked == 0

    def test_a_soft_deleted_parent_is_not_found(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        authenticated_user,
    ):
        """The soft-delete listener hides it, so no explicit deleted_at filter is needed."""
        result = TestResult(
            organization_id=test_organization.id,
            user_id=authenticated_user.id,
        )
        test_db.add(result)
        test_db.commit()
        test_db.refresh(result)

        result.deleted_at = datetime.now(timezone.utc)
        test_db.commit()

        pass_status = _pass_status(test_db, test_organization.id)
        with _caller_scope(test_db, test_organization.id, authenticated_user.id):
            response = _annotate(authenticated_client, result.id, pass_status.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text

    def test_a_live_parent_in_the_callers_org_still_works(
        self,
        authenticated_client: TestClient,
        test_db,
        test_organization,
        authenticated_user,
    ):
        """The control: the same request against a visible parent succeeds."""
        result = TestResult(
            organization_id=test_organization.id,
            user_id=authenticated_user.id,
        )
        test_db.add(result)
        test_db.commit()
        test_db.refresh(result)

        pass_status = _pass_status(test_db, test_organization.id)
        with _caller_scope(test_db, test_organization.id, authenticated_user.id):
            response = _annotate(authenticated_client, result.id, pass_status.id)

        assert response.status_code == status.HTTP_200_OK, response.text
