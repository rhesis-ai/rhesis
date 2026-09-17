"""Tests for per-run annotation count aggregation via the annotation table."""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.crud.annotation import get_annotation_statistics_for_runs
from rhesis.backend.app.crud.test_run import get_annotation_count_for_run, get_test_runs
from rhesis.backend.jobs.execution.result_processor import (
    inject_annotation_counts_into_serialized_runs,
)


def _make_annotation(
    test_db,
    *,
    entity_type,
    entity_id,
    target_type,
    status_id,
    user_id,
    organization_id,
    project_id=None,
    target_reference=None,
):
    ann = models.Annotation(
        id=uuid.uuid4(),
        entity_type=entity_type,
        entity_id=entity_id,
        target_type=target_type,
        target_reference=target_reference,
        status_id=status_id,
        user_id=user_id,
        organization_id=organization_id,
        project_id=project_id,
    )
    test_db.add(ann)
    return ann


@pytest.fixture
def annotation_statuses(test_db: Session, test_organization, db_user, db_status):
    fail_status = models.Status(
        name="Fail",
        organization_id=test_organization.id,
        user_id=db_user.id,
    )
    test_db.add(fail_status)
    test_db.flush()
    return {"pass": db_status.id, "fail": fail_status.id}


class TestGetAnnotationStatisticsForRuns:
    def test_aggregates_annotated_and_count_per_run(
        self,
        test_db: Session,
        db_test_run,
        db_test_configuration,
        db_user,
        test_organization,
        annotation_statuses,
    ):
        run_id = db_test_run.id
        test1 = models.Test(
            organization_id=test_organization.id,
            user_id=db_user.id,
        )
        test2 = models.Test(
            organization_id=test_organization.id,
            user_id=db_user.id,
        )
        test_db.add_all([test1, test2])
        test_db.flush()

        reviewed_result = models.TestResult(
            id=uuid.uuid4(),
            test_run_id=run_id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=annotation_statuses["pass"],
            original_status_id=annotation_statuses["pass"],
            test_id=test1.id,
        )
        corrected_result = models.TestResult(
            id=uuid.uuid4(),
            test_run_id=run_id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=annotation_statuses["fail"],
            original_status_id=annotation_statuses["pass"],
            test_id=test2.id,
        )
        unannotated_result = models.TestResult(
            id=uuid.uuid4(),
            test_run_id=run_id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=annotation_statuses["pass"],
        )
        test_db.add_all([reviewed_result, corrected_result, unannotated_result])
        test_db.flush()

        _make_annotation(
            test_db,
            entity_type="TestResult",
            entity_id=reviewed_result.id,
            target_type="test_result",
            status_id=annotation_statuses["pass"],
            user_id=db_user.id,
            organization_id=test_organization.id,
        )
        _make_annotation(
            test_db,
            entity_type="TestResult",
            entity_id=corrected_result.id,
            target_type="test_result",
            status_id=annotation_statuses["fail"],
            user_id=db_user.id,
            organization_id=test_organization.id,
        )
        _make_annotation(
            test_db,
            entity_type="TestResult",
            entity_id=corrected_result.id,
            target_type="metric",
            target_reference="accuracy",
            status_id=annotation_statuses["fail"],
            user_id=db_user.id,
            organization_id=test_organization.id,
        )
        test_db.commit()

        stats = get_annotation_statistics_for_runs(test_db, [run_id])[str(run_id)]
        assert stats["annotated_tests"] == 2
        # Only the corrected result's entity-level verdict differs from its snapshot.
        assert stats["corrected_tests"] == 1

    def test_returns_zeroes_for_runs_without_annotations(
        self,
        test_db: Session,
        db_test_run,
    ):
        stats = get_annotation_statistics_for_runs(test_db, [db_test_run.id])
        assert stats[str(db_test_run.id)] == {"annotated_tests": 0, "corrected_tests": 0}


class TestGetAnnotationCountForRun:
    def test_counts_distinct_tests(
        self,
        test_db: Session,
        db_test_run,
        db_test_configuration,
        db_user,
        test_organization,
        annotation_statuses,
    ):
        test1 = models.Test(
            organization_id=test_organization.id,
            user_id=db_user.id,
        )
        test_db.add(test1)
        test_db.flush()

        result = models.TestResult(
            id=uuid.uuid4(),
            test_run_id=db_test_run.id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=annotation_statuses["pass"],
            test_id=test1.id,
        )
        test_db.add(result)
        test_db.flush()

        _make_annotation(
            test_db,
            entity_type="TestResult",
            entity_id=result.id,
            target_type="test_result",
            status_id=annotation_statuses["pass"],
            user_id=db_user.id,
            organization_id=test_organization.id,
        )
        test_db.commit()

        count = get_annotation_count_for_run(test_db, db_test_run.id)
        assert count == 1


class TestGetTestRunsHasAnnotationsFilter:
    def test_has_annotations_filter(
        self,
        test_db: Session,
        db_test_run,
        db_test_configuration,
        db_user,
        test_organization,
        annotation_statuses,
    ):
        result = models.TestResult(
            id=uuid.uuid4(),
            test_run_id=db_test_run.id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=annotation_statuses["pass"],
        )
        test_db.add(result)
        test_db.flush()

        _make_annotation(
            test_db,
            entity_type="TestResult",
            entity_id=result.id,
            target_type="test_result",
            status_id=annotation_statuses["pass"],
            user_id=db_user.id,
            organization_id=test_organization.id,
        )
        test_db.commit()

        org_id = str(test_organization.id)
        with_annotations = get_test_runs(
            test_db,
            organization_id=org_id,
            has_annotations=True,
        )
        without_annotations = get_test_runs(
            test_db,
            organization_id=org_id,
            has_annotations=False,
        )

        assert db_test_run.id in [run.id for run in with_annotations]
        assert db_test_run.id not in [run.id for run in without_annotations]


class TestInjectAnnotationCountsIntoSerializedRuns:
    def test_merges_into_existing_counts(self):
        serialized = [{"id": "run-1", "counts": {"comments": 2, "tasks": 1}}]
        annotation_stats = {
            "run-1": {"annotated_tests": 1, "corrected_tests": 1},
        }

        inject_annotation_counts_into_serialized_runs(serialized, annotation_stats)

        assert serialized[0]["counts"] == {
            "comments": 2,
            "tasks": 1,
            "annotated_tests": 1,
            "corrected_tests": 1,
        }

    def test_defaults_to_zero(self):
        serialized = [{"id": "run-1", "counts": {}}]
        inject_annotation_counts_into_serialized_runs(serialized, {})
        assert serialized[0]["counts"]["annotated_tests"] == 0
        assert serialized[0]["counts"]["corrected_tests"] == 0
