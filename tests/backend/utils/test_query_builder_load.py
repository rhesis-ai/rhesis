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

from rhesis.backend.app import models, schemas
from rhesis.backend.app.crud import requirement as requirement_crud
from rhesis.backend.app.crud import tag as tag_crud
from rhesis.backend.app.crud.metric import get_metrics
from rhesis.backend.app.utils import crud_utils
from rhesis.backend.app.utils.query_utils import QueryBuilder, include
from tests.backend.routes.fixtures.data_factories import RequirementDataFactory, TestDataFactory


@pytest.fixture
def test_requirement(test_db: Session, test_org_id):
    return crud_utils.create_item(
        test_db,
        models.Requirement,
        RequirementDataFactory.sample_data(),
        organization_id=test_org_id,
    )


@pytest.fixture
def test_test(test_db: Session, test_org_id, test_requirement):
    data = TestDataFactory.sample_data()
    data["requirement_id"] = test_requirement.id
    return crud_utils.create_item(test_db, models.Test, data, organization_id=test_org_id)


def _is_loaded(instance, attr_name: str) -> bool:
    """True if attr_name is already populated on instance (no lazy load needed)."""
    return attr_name not in sa_inspect(instance).unloaded


@pytest.mark.unit
class TestIncludeConstruction:
    def test_rejects_non_relationship_attribute(self):
        """A plain column has no .uselist to dispatch joinedload/selectinload on."""
        with pytest.raises(AttributeError):
            include(models.Test.id)

    def test_rejects_empty_cols_list(self):
        """cols=[] is rejected rather than silently treated as "load everything"."""
        with pytest.raises(ValueError, match="cols=\\[\\]"):
            include(models.Test.requirement, cols=[])


@pytest.mark.unit
class TestWithRelatedColumnScoping:
    def test_scopes_columns_on_eager_loaded_relationship(
        self, test_db: Session, test_org_id, test_test, test_requirement
    ):
        # test_requirement is already fully populated in the session's identity map from
        # the fixture's create+flush; expire it so the column scoping below is what
        # actually (re)populates it, rather than reusing the already-loaded instance.
        test_db.expire_all()

        result = (
            QueryBuilder(test_db, models.Test)
            .with_organization_filter(test_org_id)
            .with_related(
                include(
                    models.Test.requirement, cols=[models.Requirement.id, models.Requirement.name]
                )
            )
            .filter_by_id(test_test.id)
        )

        assert result is not None
        # The relationship itself is eager-loaded (no lazy query needed)...
        assert _is_loaded(result, "requirement")
        # ...and the requested column is already populated...
        assert _is_loaded(result.requirement, "name")
        # ...while a column that wasn't requested stays deferred.
        assert not _is_loaded(result.requirement, "description")

    def test_omitting_cols_loads_full_related_row(
        self, test_db: Session, test_org_id, test_test, test_requirement
    ):
        """Omitting cols preserves the old "load everything" behavior."""
        result = (
            QueryBuilder(test_db, models.Test)
            .with_organization_filter(test_org_id)
            .with_related(include(models.Test.requirement), include(models.Test.status))
            .filter_by_id(test_test.id)
        )

        assert result is not None
        assert _is_loaded(result, "requirement")
        assert _is_loaded(result, "status")
        # No column scoping was requested, so the full related row loads.
        assert _is_loaded(result.requirement, "description")

    def test_mixes_scoped_and_unscoped_includes_in_one_call(
        self, test_db: Session, test_org_id, test_test, test_requirement
    ):
        result = (
            QueryBuilder(test_db, models.Test)
            .with_organization_filter(test_org_id)
            .with_related(
                include(models.Test.status),
                include(
                    models.Test.requirement, cols=[models.Requirement.id, models.Requirement.name]
                ),
            )
            .filter_by_id(test_test.id)
        )

        assert result is not None
        assert _is_loaded(result, "status")
        assert _is_loaded(result, "requirement")
        assert _is_loaded(result.requirement, "name")

    def test_scopes_columns_on_multi_hop_chain(
        self, test_db: Session, test_org_id, test_test, test_requirement
    ):
        test_db.expire_all()

        result = (
            QueryBuilder(test_db, models.Test)
            .with_organization_filter(test_org_id)
            .with_related(
                include(
                    models.Test.requirement,
                    models.Requirement.status,
                    cols=[models.Status.id, models.Status.name],
                )
            )
            .filter_by_id(test_test.id)
        )

        assert result is not None
        assert _is_loaded(result, "requirement")
        # Requirement.status may be None (not set by the data factory), but the chain
        # itself must compile and execute without error either way.
        assert _is_loaded(result.requirement, "status")


@pytest.mark.unit
class TestMetricRequirementNestedM2MLoads:
    """Regression coverage for the N+1 gap in nested many-to-many collections.

    with_default_derived_field_loads() only cascades comments/tasks/tags into
    joined single-object (many-to-one) relations -- it explicitly skips
    many-to-many. schemas.MetricDetail.requirements/test_sets (RequirementReference/
    TestSetReference) and RequirementWithMetricsSchema.metrics (schemas.Metric)
    both read derived fields on their nested rows, so those
    extra chains have to be requested explicitly in _METRIC_RELATED_FIELDS/
    _REQUIREMENT_RELATED_FIELDS -- these tests assert that eager-loading actually
    reaches those nested rows (no lazy load fires during serialization).
    """

    def test_get_metrics_loads_nested_requirement_and_test_set_derived_fields(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        from rhesis.backend.app.constants import EntityType
        from tests.backend.routes.fixtures.data_factories import (
            MetricDataFactory,
            RequirementDataFactory,
        )

        metric = crud_utils.create_item(
            test_db,
            models.Metric,
            MetricDataFactory.sample_data(),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        requirement = crud_utils.create_item(
            test_db,
            models.Requirement,
            RequirementDataFactory.sample_data(),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.execute(
            models.requirement_metric_association.insert().values(
                metric_id=metric.id,
                requirement_id=requirement.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )
        )
        tag_crud.assign_tag(
            db=test_db,
            tag=schemas.TagCreate(name="nested-requirement-tag", organization_id=test_org_id),
            entity_id=requirement.id,
            entity_type=EntityType.REQUIREMENT,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.flush()
        test_db.expire_all()

        results = get_metrics(db=test_db, skip=0, limit=100, organization_id=test_org_id)
        result = next(m for m in results if m.id == metric.id)

        assert _is_loaded(result, "requirements")
        nested_requirement = next(b for b in result.requirements if b.id == requirement.id)
        assert _is_loaded(nested_requirement, "comments")
        assert _is_loaded(nested_requirement, "tasks")
        assert _is_loaded(nested_requirement, "_tags_relationship")
        assert len(nested_requirement.tags) == 1
        assert nested_requirement.tags[0].name == "nested-requirement-tag"

    def test_get_requirement_and_get_requirements_detail_load_nested_metric_fields(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        from rhesis.backend.app.constants import EntityType
        from tests.backend.routes.fixtures.data_factories import (
            MetricDataFactory,
            RequirementDataFactory,
        )

        requirement = crud_utils.create_item(
            test_db,
            models.Requirement,
            RequirementDataFactory.sample_data(),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        metric = crud_utils.create_item(
            test_db,
            models.Metric,
            MetricDataFactory.sample_data(),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.execute(
            models.requirement_metric_association.insert().values(
                metric_id=metric.id,
                requirement_id=requirement.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )
        )
        tag_crud.assign_tag(
            db=test_db,
            tag=schemas.TagCreate(name="nested-metric-tag", organization_id=test_org_id),
            entity_id=metric.id,
            entity_type=EntityType.METRIC,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.flush()
        test_db.expire_all()

        def _nested_metric(requirement_result):
            assert _is_loaded(requirement_result, "metrics")
            nested_metric = next(m for m in requirement_result.metrics if m.id == metric.id)
            assert _is_loaded(nested_metric, "metric_type")
            assert _is_loaded(nested_metric, "backend_type")
            return nested_metric

        single = _nested_metric(
            requirement_crud.get_requirement(
                db=test_db, requirement_id=requirement.id, organization_id=test_org_id
            )
        )
        assert _is_loaded(single, "_tags_relationship")
        assert len(single.tags) == 1
        assert single.tags[0].name == "nested-metric-tag"

        # The list serializes a slim metric: no tags, and no prompt or steps.
        test_db.expire_all()
        listed = requirement_crud.get_requirements_detail(
            db=test_db, skip=0, limit=100, organization_id=test_org_id
        )
        listed_metric = _nested_metric(next(b for b in listed if b.id == requirement.id))
        for column in ("name", "description", "score_type", "metric_scope", "class_name"):
            assert _is_loaded(listed_metric, column)
        assert not _is_loaded(listed_metric, "evaluation_prompt")
        assert not _is_loaded(listed_metric, "evaluation_steps")


@pytest.mark.unit
class TestODataAnyNavigationFilter:
    """Regression coverage for OData $filter expressions that navigate a
    many-to-many relationship with `any(...)`, e.g. the frontend's
    `requirements/any(b: tolower(b/name) eq tolower('...'))` used to filter the
    metrics directory by requirement name. `odata_query`'s SQLAlchemy backend
    compiles this to an `EXISTS` subquery through the association table --
    this test locks in that it actually returns the right rows rather than
    raising or silently matching everything.
    """

    def test_get_metrics_filters_by_requirement_name_via_any(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        from tests.backend.routes.fixtures.data_factories import (
            MetricDataFactory,
            RequirementDataFactory,
        )

        matching_requirement = crud_utils.create_item(
            test_db,
            models.Requirement,
            {**RequirementDataFactory.sample_data(), "name": "Toxicity"},
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        other_requirement = crud_utils.create_item(
            test_db,
            models.Requirement,
            {**RequirementDataFactory.sample_data(), "name": "Relevance"},
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        matching_metric = crud_utils.create_item(
            test_db,
            models.Metric,
            MetricDataFactory.sample_data(),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        other_metric = crud_utils.create_item(
            test_db,
            models.Metric,
            MetricDataFactory.sample_data(),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.execute(
            models.requirement_metric_association.insert().values(
                metric_id=matching_metric.id,
                requirement_id=matching_requirement.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )
        )
        test_db.execute(
            models.requirement_metric_association.insert().values(
                metric_id=other_metric.id,
                requirement_id=other_requirement.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )
        )
        test_db.flush()
        test_db.expire_all()

        odata_filter = "requirements/any(b: tolower(b/name) eq tolower('Toxicity'))"
        results = get_metrics(
            db=test_db,
            skip=0,
            limit=100,
            filter=odata_filter,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        result_ids = {m.id for m in results}

        assert matching_metric.id in result_ids
        assert other_metric.id not in result_ids


@pytest.mark.unit
class TestTestListDerivedCascade:
    """The tests list loads the nested counts/tags TestDetail shows, and nothing else."""

    def test_nested_references_are_loaded_but_unused_relations_are_not(
        self, test_db: Session, test_org_id, test_test
    ):
        from rhesis.backend.app.crud.test import get_tests

        tests = get_tests(test_db, limit=100, organization_id=test_org_id)
        [test] = [t for t in tests if t.id == test_test.id]

        assert _is_loaded(test, "requirement")
        assert _is_loaded(test.requirement, "comments")
        for unused in ("organization", "project", "parent", "source"):
            if hasattr(models.Test, unused):
                assert not _is_loaded(test, unused), unused

    def test_cascade_limits_only_the_nested_loads(self):
        from rhesis.backend.app.utils.derived_field_loads import derived_field_load_options

        everything = derived_field_load_options(models.Test)
        own_only = derived_field_load_options(models.Test, cascade=())
        prompt_too = derived_field_load_options(models.Test, cascade=("prompt",))

        assert len(own_only) < len(prompt_too) < len(everything)


@pytest.mark.unit
class TestQueryBuilderCount:
    def test_count_skips_soft_deleted_rows(self, test_db: Session, test_org_id, test_test):
        from datetime import datetime, timezone

        before = QueryBuilder(test_db, models.Test).with_organization_filter(test_org_id).count()
        test_test.deleted_at = datetime.now(timezone.utc)
        test_db.flush()
        after = QueryBuilder(test_db, models.Test).with_organization_filter(test_org_id).count()

        assert after == before - 1

    def test_distinct_queries_keep_the_subquery_count(
        self, test_db: Session, test_org_id, test_test
    ):
        builder = QueryBuilder(test_db, models.Test).with_organization_filter(test_org_id)
        plain = builder.count()
        builder.query = builder.query.distinct()

        assert builder.count() == plain
