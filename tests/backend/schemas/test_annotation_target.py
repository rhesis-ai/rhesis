"""A sub-target has to name what it judges.

`metric` and `turn` targets are looked up by name downstream, and a null
reference reaches `_normalize_metric_name` as `None.lower()` -- an
AttributeError, so a 500 rather than a bad request. The UI cannot produce one
(a target only exists there once a mention names it), but the SDK and the MCP
tools take the target as an argument, so the schema is the place to stop it.
"""

import pytest
from pydantic import ValidationError

from rhesis.backend.app.constants import AnnotationTarget
from rhesis.backend.app.schemas.annotation import AnnotationCreate, AnnotationTargetSchema

ENTITY_ID = "11111111-1111-1111-1111-111111111111"
STATUS_ID = "22222222-2222-2222-2222-222222222222"


@pytest.mark.unit
class TestSubTargetsNeedAReference:
    @pytest.mark.parametrize("target_type", [AnnotationTarget.METRIC, AnnotationTarget.TURN])
    def test_a_missing_reference_is_rejected(self, target_type):
        with pytest.raises(ValidationError, match="target.reference is required"):
            AnnotationTargetSchema(type=target_type)

    @pytest.mark.parametrize("target_type", [AnnotationTarget.METRIC, AnnotationTarget.TURN])
    def test_a_blank_reference_is_rejected(self, target_type):
        """Whitespace would pass a truthiness check but name nothing."""
        with pytest.raises(ValidationError, match="target.reference is required"):
            AnnotationTargetSchema(type=target_type, reference="   ")

    def test_a_named_metric_is_accepted(self):
        target = AnnotationTargetSchema(type=AnnotationTarget.METRIC, reference="Answer Fluency")
        assert target.reference == "Answer Fluency"

    def test_a_named_turn_is_accepted(self):
        assert AnnotationTargetSchema(type=AnnotationTarget.TURN, reference="Turn 2").reference

    @pytest.mark.parametrize(
        "target_type",
        [AnnotationTarget.TEST_RESULT, AnnotationTarget.TRACE, AnnotationTarget.TEST],
    )
    def test_entity_level_targets_need_no_reference(self, target_type):
        """The entity is the subject, so there is nothing to name."""
        assert AnnotationTargetSchema(type=target_type).reference is None


@pytest.mark.unit
class TestThroughTheCreateSchema:
    def test_the_rejection_reaches_a_create_body(self):
        """Nested validation has to fire, or the route still accepts it."""
        with pytest.raises(ValidationError, match="target.reference is required"):
            AnnotationCreate(
                entity_type="TestResult",
                entity_id=ENTITY_ID,
                status_id=STATUS_ID,
                target={"type": "metric"},
            )

    def test_a_create_with_no_target_at_all_is_fine(self):
        """Omitting the target is how a caller asks for the entity-level one."""
        created = AnnotationCreate(
            entity_type="TestResult", entity_id=ENTITY_ID, status_id=STATUS_ID
        )
        assert created.target is None
