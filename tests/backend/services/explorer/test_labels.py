"""Tests for the human label on an explorer test, which is an annotation on it.

A label has two possible authors. A metric that evaluated the test writes
``pass``/``fail`` into ``test_metadata`` naming itself as the ``labeler``; a
person who labels the same test writes an ``annotation`` row. The whole point of
keeping them apart is that "the metric said fail, a human said pass" is now
expressible, so most of what is pinned here is the precedence between the two and
the fact that neither write clobbers the other.

Labels are per person, which is the one place the explorer differs from the rest
of annotations: a tree cell shows one label, so labelling a test twice moves your
row instead of adding a second one, and clearing it removes yours and leaves
everyone else's alone.

Run with: python -m pytest tests/backend/services/explorer/test_labels.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import models
from rhesis.backend.app.constants import AnnotationTarget, EntityType
from rhesis.backend.app.schemas.explorer_metadata import ExplorerTestMetadata
from rhesis.backend.app.services.explorer.evaluation import _collect_evaluation_targets
from rhesis.backend.app.services.explorer.labels import (
    CLEARED,
    HUMAN_LABELER,
    effective_label,
    entity_level,
    is_human_label,
    label_of,
    set_label,
)
from rhesis.backend.app.services.explorer.tests import create_test_node, update_test_node
from rhesis.backend.app.utils.crud_utils import get_or_create_status


def _status(db: Session, name: str, organization_id, user_id) -> models.Status:
    """A Pass/Fail status row, which is where a human label is stored."""
    return get_or_create_status(
        db,
        name=name,
        entity_type=EntityType.TEST_RESULT,
        organization_id=organization_id,
        user_id=user_id,
        commit=False,
    )


def _annotation(db: Session, name: str, organization_id, user_id, **overrides):
    """An unsaved entity-level label annotation, for the pure-function tests."""
    return models.Annotation(
        entity_type=EntityType.TEST.value,
        entity_id=overrides.pop("entity_id", uuid.uuid4()),
        target_type=overrides.pop("target_type", AnnotationTarget.TEST.value),
        status=_status(db, name, organization_id, user_id),
        **overrides,
    )


def _labels_on(db: Session, test_id) -> list:
    """``(status name, author)`` for every live label on a test, newest first."""
    db.expire_all()
    rows = (
        db.query(models.Annotation)
        .options(joinedload(models.Annotation.status))
        .filter(
            models.Annotation.entity_type == EntityType.TEST.value,
            models.Annotation.entity_id == uuid.UUID(str(test_id)),
            models.Annotation.target_type == AnnotationTarget.TEST.value,
            models.Annotation.deleted_at.is_(None),
        )
        .order_by(models.Annotation.created_at.desc())
        .all()
    )
    return [(row.status.name, str(row.user_id)) for row in rows]


def _metadata_of(db: Session, test_id) -> dict:
    db.expire_all()
    db_test = db.query(models.Test).filter(models.Test.id == uuid.UUID(str(test_id))).first()
    return db_test.test_metadata or {}


def _second_user(db: Session, organization_id) -> models.User:
    """Another real person, so "somebody else's label" means somebody else's."""
    suffix = uuid.uuid4().hex[:10]
    user = models.User(
        email=f"explorer-labeller-{suffix}@rhesis-test.com",
        name=f"Explorer Labeller {suffix}",
        is_active=True,
        auth0_id=f"auth0|{suffix}",
        organization_id=organization_id,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


@pytest.mark.unit
class TestIsHumanLabel:
    """Which writes are a person's judgement and so become an annotation."""

    @pytest.mark.parametrize("label", ["pass", "fail"])
    def test_a_verdict_from_a_person_is_one(self, label):
        assert is_human_label(label, HUMAN_LABELER) is True

    def test_a_metrics_own_verdict_is_not(self):
        """It is a fact about what the metric said, not a judgement of it."""
        assert is_human_label("pass", "answer_relevancy") is False

    def test_an_imported_verdict_is_not(self):
        """A copy must not arrive as an annotation attributed to anybody."""
        assert is_human_label("pass", "imported") is False

    @pytest.mark.parametrize("label", ["", "error", "topic_marker"])
    def test_anything_that_is_not_a_verdict_is_not(self, label):
        assert is_human_label(label, HUMAN_LABELER) is False


@pytest.mark.integration
class TestReadingALabelOffAnAnnotation:
    def test_pass_and_fail_are_recognized(self, test_db, test_org_id, authenticated_user_id):
        for name, expected in (("Pass", "pass"), ("Fail", "fail")):
            annotation = _annotation(test_db, name, test_org_id, authenticated_user_id)

            assert label_of(annotation) == expected

    def test_any_other_status_is_not_a_label(self, test_db, test_org_id, authenticated_user_id):
        """An organization can define statuses the explorer knows nothing about,
        and reading one of those as a label would invent a verdict."""
        annotation = _annotation(test_db, "Inconclusive", test_org_id, authenticated_user_id)

        assert label_of(annotation) is None

    def test_a_tuning_judgement_on_the_same_row_is_not_a_label(
        self, test_db, test_org_id, authenticated_user_id
    ):
        """It targets a metric, not the test, so it says nothing about the test."""
        judgement = _annotation(
            test_db,
            "Pass",
            test_org_id,
            authenticated_user_id,
            target_type=AnnotationTarget.METRIC.value,
            target_reference=str(uuid.uuid4()),
        )

        assert entity_level([judgement]) == []


@pytest.mark.integration
class TestEffectiveLabelPrecedence:
    """A person's label beats a metric's, and the labeler says which you got."""

    def test_a_human_label_wins_over_the_metrics(self, test_db, test_org_id, authenticated_user_id):
        """The disagreement the explorer exists to surface."""
        meta = ExplorerTestMetadata(label="fail", labeler="answer_relevancy")
        annotation = _annotation(test_db, "Pass", test_org_id, authenticated_user_id)

        assert effective_label(meta, [annotation]) == ("pass", HUMAN_LABELER)

    def test_the_metrics_label_stands_when_nobody_has_labelled_it(self):
        meta = ExplorerTestMetadata(label="fail", labeler="answer_relevancy")

        assert effective_label(meta, []) == ("fail", "answer_relevancy")

    def test_the_newest_human_label_is_the_one_that_shows(
        self, test_db, test_org_id, authenticated_user_id
    ):
        """Annotations arrive newest first, so the first one carrying a verdict wins."""
        newest = _annotation(test_db, "Fail", test_org_id, authenticated_user_id)
        older = _annotation(test_db, "Pass", test_org_id, authenticated_user_id)

        assert effective_label(ExplorerTestMetadata(), [newest, older]) == ("fail", HUMAN_LABELER)

    def test_a_row_naming_no_labeler_hands_back_none(self):
        """Not a default: the tree shows "imported" and a copy stamps itself, and
        choosing either here would silently override the other."""
        assert effective_label(ExplorerTestMetadata(label="pass"), []) == ("pass", None)

    def test_an_unlabelled_test_is_unlabelled(self):
        assert effective_label(ExplorerTestMetadata(labeler=""), []) == ("", "")


@pytest.mark.integration
class TestSettingALabel:
    """``set_label`` records, moves and clears the caller's own label."""

    def _test_id(self, db, test_set, org_id, user_id) -> str:
        node = create_test_node(
            db=db,
            test_set_id=test_set.id,
            organization_id=org_id,
            user_id=user_id,
            input="Does it label?",
            topic="Safety",
        )
        return node.id

    def test_recording_a_label_creates_the_annotation(
        self, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        test_id = self._test_id(test_db, explorer_test_set, test_org_id, authenticated_user_id)

        set_label(test_db, uuid.UUID(test_id), "fail", test_org_id, authenticated_user_id)

        assert _labels_on(test_db, test_id) == [("Fail", str(authenticated_user_id))]

    def test_labelling_twice_moves_your_label_rather_than_adding_one(
        self, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        """A tree cell shows one label, so editing yours has to be editing."""
        test_id = self._test_id(test_db, explorer_test_set, test_org_id, authenticated_user_id)

        set_label(test_db, uuid.UUID(test_id), "pass", test_org_id, authenticated_user_id)
        set_label(test_db, uuid.UUID(test_id), "fail", test_org_id, authenticated_user_id)

        assert _labels_on(test_db, test_id) == [("Fail", str(authenticated_user_id))]

    def test_clearing_removes_your_label(
        self, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        test_id = self._test_id(test_db, explorer_test_set, test_org_id, authenticated_user_id)
        set_label(test_db, uuid.UUID(test_id), "pass", test_org_id, authenticated_user_id)

        assert (
            set_label(test_db, uuid.UUID(test_id), CLEARED, test_org_id, authenticated_user_id)
            is None
        )
        assert _labels_on(test_db, test_id) == []

    def test_clearing_a_label_nobody_set_is_not_an_error(
        self, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        test_id = self._test_id(test_db, explorer_test_set, test_org_id, authenticated_user_id)

        assert (
            set_label(test_db, uuid.UUID(test_id), CLEARED, test_org_id, authenticated_user_id)
            is None
        )
        assert _labels_on(test_db, test_id) == []

    def test_labels_are_per_person(
        self, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        """Two people can disagree about the same test, and both rows stand."""
        test_id = self._test_id(test_db, explorer_test_set, test_org_id, authenticated_user_id)
        other = _second_user(test_db, test_org_id)

        set_label(test_db, uuid.UUID(test_id), "pass", test_org_id, authenticated_user_id)
        set_label(test_db, uuid.UUID(test_id), "fail", test_org_id, str(other.id))

        assert sorted(_labels_on(test_db, test_id)) == sorted(
            [("Pass", str(authenticated_user_id)), ("Fail", str(other.id))]
        )

    def test_clearing_yours_leaves_everyone_elses_alone(
        self, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        test_id = self._test_id(test_db, explorer_test_set, test_org_id, authenticated_user_id)
        other = _second_user(test_db, test_org_id)
        set_label(test_db, uuid.UUID(test_id), "pass", test_org_id, authenticated_user_id)
        set_label(test_db, uuid.UUID(test_id), "fail", test_org_id, str(other.id))

        set_label(test_db, uuid.UUID(test_id), CLEARED, test_org_id, authenticated_user_id)

        assert _labels_on(test_db, test_id) == [("Fail", str(other.id))]

    @pytest.mark.parametrize("label", ["error", "topic_marker", "maybe"])
    def test_a_label_that_is_not_a_verdict_is_left_to_the_metadata(
        self, label, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        """``error`` comes from a failed metric call, not from a person."""
        test_id = self._test_id(test_db, explorer_test_set, test_org_id, authenticated_user_id)

        assert (
            set_label(test_db, uuid.UUID(test_id), label, test_org_id, authenticated_user_id)
            is None
        )
        assert _labels_on(test_db, test_id) == []


@pytest.mark.integration
class TestWritingANodesLabel:
    """``create_test_node`` and ``update_test_node`` route a label by its author."""

    def test_creating_with_a_human_label_writes_an_annotation_not_metadata(
        self, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        """Two copies of one label would disagree the first time either changed."""
        node = create_test_node(
            db=test_db,
            test_set_id=explorer_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            input="A person judged this",
            topic="Safety",
            label="fail",
            labeler=HUMAN_LABELER,
        )

        assert node.label == "fail"
        assert node.labeler == HUMAN_LABELER
        assert node.annotations_count == 1
        assert _labels_on(test_db, node.id) == [("Fail", str(authenticated_user_id))]
        assert _metadata_of(test_db, node.id).get("label", "") == ""

    def test_creating_with_a_metrics_label_writes_metadata_not_an_annotation(
        self, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        node = create_test_node(
            db=test_db,
            test_set_id=explorer_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            input="A metric judged this",
            topic="Safety",
            label="pass",
            labeler="answer_relevancy",
        )

        assert node.label == "pass"
        assert node.labeler == "answer_relevancy"
        assert node.annotations_count == 0
        assert _labels_on(test_db, node.id) == []
        assert _metadata_of(test_db, node.id)["label"] == "pass"

    def test_updating_a_label_never_touches_the_metadata(
        self, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        """So a person's label cannot overwrite what the metric said."""
        node = create_test_node(
            db=test_db,
            test_set_id=explorer_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            input="The metric had a view",
            topic="Safety",
            label="fail",
            labeler="answer_relevancy",
        )

        updated = update_test_node(
            db=test_db,
            test_set_id=explorer_test_set.id,
            test_id=uuid.UUID(node.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            label="pass",
        )

        assert updated.label == "pass"
        assert updated.labeler == HUMAN_LABELER
        assert updated.last_annotation is not None
        # The metric's verdict is still there underneath, untouched.
        assert _metadata_of(test_db, node.id)["label"] == "fail"
        assert _metadata_of(test_db, node.id)["labeler"] == "answer_relevancy"

    def test_clearing_a_label_falls_back_to_the_metrics(
        self, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        node = create_test_node(
            db=test_db,
            test_set_id=explorer_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            input="Both had a view",
            topic="Safety",
            label="fail",
            labeler="answer_relevancy",
        )
        update_test_node(
            db=test_db,
            test_set_id=explorer_test_set.id,
            test_id=uuid.UUID(node.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            label="pass",
        )

        cleared = update_test_node(
            db=test_db,
            test_set_id=explorer_test_set.id,
            test_id=uuid.UUID(node.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            label=CLEARED,
        )

        assert cleared.label == "fail"
        assert cleared.labeler == "answer_relevancy"
        assert cleared.annotations_count == 0
        assert cleared.last_annotation is None

    def test_updating_something_else_leaves_the_label_alone(
        self, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        """Omitting the field is how a caller says "not this"."""
        node = create_test_node(
            db=test_db,
            test_set_id=explorer_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            input="Judged, then edited",
            topic="Safety",
            label="pass",
            labeler=HUMAN_LABELER,
        )

        updated = update_test_node(
            db=test_db,
            test_set_id=explorer_test_set.id,
            test_id=uuid.UUID(node.id),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            output="A new answer",
        )

        assert updated.output == "A new answer"
        assert updated.label == "pass"
        assert updated.labeler == HUMAN_LABELER


@pytest.mark.integration
class TestEvaluationSkipsWhatIsAlreadyLabelled:
    """``overwrite=False`` means "leave the labelled ones alone", and a person's
    label counts as a label."""

    def _node(self, db, test_set, org_id, user_id, **kwargs):
        return create_test_node(
            db=db,
            test_set_id=test_set.id,
            organization_id=org_id,
            user_id=user_id,
            topic="Safety",
            output="An answer",
            **kwargs,
        )

    def _targets(self, db, test_set, org_id, user_id, *, overwrite: bool):
        _eligible, targets, skipped = _collect_evaluation_targets(
            db,
            str(test_set.id),
            org_id,
            user_id,
            None,
            None,
            True,
            overwrite,
        )
        return {target.test_id for target in targets}, skipped

    def test_a_human_labelled_test_is_skipped(
        self, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        """It lives in an annotation rather than the metadata, so leaving it out
        would re-score exactly the tests someone has already judged."""
        judged = self._node(
            test_db,
            explorer_test_set,
            test_org_id,
            authenticated_user_id,
            input="Already judged",
            label="pass",
            labeler=HUMAN_LABELER,
        )
        fresh = self._node(
            test_db,
            explorer_test_set,
            test_org_id,
            authenticated_user_id,
            input="Nobody has judged this",
        )

        target_ids, skipped = self._targets(
            test_db, explorer_test_set, test_org_id, authenticated_user_id, overwrite=False
        )

        assert fresh.id in target_ids
        assert judged.id not in target_ids
        assert skipped >= 1

    def test_a_metric_labelled_test_is_skipped_too(
        self, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        labelled = self._node(
            test_db,
            explorer_test_set,
            test_org_id,
            authenticated_user_id,
            input="A metric already scored this",
            label="fail",
            labeler="answer_relevancy",
        )

        target_ids, _skipped = self._targets(
            test_db, explorer_test_set, test_org_id, authenticated_user_id, overwrite=False
        )

        assert labelled.id not in target_ids

    def test_overwrite_takes_the_human_labelled_test_anyway(
        self, test_db: Session, explorer_test_set, test_org_id, authenticated_user_id
    ):
        """Asking to overwrite is asking for exactly that."""
        judged = self._node(
            test_db,
            explorer_test_set,
            test_org_id,
            authenticated_user_id,
            input="Judged but re-score it",
            label="pass",
            labeler=HUMAN_LABELER,
        )

        target_ids, skipped = self._targets(
            test_db, explorer_test_set, test_org_id, authenticated_user_id, overwrite=True
        )

        assert judged.id in target_ids
        assert skipped == 0
