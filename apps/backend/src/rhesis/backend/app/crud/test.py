"""Per-entity CRUD for tests.

Follows the split convention described in ``apps/backend/AGENTS.md`` --
anything that would have been added to ``crud/__init__.py`` goes here.
"""

from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from rhesis.backend.app.models.category import Category
from rhesis.backend.app.models.requirement import Requirement
from rhesis.backend.app.models.test import Test, test_test_set_association
from rhesis.backend.app.models.topic import Topic
from rhesis.backend.app.models.type_lookup import TypeLookup


def get_test_facets(
    db: Session,
    *,
    organization_id: str,
    project_id: UUID | None = None,
    test_set_id: UUID | None = None,
) -> dict[str, list[str]]:
    """Return the distinct requirement/category/topic/test-type values that
    appear on at least one visible test.

    When *test_set_id* is provided, only tests linked to that set are
    considered, so a filter drawer offers exactly the values its grid can match.

    Every predicate on ``Test`` is spelled out here rather than left to the
    ambient listeners, because neither one covers this query shape: the
    soft-delete listener reads ``column_descriptions``, which for a
    column-narrowed select names the lookup table and not ``Test``, and the
    scope listener's ``with_loader_criteria`` is likewise keyed to the entities
    the ORM sees selected. Without these, soft-deleted and out-of-project tests
    would contribute filter options.
    """
    test_predicates = [
        Test.deleted_at.is_(None),
        Test.explorer_row.is_(False),
        Test.metric_id.is_(None),
        Test.organization_id == organization_id,
    ]
    if project_id is not None:
        # Mirrors the ambient project predicate: org-wide rows carry no project.
        test_predicates.append(or_(Test.project_id == project_id, Test.project_id.is_(None)))

    def _distinct_names(entity_cls, fk_col, name_attr: str = "name") -> list[str]:
        col = getattr(entity_cls, name_attr)
        query = (
            db.query(col)
            .join(Test, fk_col == entity_cls.id)
            .filter(col.isnot(None), *test_predicates)
        )
        if test_set_id is not None:
            # The association table is tenant-scoped too, so it carries the org
            # predicate as well: Test being filtered already rules out
            # cross-org rows, but neither join should be the one thing holding
            # that line.
            query = query.join(
                test_test_set_association,
                test_test_set_association.c.test_id == Test.id,
            ).filter(
                test_test_set_association.c.test_set_id == test_set_id,
                test_test_set_association.c.organization_id == organization_id,
            )
        return [name for (name,) in query.distinct().order_by(col).all()]

    return {
        "requirements": _distinct_names(Requirement, Test.requirement_id),
        "categories": _distinct_names(Category, Test.category_id),
        "topics": _distinct_names(Topic, Test.topic_id),
        "test_types": _distinct_names(TypeLookup, Test.test_type_id, "type_value"),
    }
