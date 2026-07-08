"""Tests for per-run review count aggregation."""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services.review import classify_test_result_review_counts
from rhesis.backend.tasks.execution.result_processor import (
    get_review_statistics_for_runs,
    inject_review_counts_into_serialized_runs,
)


class TestClassifyTestResultReviewCounts:
    def test_no_reviews(self):
        assert classify_test_result_review_counts(None, "status-1") == (False, False)

    def test_metric_only_review_counts_as_reviewed_not_corrected(self):
        reviews = {
            "reviews": [
                {
                    "review_id": "r1",
                    "target": {"type": "metric", "reference": "accuracy"},
                    "status": {"status_id": "other", "name": "Fail"},
                    "updated_at": "2025-01-01T00:00:00",
                }
            ]
        }
        assert classify_test_result_review_counts(reviews, "status-1") == (True, False)

    def test_matching_entity_review_is_reviewed_not_corrected(self):
        reviews = {
            "reviews": [
                {
                    "review_id": "r1",
                    "target": {"type": "test_result"},
                    "status": {"status_id": "status-1", "name": "Pass"},
                    "updated_at": "2025-01-01T00:00:00",
                }
            ]
        }
        assert classify_test_result_review_counts(reviews, "status-1") == (True, False)

    def test_legacy_test_target_treated_as_entity_level(self):
        reviews = {
            "reviews": [
                {
                    "review_id": "r1",
                    "target": {"type": "test"},
                    "status": {"status_id": "status-2", "name": "Fail"},
                    "updated_at": "2025-01-01T00:00:00",
                }
            ]
        }
        assert classify_test_result_review_counts(reviews, "status-1") == (True, True)

    def test_entity_review_with_different_status_is_corrected(self):
        reviews = {
            "reviews": [
                {
                    "review_id": "r1",
                    "target": {"type": "test_result"},
                    "status": {"status_id": "status-2", "name": "Fail"},
                    "updated_at": "2025-01-01T00:00:00",
                }
            ]
        }
        assert classify_test_result_review_counts(reviews, "status-1") == (True, True)


class TestGetReviewStatisticsForRuns:
    @pytest.fixture
    def review_status_ids(self, test_db: Session, test_organization, db_user, db_status):
        fail_status = models.Status(
            name="Fail",
            organization_id=test_organization.id,
            user_id=db_user.id,
        )
        test_db.add(fail_status)
        test_db.flush()
        return {"pass": db_status.id, "fail": fail_status.id}

    def test_aggregates_reviewed_and_corrected_per_run(
        self,
        test_db: Session,
        db_test_run,
        db_test_configuration,
        db_user,
        test_organization,
        review_status_ids,
    ):
        run_id = db_test_run.id
        org_id = str(test_organization.id)

        reviewed_only = models.TestResult(
            id=uuid4(),
            test_run_id=run_id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=review_status_ids["pass"],
            test_reviews={
                "reviews": [
                    {
                        "review_id": "r1",
                        "target": {"type": "test_result"},
                        "status": {
                            "status_id": str(review_status_ids["pass"]),
                            "name": "Pass",
                        },
                        "updated_at": "2025-01-01T00:00:00",
                    }
                ]
            },
        )
        corrected = models.TestResult(
            id=uuid4(),
            test_run_id=run_id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=review_status_ids["pass"],
            test_reviews={
                "reviews": [
                    {
                        "review_id": "r2",
                        "target": {"type": "test_result"},
                        "status": {
                            "status_id": str(review_status_ids["fail"]),
                            "name": "Fail",
                        },
                        "updated_at": "2025-02-01T00:00:00",
                    }
                ]
            },
        )
        no_reviews = models.TestResult(
            id=uuid4(),
            test_run_id=run_id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=review_status_ids["pass"],
        )
        test_db.add_all([reviewed_only, corrected, no_reviews])
        test_db.commit()

        stats = get_review_statistics_for_runs(
            test_db,
            [run_id],
            organization_id=org_id,
        )

        assert stats[str(run_id)] == {"reviewed_tests": 2, "corrected_tests": 1}

    def test_returns_zero_buckets_for_runs_without_results(
        self,
        test_db: Session,
        db_test_run,
        test_organization,
    ):
        stats = get_review_statistics_for_runs(
            test_db,
            [db_test_run.id],
            organization_id=str(test_organization.id),
        )
        assert stats[str(db_test_run.id)] == {
            "reviewed_tests": 0,
            "corrected_tests": 0,
        }


class TestInjectReviewCountsIntoSerializedRuns:
    def test_merges_into_existing_counts(self):
        serialized = [{"id": "run-1", "counts": {"comments": 2, "tasks": 1}}]
        review_stats = {"run-1": {"reviewed_tests": 3, "corrected_tests": 1}}

        inject_review_counts_into_serialized_runs(serialized, review_stats)

        assert serialized[0]["counts"] == {
            "comments": 2,
            "tasks": 1,
            "reviewed_tests": 3,
            "corrected_tests": 1,
        }
