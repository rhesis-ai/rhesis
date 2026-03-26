"""
Unit tests for ReviewsMixin in rhesis.backend.app.models.mixins

Tests the shared review mixin properties: last_review, matches_review,
review_summary. Uses a lightweight stub that inherits from ReviewsMixin.
"""

import pytest

from rhesis.backend.app.models.mixins import ReviewsMixin


class StubModel(ReviewsMixin):
    """Minimal stub inheriting ReviewsMixin for isolated testing."""

    _reviews_column_name = "test_reviews"
    _reviews_entity_type = "test_result"
    _reviews_legacy_types = ("test",)

    def __init__(self, reviews_data=None, status_id=None):
        self.test_reviews = reviews_data
        self.status_id = status_id


class TraceStubModel(ReviewsMixin):
    """Stub using trace-like configuration with overridden _get_status_id_for_match."""

    _reviews_column_name = "trace_reviews"
    _reviews_entity_type = "trace"
    _reviews_legacy_types = ()

    def __init__(self, reviews_data=None, trace_metrics_status_id=None):
        self.trace_reviews = reviews_data
        self.trace_metrics_status_id = trace_metrics_status_id

    def _get_status_id_for_match(self):
        return self.trace_metrics_status_id


class TestGetReviewsData:
    def test_none_reviews_returns_empty(self):
        model = StubModel(reviews_data=None)
        assert model._get_reviews_data() == {}

    def test_non_dict_returns_empty(self):
        model = StubModel(reviews_data="bad")
        assert model._get_reviews_data() == {}

    def test_valid_dict_returned(self):
        data = {"metadata": {}, "reviews": []}
        model = StubModel(reviews_data=data)
        assert model._get_reviews_data() == data


class TestGetAllReviews:
    def test_empty_reviews_list(self):
        model = StubModel(reviews_data={"reviews": []})
        assert model._get_all_reviews() == []

    def test_returns_reviews_list(self):
        reviews = [{"review_id": "r1"}, {"review_id": "r2"}]
        model = StubModel(reviews_data={"reviews": reviews})
        assert model._get_all_reviews() == reviews

    def test_missing_reviews_key(self):
        model = StubModel(reviews_data={"metadata": {}})
        assert model._get_all_reviews() == []

    def test_non_list_reviews(self):
        model = StubModel(reviews_data={"reviews": "not a list"})
        assert model._get_all_reviews() == []


class TestLastReview:
    def test_no_reviews_returns_none(self):
        model = StubModel(reviews_data=None)
        assert model.last_review is None

    def test_single_entity_level_review(self):
        review = {
            "review_id": "r1",
            "target": {"type": "test_result"},
            "status": {"status_id": "s1", "name": "Pass"},
            "updated_at": "2025-01-01T00:00:00",
        }
        model = StubModel(reviews_data={"reviews": [review]})
        assert model.last_review == review

    def test_legacy_type_treated_as_entity_level(self):
        review = {
            "review_id": "r1",
            "target": {"type": "test"},
            "status": {"status_id": "s1", "name": "Pass"},
            "updated_at": "2025-01-01T00:00:00",
        }
        model = StubModel(reviews_data={"reviews": [review]})
        assert model.last_review == review

    def test_metric_level_not_returned_as_last_review(self):
        review = {
            "review_id": "r1",
            "target": {"type": "metric", "reference": "accuracy"},
            "status": {"status_id": "s1", "name": "Pass"},
            "updated_at": "2025-01-01T00:00:00",
        }
        model = StubModel(reviews_data={"reviews": [review]})
        assert model.last_review is None

    def test_most_recent_entity_review_selected(self):
        old_review = {
            "review_id": "r1",
            "target": {"type": "test_result"},
            "status": {"status_id": "s1", "name": "Pass"},
            "updated_at": "2025-01-01T00:00:00",
        }
        new_review = {
            "review_id": "r2",
            "target": {"type": "test_result"},
            "status": {"status_id": "s2", "name": "Fail"},
            "updated_at": "2025-06-01T00:00:00",
        }
        model = StubModel(reviews_data={"reviews": [old_review, new_review]})
        assert model.last_review["review_id"] == "r2"


class TestMatchesReview:
    def test_no_reviews_returns_false(self):
        model = StubModel(reviews_data=None)
        assert model.matches_review is False

    def test_matching_status_id(self):
        review = {
            "review_id": "r1",
            "target": {"type": "test_result"},
            "status": {"status_id": "abc-123", "name": "Pass"},
            "updated_at": "2025-01-01T00:00:00",
        }
        model = StubModel(reviews_data={"reviews": [review]}, status_id="abc-123")
        assert model.matches_review is True

    def test_non_matching_status_id(self):
        review = {
            "review_id": "r1",
            "target": {"type": "test_result"},
            "status": {"status_id": "abc-123", "name": "Pass"},
            "updated_at": "2025-01-01T00:00:00",
        }
        model = StubModel(reviews_data={"reviews": [review]}, status_id="xyz-789")
        assert model.matches_review is False

    def test_trace_model_compares_trace_metrics_status_id(self):
        review = {
            "review_id": "r1",
            "target": {"type": "trace"},
            "status": {"status_id": "abc-123", "name": "Pass"},
            "updated_at": "2025-01-01T00:00:00",
        }
        model = TraceStubModel(
            reviews_data={"reviews": [review]},
            trace_metrics_status_id="abc-123",
        )
        assert model.matches_review is True


class TestReviewSummary:
    def test_no_reviews_returns_none(self):
        model = StubModel(reviews_data=None)
        assert model.review_summary is None

    def test_single_review_produces_summary(self):
        review = {
            "review_id": "r1",
            "target": {"type": "test_result"},
            "status": {"status_id": "s1", "name": "Pass"},
            "user": {"user_id": "u1", "name": "Alice"},
            "updated_at": "2025-01-01T00:00:00",
        }
        model = StubModel(reviews_data={"reviews": [review]})
        summary = model.review_summary
        assert summary is not None
        assert "test_result" in summary
        assert summary["test_result"]["review_id"] == "r1"

    def test_summary_keyed_by_target(self):
        reviews = [
            {
                "review_id": "r1",
                "target": {"type": "test_result"},
                "status": {"status_id": "s1", "name": "Pass"},
                "user": {"user_id": "u1", "name": "Alice"},
                "updated_at": "2025-01-01T00:00:00",
            },
            {
                "review_id": "r2",
                "target": {"type": "metric", "reference": "accuracy"},
                "status": {"status_id": "s2", "name": "Fail"},
                "user": {"user_id": "u1", "name": "Alice"},
                "updated_at": "2025-02-01T00:00:00",
            },
        ]
        model = StubModel(reviews_data={"reviews": reviews})
        summary = model.review_summary
        assert "test_result" in summary
        assert "metric:accuracy" in summary

    def test_summary_keeps_latest_per_target(self):
        reviews = [
            {
                "review_id": "r1",
                "target": {"type": "test_result"},
                "status": {"status_id": "s1", "name": "Pass"},
                "updated_at": "2025-01-01T00:00:00",
            },
            {
                "review_id": "r2",
                "target": {"type": "test_result"},
                "status": {"status_id": "s2", "name": "Fail"},
                "updated_at": "2025-06-01T00:00:00",
            },
        ]
        model = StubModel(reviews_data={"reviews": reviews})
        summary = model.review_summary
        assert summary["test_result"]["review_id"] == "r2"

    def test_legacy_type_normalized_in_summary(self):
        review = {
            "review_id": "r1",
            "target": {"type": "test"},
            "status": {"status_id": "s1", "name": "Pass"},
            "updated_at": "2025-01-01T00:00:00",
        }
        model = StubModel(reviews_data={"reviews": [review]})
        summary = model.review_summary
        assert "test_result" in summary
        assert "test" not in summary
