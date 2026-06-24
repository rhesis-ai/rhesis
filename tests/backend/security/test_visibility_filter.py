"""Deny-first tests for the visibility filter.

Verifies that ``QueryBuilder.with_visibility_filter()`` correctly hides
owner-only rows (TestSet ``visibility='user'``, Experiment
``visibility='private'``) from non-owners, while keeping shared rows
visible to all org members.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.utils.query_utils import QueryBuilder, has_visibility

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OWNER_ID = str(uuid.uuid4())
_OTHER_USER_ID = str(uuid.uuid4())
_ORG_ID = str(uuid.uuid4())


def _insert_test_set(
    db: Session,
    *,
    visibility: str = "organization",
    user_id: str = _OWNER_ID,
    organization_id: str = _ORG_ID,
) -> uuid.UUID:
    """Insert a minimal test_set row and return its id."""
    ts_id = uuid.uuid4()
    db.execute(
        text(
            """
            INSERT INTO test_set
                (id, name, visibility, user_id, organization_id,
                 created_at, updated_at)
            VALUES (:id, :name, :vis, :uid, :oid, now(), now())
            """
        ),
        {
            "id": str(ts_id),
            "name": f"ts-{ts_id.hex[:8]}",
            "vis": visibility,
            "uid": user_id,
            "oid": organization_id,
        },
    )
    db.flush()
    return ts_id


def _ensure_project(db: Session, project_id: str, organization_id: str) -> None:
    """Create a project row if it doesn't exist (for FK satisfaction)."""
    exists = db.execute(
        text("SELECT 1 FROM project WHERE id = :pid"),
        {"pid": project_id},
    ).scalar()
    if not exists:
        db.execute(
            text(
                "INSERT INTO project (id, name, organization_id, created_at, updated_at) "
                "VALUES (:pid, :name, :oid, now(), now())"
            ),
            {"pid": project_id, "name": f"proj-{project_id[:8]}", "oid": organization_id},
        )
        db.flush()


def _insert_experiment(
    db: Session,
    *,
    visibility: str = "private",
    owner_user_id: str = _OWNER_ID,
    organization_id: str = _ORG_ID,
    project_id: str | None = None,
) -> uuid.UUID:
    """Insert a minimal experiment row and return its id."""
    exp_id = uuid.uuid4()
    pid = project_id or str(uuid.uuid4())
    _ensure_project(db, pid, organization_id)
    db.execute(
        text(
            """
            INSERT INTO experiment
                (id, name, visibility, owner_user_id, organization_id, project_id,
                 versions, update_count, created_at, updated_at)
            VALUES (:id, :name, :vis, :uid, :oid, :pid,
                    '[]'::jsonb, 0, now(), now())
            """
        ),
        {
            "id": str(exp_id),
            "name": f"exp-{exp_id.hex[:8]}",
            "vis": visibility,
            "uid": owner_user_id,
            "oid": organization_id,
            "pid": pid,
        },
    )
    db.flush()
    return exp_id


# ---------------------------------------------------------------------------
# has_visibility probe
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHasVisibility:
    def test_test_set_has_visibility(self):
        assert has_visibility(models.TestSet) is True

    def test_experiment_has_visibility(self):
        assert has_visibility(models.Experiment) is True

    def test_project_no_visibility(self):
        assert has_visibility(models.Project) is False


# ---------------------------------------------------------------------------
# TestSet visibility
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestTestSetVisibility:
    """TestSet visibility='user' must be hidden from non-owners."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session, test_org_id, authenticated_user_id):
        self.db = test_db
        self.org_id = test_org_id
        self.user_id = authenticated_user_id
        self.other_user_id = _OTHER_USER_ID

    def test_org_visible_to_all(self):
        ts_id = _insert_test_set(
            self.db,
            visibility="organization",
            user_id=self.user_id,
            organization_id=self.org_id,
        )
        rows = (
            QueryBuilder(self.db, models.TestSet).with_visibility_filter(self.other_user_id).all()
        )
        assert any(r.id == ts_id for r in rows)

    def test_user_visible_to_owner(self):
        ts_id = _insert_test_set(
            self.db,
            visibility="user",
            user_id=self.user_id,
            organization_id=self.org_id,
        )
        rows = QueryBuilder(self.db, models.TestSet).with_visibility_filter(self.user_id).all()
        assert any(r.id == ts_id for r in rows)

    def test_user_hidden_from_non_owner(self):
        ts_id = _insert_test_set(
            self.db,
            visibility="user",
            user_id=self.user_id,
            organization_id=self.org_id,
        )
        rows = (
            QueryBuilder(self.db, models.TestSet).with_visibility_filter(self.other_user_id).all()
        )
        assert not any(r.id == ts_id for r in rows)

    def test_user_hidden_when_no_user_id(self):
        ts_id = _insert_test_set(
            self.db,
            visibility="user",
            user_id=self.user_id,
            organization_id=self.org_id,
        )
        rows = QueryBuilder(self.db, models.TestSet).with_visibility_filter().all()
        assert not any(r.id == ts_id for r in rows)


# ---------------------------------------------------------------------------
# Experiment visibility
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestExperimentVisibility:
    """Experiment visibility='private' must be hidden from non-owners."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db: Session, test_org_id, authenticated_user_id):
        self.db = test_db
        self.org_id = test_org_id
        self.user_id = authenticated_user_id
        self.other_user_id = _OTHER_USER_ID

    def test_shared_visible_to_all(self):
        exp_id = _insert_experiment(
            self.db,
            visibility="shared",
            owner_user_id=self.user_id,
            organization_id=self.org_id,
        )
        rows = (
            QueryBuilder(self.db, models.Experiment)
            .with_visibility_filter(self.other_user_id)
            .all()
        )
        assert any(r.id == exp_id for r in rows)

    def test_private_visible_to_owner(self):
        exp_id = _insert_experiment(
            self.db,
            visibility="private",
            owner_user_id=self.user_id,
            organization_id=self.org_id,
        )
        rows = QueryBuilder(self.db, models.Experiment).with_visibility_filter(self.user_id).all()
        assert any(r.id == exp_id for r in rows)

    def test_private_hidden_from_non_owner(self):
        exp_id = _insert_experiment(
            self.db,
            visibility="private",
            owner_user_id=self.user_id,
            organization_id=self.org_id,
        )
        rows = (
            QueryBuilder(self.db, models.Experiment)
            .with_visibility_filter(self.other_user_id)
            .all()
        )
        assert not any(r.id == exp_id for r in rows)

    def test_private_hidden_when_no_user_id(self):
        exp_id = _insert_experiment(
            self.db,
            visibility="private",
            owner_user_id=self.user_id,
            organization_id=self.org_id,
        )
        rows = QueryBuilder(self.db, models.Experiment).with_visibility_filter().all()
        assert not any(r.id == exp_id for r in rows)


# ---------------------------------------------------------------------------
# Models without visibility are unaffected
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNoVisibilityModel:
    """Models without a visibility column pass through unfiltered."""

    def test_filter_is_noop_for_project(self, test_db: Session):
        qb = QueryBuilder(test_db, models.Project)
        before = str(qb.query)
        qb.with_visibility_filter(_OTHER_USER_ID)
        after = str(qb.query)
        assert before == after


# ---------------------------------------------------------------------------
# CHECK constraint: 'public' is rejected
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPublicRemoved:
    """The migration should have removed 'public' from the CHECK constraint."""

    def test_public_rejected_by_db(self, test_db: Session):
        with pytest.raises(Exception):
            _insert_test_set(
                test_db,
                visibility="public",
                user_id=_OWNER_ID,
                organization_id=_ORG_ID,
            )
        test_db.rollback()
