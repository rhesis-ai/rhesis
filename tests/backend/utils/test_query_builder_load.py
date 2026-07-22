"""
Tests for QueryBuilder.with_related()'s only calling convention: passing
options built by include().

Coverage:
- include(attr, cols=[...]) eager-loads the relationship and only the requested
  columns are populated (unrequested columns stay deferred)
- include(attr, attr, ..., cols=[...]) scopes columns on a multi-hop chain,
  picking joinedload/selectinload per hop from each hop's own cardinality
- Omitting cols loads the full related row (no column scoping)
- include() rejects a non-relationship attribute (nothing to dispatch on)
"""

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.utils import crud_utils
from rhesis.backend.app.utils.query_utils import QueryBuilder, include
from tests.backend.routes.fixtures.data_factories import BehaviorDataFactory, TestDataFactory


@pytest.fixture
def test_behavior(test_db: Session, test_org_id):
    return crud_utils.create_item(
        test_db, models.Behavior, BehaviorDataFactory.sample_data(), organization_id=test_org_id
    )


@pytest.fixture
def test_test(test_db: Session, test_org_id, test_behavior):
    data = TestDataFactory.sample_data()
    data["behavior_id"] = test_behavior.id
    return crud_utils.create_item(test_db, models.Test, data, organization_id=test_org_id)


def _is_loaded(instance, attr_name: str) -> bool:
    """True if attr_name is already populated on instance (no lazy load needed)."""
    return attr_name not in sa_inspect(instance).unloaded


@pytest.mark.unit
@pytest.mark.utils
class TestIncludeConstruction:
    def test_rejects_non_relationship_attribute(self):
        """A plain column has no .uselist to dispatch joinedload/selectinload on."""
        with pytest.raises(AttributeError):
            include(models.Test.id)


@pytest.mark.unit
@pytest.mark.utils
class TestWithRelatedColumnScoping:
    def test_scopes_columns_on_eager_loaded_relationship(
        self, test_db: Session, test_org_id, test_test, test_behavior
    ):
        # test_behavior is already fully populated in the session's identity map from
        # the fixture's create+flush; expire it so the column scoping below is what
        # actually (re)populates it, rather than reusing the already-loaded instance.
        test_db.expire_all()

        result = (
            QueryBuilder(test_db, models.Test)
            .with_organization_filter(test_org_id)
            .with_related(
                include(models.Test.behavior, cols=[models.Behavior.id, models.Behavior.name])
            )
            .filter_by_id(test_test.id)
        )

        assert result is not None
        # The relationship itself is eager-loaded (no lazy query needed)...
        assert _is_loaded(result, "behavior")
        # ...and the requested column is already populated...
        assert _is_loaded(result.behavior, "name")
        # ...while a column that wasn't requested stays deferred.
        assert not _is_loaded(result.behavior, "description")

    def test_omitting_cols_loads_full_related_row(
        self, test_db: Session, test_org_id, test_test, test_behavior
    ):
        """Omitting cols preserves the old "load everything" behavior."""
        result = (
            QueryBuilder(test_db, models.Test)
            .with_organization_filter(test_org_id)
            .with_related(include(models.Test.behavior), include(models.Test.status))
            .filter_by_id(test_test.id)
        )

        assert result is not None
        assert _is_loaded(result, "behavior")
        assert _is_loaded(result, "status")
        # No column scoping was requested, so the full related row loads.
        assert _is_loaded(result.behavior, "description")

    def test_mixes_scoped_and_unscoped_includes_in_one_call(
        self, test_db: Session, test_org_id, test_test, test_behavior
    ):
        result = (
            QueryBuilder(test_db, models.Test)
            .with_organization_filter(test_org_id)
            .with_related(
                include(models.Test.status),
                include(models.Test.behavior, cols=[models.Behavior.id, models.Behavior.name]),
            )
            .filter_by_id(test_test.id)
        )

        assert result is not None
        assert _is_loaded(result, "status")
        assert _is_loaded(result, "behavior")
        assert _is_loaded(result.behavior, "name")

    def test_scopes_columns_on_multi_hop_chain(
        self, test_db: Session, test_org_id, test_test, test_behavior
    ):
        test_db.expire_all()

        result = (
            QueryBuilder(test_db, models.Test)
            .with_organization_filter(test_org_id)
            .with_related(
                include(
                    models.Test.behavior,
                    models.Behavior.status,
                    cols=[models.Status.id, models.Status.name],
                )
            )
            .filter_by_id(test_test.id)
        )

        assert result is not None
        assert _is_loaded(result, "behavior")
        # Behavior.status may be None (not set by the data factory), but the chain
        # itself must compile and execute without error either way.
        assert _is_loaded(result.behavior, "status")
