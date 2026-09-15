"""Unit tests for AnnotationsMixin in rhesis.backend.app.models.mixins.

Covers last_annotation, matches_annotation and annotation_summary against
lightweight stubs instead of real ORM objects.
"""

import uuid
from datetime import datetime, timezone

from rhesis.backend.app.models.mixins import AnnotationsMixin

OLD = datetime(2025, 1, 1, tzinfo=timezone.utc)
NEW = datetime(2025, 6, 1, tzinfo=timezone.utc)


class _Status:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class _User:
    def __init__(self, id="u1", given_name="Alice", family_name="Smith", name=None, email="a@b.c"):
        self.id = id
        self.given_name = given_name
        self.family_name = family_name
        self.name = name
        self.email = email


class _Annotation:
    def __init__(
        self,
        *,
        id=None,
        target_type="test_result",
        target_reference=None,
        status_id="s1",
        status_name="Pass",
        user=None,
        comments=None,
        updated_at=OLD,
        created_at=OLD,
    ):
        self.id = id or uuid.uuid4()
        self.target_type = target_type
        self.target_reference = target_reference
        self.comments = comments
        self.updated_at = updated_at
        self.created_at = created_at
        self.status_id = status_id
        self.status = _Status(status_id, status_name) if status_id else None
        self.user = user or _User()


class StubModel(AnnotationsMixin):
    _annotations_entity_type = "test_result"

    def __init__(self, annotations=None, status_id=None, original_status_id=None):
        self.annotations = annotations or []
        self.status_id = status_id
        self.original_status_id = original_status_id


class TraceStubModel(AnnotationsMixin):
    _annotations_entity_type = "trace"

    def __init__(self, annotations=None, trace_metrics_status_id=None, original_status_id=None):
        self.annotations = annotations or []
        self.trace_metrics_status_id = trace_metrics_status_id
        self.original_status_id = original_status_id

    def _get_status_id_for_match(self):
        return self.trace_metrics_status_id


class TestLastAnnotation:
    def test_no_annotations_returns_none(self):
        model = StubModel()
        assert model.last_annotation is None

    def test_single_entity_level_annotation(self):
        ann = _Annotation(target_type="test_result")
        model = StubModel(annotations=[ann])
        result = model.last_annotation
        assert result is not None
        assert result["annotation_id"] == str(ann.id)

    def test_metric_level_not_returned(self):
        ann = _Annotation(target_type="metric", target_reference="accuracy")
        model = StubModel(annotations=[ann])
        assert model.last_annotation is None

    def test_most_recent_entity_level_selected(self):
        old = _Annotation(
            id=uuid.uuid4(),
            target_type="test_result",
            status_name="Pass",
            updated_at=OLD,
        )
        new = _Annotation(
            id=uuid.uuid4(),
            target_type="test_result",
            status_name="Fail",
            updated_at=NEW,
        )
        model = StubModel(annotations=[old, new])
        assert model.last_annotation["annotation_id"] == str(new.id)

    def test_trace_entity_type(self):
        ann = _Annotation(target_type="trace")
        model = TraceStubModel(annotations=[ann])
        assert model.last_annotation is not None
        assert model.last_annotation["annotation_id"] == str(ann.id)


class TestMatchesAnnotation:
    def test_no_annotations_returns_false(self):
        model = StubModel()
        assert model.matches_annotation is False

    def test_matching_status_id(self):
        ann = _Annotation(target_type="test_result", status_id="abc-123")
        model = StubModel(annotations=[ann], status_id="abc-123")
        assert model.matches_annotation is True

    def test_non_matching_status_id(self):
        ann = _Annotation(target_type="test_result", status_id="abc-123")
        model = StubModel(annotations=[ann], status_id="xyz-789")
        assert model.matches_annotation is False

    def test_uses_original_status_id_when_set(self):
        ann = _Annotation(target_type="test_result", status_id="abc-123")
        model = StubModel(
            annotations=[ann],
            status_id="xyz-789",
            original_status_id="abc-123",
        )
        assert model.matches_annotation is True

    def test_trace_model_compares_trace_metrics_status_id(self):
        ann = _Annotation(target_type="trace", status_id="abc-123")
        model = TraceStubModel(
            annotations=[ann],
            trace_metrics_status_id="abc-123",
        )
        assert model.matches_annotation is True


class TestAnnotationSummary:
    def test_no_annotations_returns_none(self):
        model = StubModel()
        assert model.annotation_summary is None

    def test_single_annotation_produces_summary(self):
        ann = _Annotation(target_type="test_result")
        model = StubModel(annotations=[ann])
        summary = model.annotation_summary
        assert summary is not None
        assert "test_result" in summary
        assert summary["test_result"]["annotation_id"] == str(ann.id)

    def test_summary_keyed_by_target(self):
        entity = _Annotation(target_type="test_result", status_name="Pass")
        metric = _Annotation(
            target_type="metric",
            target_reference="accuracy",
            status_name="Fail",
        )
        model = StubModel(annotations=[entity, metric])
        summary = model.annotation_summary
        assert "test_result" in summary
        assert "metric:accuracy" in summary

    def test_summary_keeps_latest_per_target(self):
        old_id = uuid.uuid4()
        new_id = uuid.uuid4()
        old = _Annotation(
            id=old_id,
            target_type="test_result",
            status_name="Pass",
            updated_at=OLD,
        )
        new = _Annotation(
            id=new_id,
            target_type="test_result",
            status_name="Fail",
            updated_at=NEW,
        )
        model = StubModel(annotations=[old, new])
        summary = model.annotation_summary
        assert summary["test_result"]["annotation_id"] == str(new_id)


class TestCaching:
    def test_state_is_cached_across_property_calls(self):
        ann = _Annotation(target_type="test_result")
        model = StubModel(annotations=[ann])
        first = model.last_annotation
        second = model.last_annotation
        assert first is second

    def test_cache_shared_across_properties(self):
        ann = _Annotation(target_type="test_result", status_id="s1")
        model = StubModel(annotations=[ann], status_id="s1")
        _ = model.last_annotation
        _ = model.matches_annotation
        _ = model.annotation_summary
        assert "_annotation_state_cache" in model.__dict__


class TestUserDisplayName:
    def test_name_is_carried_through(self):
        ann = _Annotation(target_type="test_result", user=_User(name="Alice Smith"))
        model = StubModel(annotations=[ann])
        assert model.last_annotation["user"]["name"] == "Alice Smith"

    def test_email_stands_in_for_a_missing_name(self):
        ann = _Annotation(target_type="test_result", user=_User(name=None, email="a@b.c"))
        model = StubModel(annotations=[ann])
        assert model.last_annotation["user"]["name"] == "a@b.c"
