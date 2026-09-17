"""Annotations go with the entity they judge, and come back with it.

An annotation is polymorphic on ``(entity_type, entity_id)``, so nothing in the
database makes it follow its parent — the cascade registry is what does, and it
has to match on both columns or an annotation on one entity would be deleted by
another entity of a different type that happens to share an id.

The reason this matters is the annotations hub: it lists rows from every entity
type at once and does not join the parent, so an annotation left behind by a
deleted parent shows up there with a deep link to nothing.

The registry is reached two ways, and both are covered end to end here:
``delete_item`` runs it for ``TestResult``, while ``crud/test.py::delete_test``
calls ``cascade_soft_delete`` itself because it soft-deletes the row directly.
``bulk_delete_tests`` is a third path, through ``bulk_delete_by_ids``.

Run with: python -m pytest tests/backend/services/test_annotation_cascade.py -v
"""

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.config.cascade_config import get_cascade_relationships
from rhesis.backend.app.constants import AnnotationTarget, EntityType
from rhesis.backend.app.crud.test import bulk_delete_tests, delete_test
from rhesis.backend.app.crud.test_result import delete_test_result
from rhesis.backend.app.database import without_soft_delete_filter
from rhesis.backend.app.services.cascade import cascade_restore, cascade_soft_delete
from rhesis.backend.app.utils.crud_utils import get_or_create_status


def _make_test(db: Session, organization_id, user_id) -> models.Test:
    prompt = models.Prompt(
        content="Does the annotation follow it?",
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(prompt)
    db.flush()
    db_test = models.Test(
        prompt_id=prompt.id,
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(db_test)
    db.flush()
    db.refresh(db_test)
    return db_test


def _make_test_result(db: Session, organization_id, user_id) -> models.TestResult:
    result = models.TestResult(organization_id=organization_id, user_id=user_id)
    db.add(result)
    db.flush()
    db.refresh(result)
    return result


def _annotate(
    db: Session,
    entity_type: str,
    entity_id,
    target_type: str,
    organization_id,
    user_id,
    target_reference=None,
) -> models.Annotation:
    status = get_or_create_status(
        db,
        name="Pass",
        entity_type=EntityType.TEST_RESULT,
        organization_id=organization_id,
        user_id=user_id,
        commit=False,
    )
    annotation = models.Annotation(
        entity_type=entity_type,
        entity_id=entity_id,
        target_type=target_type,
        target_reference=target_reference,
        status_id=status.id,
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(annotation)
    db.flush()
    db.refresh(annotation)
    return annotation


def _deleted_at(db: Session, annotation_id):
    """Read the row even once it is soft-deleted, which is the whole question."""
    db.expire_all()
    with without_soft_delete_filter():
        return (
            db.query(models.Annotation.deleted_at)
            .filter(models.Annotation.id == annotation_id)
            .scalar()
        )


@pytest.mark.unit
class TestTheRegistry:
    """Every annotatable parent is registered, and each one pins its entity type."""

    @pytest.mark.parametrize(
        ("model", "entity_type"),
        [
            (models.Test, "Test"),
            (models.TestResult, "TestResult"),
            (models.Trace, "Trace"),
        ],
    )
    def test_each_parent_cascades_to_its_own_annotations(self, model, entity_type):
        relationships = [
            rel for rel in get_cascade_relationships(model) if rel.child_model is models.Annotation
        ]

        assert len(relationships) == 1
        relationship = relationships[0]
        assert relationship.foreign_key == "entity_id"
        # Without this the id alone would match an annotation on another type.
        assert relationship.extra_filters == {"entity_type": entity_type}
        assert relationship.cascade_delete is True
        assert relationship.cascade_restore is True


@pytest.mark.integration
class TestTheCascadeItself:
    """``cascade_soft_delete`` / ``cascade_restore`` over real rows.

    Driven directly because that is the layer the registry configures; whether a
    given parent's CRUD reaches it is the next class down.
    """

    def test_it_soft_deletes_a_tests_annotations(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        db_test = _make_test(test_db, test_org_id, authenticated_user_id)
        annotation = _annotate(
            test_db,
            EntityType.TEST.value,
            db_test.id,
            AnnotationTarget.TEST.value,
            test_org_id,
            authenticated_user_id,
        )

        cascade_soft_delete(test_db, models.Test, db_test.id, test_org_id)

        assert _deleted_at(test_db, annotation.id) is not None

    def test_it_restores_them_again(self, test_db: Session, test_org_id, authenticated_user_id):
        db_test = _make_test(test_db, test_org_id, authenticated_user_id)
        annotation = _annotate(
            test_db,
            EntityType.TEST.value,
            db_test.id,
            AnnotationTarget.TEST.value,
            test_org_id,
            authenticated_user_id,
        )
        cascade_soft_delete(test_db, models.Test, db_test.id, test_org_id)

        cascade_restore(test_db, models.Test, db_test.id, test_org_id)

        assert _deleted_at(test_db, annotation.id) is None

    def test_a_tuning_judgement_goes_with_its_case(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """A metric-target annotation sits on the test too, so it cascades alike."""
        case = _make_test(test_db, test_org_id, authenticated_user_id)
        judgement = _annotate(
            test_db,
            EntityType.TEST.value,
            case.id,
            AnnotationTarget.METRIC.value,
            test_org_id,
            authenticated_user_id,
            target_reference=str(case.id),
        )

        cascade_soft_delete(test_db, models.Test, case.id, test_org_id)

        assert _deleted_at(test_db, judgement.id) is not None

    def test_an_annotation_on_a_different_entity_type_is_untouched(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """The id is the same; the entity type is what keeps them apart."""
        db_test = _make_test(test_db, test_org_id, authenticated_user_id)
        mine = _annotate(
            test_db,
            EntityType.TEST.value,
            db_test.id,
            AnnotationTarget.TEST.value,
            test_org_id,
            authenticated_user_id,
        )
        # A TestResult annotation carrying the test's id. Nothing in the database
        # stops this, which is exactly why the filter is needed.
        theirs = _annotate(
            test_db,
            EntityType.TEST_RESULT.value,
            db_test.id,
            AnnotationTarget.TEST_RESULT.value,
            test_org_id,
            authenticated_user_id,
        )

        cascade_soft_delete(test_db, models.Test, db_test.id, test_org_id)

        assert _deleted_at(test_db, mine.id) is not None
        assert _deleted_at(test_db, theirs.id) is None

    def test_another_parents_annotations_are_untouched(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        doomed = _make_test(test_db, test_org_id, authenticated_user_id)
        kept = _make_test(test_db, test_org_id, authenticated_user_id)
        on_doomed = _annotate(
            test_db,
            EntityType.TEST.value,
            doomed.id,
            AnnotationTarget.TEST.value,
            test_org_id,
            authenticated_user_id,
        )
        on_kept = _annotate(
            test_db,
            EntityType.TEST.value,
            kept.id,
            AnnotationTarget.TEST.value,
            test_org_id,
            authenticated_user_id,
        )

        cascade_soft_delete(test_db, models.Test, doomed.id, test_org_id)

        assert _deleted_at(test_db, on_doomed.id) is not None
        assert _deleted_at(test_db, on_kept.id) is None


@pytest.mark.integration
class TestDeletingThroughCrud:
    """Whether a parent's own delete actually reaches the cascade."""

    def test_deleting_a_test_result_takes_its_annotations(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        result = _make_test_result(test_db, test_org_id, authenticated_user_id)
        annotation = _annotate(
            test_db,
            EntityType.TEST_RESULT.value,
            result.id,
            AnnotationTarget.TEST_RESULT.value,
            test_org_id,
            authenticated_user_id,
        )

        delete_test_result(
            test_db,
            result.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert _deleted_at(test_db, annotation.id) is not None

    def test_deleting_a_test_takes_its_annotations(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        db_test = _make_test(test_db, test_org_id, authenticated_user_id)
        annotation = _annotate(
            test_db,
            EntityType.TEST.value,
            db_test.id,
            AnnotationTarget.TEST.value,
            test_org_id,
            authenticated_user_id,
        )

        delete_test(
            test_db,
            db_test.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert _deleted_at(test_db, annotation.id) is not None

    def test_bulk_deleting_tests_takes_their_annotations_too(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """A third path into the registry, and the one the grid's multi-select
        uses — so it has to cascade like the single delete does."""
        first = _make_test(test_db, test_org_id, authenticated_user_id)
        second = _make_test(test_db, test_org_id, authenticated_user_id)
        spared = _make_test(test_db, test_org_id, authenticated_user_id)
        annotations = [
            _annotate(
                test_db,
                EntityType.TEST.value,
                db_test.id,
                AnnotationTarget.TEST.value,
                test_org_id,
                authenticated_user_id,
            )
            for db_test in (first, second, spared)
        ]

        bulk_delete_tests(
            test_db,
            [first.id, second.id],
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert _deleted_at(test_db, annotations[0].id) is not None
        assert _deleted_at(test_db, annotations[1].id) is not None
        assert _deleted_at(test_db, annotations[2].id) is None
