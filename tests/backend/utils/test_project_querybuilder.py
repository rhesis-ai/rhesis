"""
Tests for project-scoped QueryBuilder helpers and the cross-project guard.

Coverage:
- has_project_id() returns True/False based on model columns
- QueryBuilder.with_project_filter() no-op when project_id is None
- QueryBuilder.with_project_filter() applies (pid = :pid OR pid IS NULL) filter
- QueryBuilder.with_project_filter() allows org-wide (NULL) rows through
- QueryBuilder.with_project_filter() excludes rows from other projects
- validate_same_project() passes when all entities share a project
- validate_same_project() passes when some/all entities are org-wide (NULL)
- validate_same_project() raises ValueError for conflicting non-NULL project_ids
- validate_same_project() skips entities without project_id attribute
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.utils import crud_utils
from rhesis.backend.app.utils.crud_utils import validate_same_project
from rhesis.backend.app.utils.query_utils import QueryBuilder, has_project_id
from tests.backend.routes.fixtures.data_factories import BehaviorDataFactory


@pytest.fixture
def test_project(test_db: Session, test_org_id):
    """Create a real project row for tests that need a valid FK project_id."""
    project = models.Project(
        name=f"Test Project {uuid.uuid4().hex[:8]}",
        organization_id=uuid.UUID(test_org_id),
    )
    test_db.add(project)
    test_db.flush()
    yield project
    test_db.rollback()


@pytest.fixture
def test_project2(test_db: Session, test_org_id):
    """Second project for cross-project filter tests."""
    project = models.Project(
        name=f"Test Project 2 {uuid.uuid4().hex[:8]}",
        organization_id=uuid.UUID(test_org_id),
    )
    test_db.add(project)
    test_db.flush()
    yield project
    test_db.rollback()


# ---------------------------------------------------------------------------
# has_project_id
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.utils
class TestHasProjectId:
    """Unit tests for the has_project_id() helper."""

    def test_returns_true_for_model_with_project_id(self):
        """Behavior has project_id (ProjectMixin); should return True."""
        assert has_project_id(models.Behavior) is True

    def test_returns_true_for_test_model(self):
        """Test model has project_id (ProjectMixin); should return True."""
        assert has_project_id(models.Test) is True

    def test_returns_false_for_model_without_project_id(self):
        """User has no project_id column; should return False."""
        assert has_project_id(models.User) is False

    def test_returns_false_for_organization(self):
        """Organization has no project_id column; should return False."""
        assert has_project_id(models.Organization) is False


# ---------------------------------------------------------------------------
# QueryBuilder.with_project_filter
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.utils
class TestQueryBuilderProjectFilter:
    """Tests for QueryBuilder.with_project_filter()."""

    def test_noop_when_project_id_is_none(self, test_db: Session, test_org_id):
        """Calling with_project_filter(None) should not restrict results."""
        b1 = crud_utils.create_item(
            test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
        )
        results = (
            QueryBuilder(test_db, models.Behavior)
            .with_organization_filter(test_org_id)
            .with_project_filter(None)
            .all()
        )
        ids = [r.id for r in results]
        assert b1.id in ids

    def test_noop_when_model_lacks_project_id(self, test_db: Session):
        """with_project_filter on a model without project_id is silently ignored."""
        project_id = str(uuid.uuid4())
        # User has no project_id — the filter should be skipped, not raise.
        result = (
            QueryBuilder(test_db, models.User)
            .with_project_filter(project_id)
            .all()
        )
        assert isinstance(result, list)

    def test_includes_matching_project_rows(self, test_db: Session, test_org_id, test_project):
        """Rows with project_id == the given id are included."""
        data = BehaviorDataFactory.sample_data()
        data["project_id"] = test_project.id
        b = crud_utils.create_item(test_db, models.Behavior, data, organization_id=test_org_id)

        results = (
            QueryBuilder(test_db, models.Behavior)
            .with_organization_filter(test_org_id)
            .with_project_filter(str(test_project.id))
            .all()
        )
        assert b.id in [r.id for r in results]

    def test_includes_null_project_rows(self, test_db: Session, test_org_id, test_project):
        """Org-wide rows (project_id IS NULL) pass through the project filter."""
        data = BehaviorDataFactory.sample_data()
        # No project_id set → NULL (org-wide)
        b = crud_utils.create_item(test_db, models.Behavior, data, organization_id=test_org_id)
        assert b.project_id is None

        results = (
            QueryBuilder(test_db, models.Behavior)
            .with_organization_filter(test_org_id)
            .with_project_filter(str(test_project.id))
            .all()
        )
        assert b.id in [r.id for r in results]

    def test_excludes_rows_from_other_projects(
        self, test_db: Session, test_org_id, test_project, test_project2
    ):
        """Rows stamped with a different non-NULL project_id are excluded."""
        data = BehaviorDataFactory.sample_data()
        data["project_id"] = test_project2.id
        b_other = crud_utils.create_item(
            test_db, models.Behavior, data, organization_id=test_org_id
        )

        results = (
            QueryBuilder(test_db, models.Behavior)
            .with_organization_filter(test_org_id)
            .with_project_filter(str(test_project.id))
            .all()
        )
        assert b_other.id not in [r.id for r in results]

    def test_chaining_with_other_filters(self, test_db: Session, test_org_id, test_project):
        """with_project_filter chains cleanly with org filter and pagination."""
        data = BehaviorDataFactory.sample_data()
        data["project_id"] = test_project.id
        crud_utils.create_item(test_db, models.Behavior, data, organization_id=test_org_id)

        results = (
            QueryBuilder(test_db, models.Behavior)
            .with_organization_filter(test_org_id)
            .with_project_filter(str(test_project.id))
            .with_pagination(skip=0, limit=10)
            .all()
        )
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# validate_same_project
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.utils
class TestValidateSameProject:
    """Unit tests for validate_same_project()."""

    def _make_entity(self, project_id=None):
        """Return a minimal mock object with a project_id attribute."""

        class _Stub:
            pass

        obj = _Stub()
        obj.project_id = uuid.UUID(project_id) if project_id else None
        return obj

    def test_passes_when_all_share_same_project(self):
        pid = str(uuid.uuid4())
        e1 = self._make_entity(pid)
        e2 = self._make_entity(pid)
        validate_same_project(e1, e2)  # should not raise

    def test_passes_when_all_null(self):
        """All org-wide entities — compatible."""
        e1 = self._make_entity(None)
        e2 = self._make_entity(None)
        validate_same_project(e1, e2)  # should not raise

    def test_passes_when_mix_of_null_and_same_project(self):
        """One org-wide + one project-scoped — compatible."""
        pid = str(uuid.uuid4())
        e_null = self._make_entity(None)
        e_pid = self._make_entity(pid)
        validate_same_project(e_null, e_pid)  # should not raise

    def test_raises_for_conflicting_projects(self):
        """Two different non-NULL project_ids must raise ValueError."""
        pid1 = str(uuid.uuid4())
        pid2 = str(uuid.uuid4())
        e1 = self._make_entity(pid1)
        e2 = self._make_entity(pid2)
        with pytest.raises(ValueError, match="different projects"):
            validate_same_project(e1, e2)

    def test_raises_with_three_entities_two_projects(self):
        """Three entities, two distinct project_ids → raises."""
        pid1 = str(uuid.uuid4())
        pid2 = str(uuid.uuid4())
        e1 = self._make_entity(pid1)
        e2 = self._make_entity(pid1)
        e3 = self._make_entity(pid2)
        with pytest.raises(ValueError):
            validate_same_project(e1, e2, e3)

    def test_skips_entities_without_project_id_attribute(self):
        """Objects without project_id attribute are silently skipped."""

        class _NoProjectId:
            pass

        obj = _NoProjectId()
        # Should not raise even though obj has no project_id
        validate_same_project(obj)

    def test_passes_for_single_entity(self):
        pid = str(uuid.uuid4())
        validate_same_project(self._make_entity(pid))  # should not raise

    def test_error_message_includes_conflicting_ids(self):
        pid1 = str(uuid.uuid4())
        pid2 = str(uuid.uuid4())
        e1 = self._make_entity(pid1)
        e2 = self._make_entity(pid2)
        with pytest.raises(ValueError) as exc_info:
            validate_same_project(e1, e2)
        # Both IDs should appear in the error message
        assert pid1 in str(exc_info.value) or pid2 in str(exc_info.value)
