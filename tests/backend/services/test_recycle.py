"""
🧪 Recycle Service Testing

Test suite to verify cascade-aware restoration in the recycle service.

Functions tested:
- restore_item_with_cascade: Restore items with cascade logic
- bulk_restore_with_cascade: Restore multiple items with cascade

Run with: python -m pytest tests/backend/services/test_recycle.py -v
"""

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services import recycle as recycle_service
from rhesis.backend.app.database import without_soft_delete_filter


@pytest.fixture
def db_soft_deleted_test_run_with_results(
    test_db: Session, db_test_run, db_test_configuration, db_user, test_organization, db_status
):
    """
    🧪 Create a soft-deleted test run with 3 soft-deleted test results

    Returns tuple of (test_run, test_result_ids)
    """
    # Create 3 test results
    test_result_ids = []
    for i in range(3):
        test_result = models.TestResult(
            test_run_id=db_test_run.id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
            test_output={"result": f"output_{i}"},
            test_metrics={"score": i * 0.3},
        )
        test_db.add(test_result)
        test_db.flush()
        test_result_ids.append(test_result.id)

    test_db.commit()

    # Soft delete the test run and all results
    db_test_run.soft_delete()
    for test_result_id in test_result_ids:
        result = (
            test_db.query(models.TestResult).filter(models.TestResult.id == test_result_id).first()
        )
        result.soft_delete()

    test_db.commit()

    return db_test_run, test_result_ids


@pytest.mark.unit
@pytest.mark.service
class TestRecycleService:
    """🧪 Test recycle service operations"""

    def test_restore_test_run_with_cascade(
        self,
        test_db: Session,
        db_soft_deleted_test_run_with_results,
        test_org_id: str,
    ):
        """Test that restoring a test run cascades to test results"""
        test_run, test_result_ids = db_soft_deleted_test_run_with_results
        test_run_id = test_run.id

        # Verify everything is soft deleted before restoration
        with without_soft_delete_filter():
            tr = test_db.query(models.TestRun).filter(models.TestRun.id == test_run_id).first()
            assert tr.deleted_at is not None

            for test_result_id in test_result_ids:
                result = (
                    test_db.query(models.TestResult)
                    .filter(models.TestResult.id == test_result_id)
                    .first()
                )
                assert result.deleted_at is not None

        # Restore the test run (should cascade to test results)
        restored_test_run = recycle_service.restore_item_with_cascade(
            test_db, models.TestRun, test_run_id, organization_id=test_org_id
        )

        # Verify test run was restored
        assert restored_test_run is not None
        assert restored_test_run.id == test_run_id
        assert restored_test_run.deleted_at is None

        # Verify all test results were also restored
        for test_result_id in test_result_ids:
            result = (
                test_db.query(models.TestResult)
                .filter(models.TestResult.id == test_result_id)
                .first()
            )
            assert result is not None, f"Test result {test_result_id} should be restored"
            assert result.deleted_at is None, f"Test result {test_result_id} should not be deleted"

    def test_restore_non_cascade_model(
        self,
        test_db: Session,
        test_organization,
        test_org_id: str,
    ):
        """Test that restoring a non-cascade model works normally"""
        # Create and soft delete a status (no cascade needed)
        from faker import Faker

        fake = Faker()

        status = models.Status(
            name=f"Test Status {fake.uuid4()}",
            organization_id=test_organization.id,
        )
        test_db.add(status)
        test_db.flush()
        status_id = status.id
        status.soft_delete()
        test_db.commit()

        # Verify status is soft deleted
        with without_soft_delete_filter():
            s = test_db.query(models.Status).filter(models.Status.id == status_id).first()
            assert s.deleted_at is not None

        # Restore the status (no cascade)
        restored_status = recycle_service.restore_item_with_cascade(
            test_db, models.Status, status_id, organization_id=test_org_id
        )

        # Verify status was restored
        assert restored_status is not None
        assert restored_status.id == status_id
        assert restored_status.deleted_at is None

    def test_bulk_restore_with_cascade(
        self,
        test_db: Session,
        db_test_configuration,
        db_user,
        test_organization,
        db_status,
        test_org_id: str,
    ):
        """Test bulk restoration with cascade awareness"""
        # Create 2 test runs with results
        test_run_ids = []

        for i in range(2):
            test_run = models.TestRun(
                name=f"Test Run {i}",
                user_id=db_user.id,
                organization_id=test_organization.id,
                status_id=db_status.id,
                test_configuration_id=db_test_configuration.id,
                attributes={"test": "data"},
            )
            test_db.add(test_run)
            test_db.flush()

            # Add 2 test results to each run
            for j in range(2):
                test_result = models.TestResult(
                    test_run_id=test_run.id,
                    test_configuration_id=db_test_configuration.id,
                    user_id=db_user.id,
                    organization_id=test_organization.id,
                    status_id=db_status.id,
                    test_output={"result": f"output_{j}"},
                    test_metrics={"score": j * 0.5},
                )
                test_db.add(test_result)

            test_db.flush()
            test_run_ids.append(test_run.id)

        test_db.commit()

        # Soft delete everything
        for test_run_id in test_run_ids:
            tr = test_db.query(models.TestRun).filter(models.TestRun.id == test_run_id).first()
            tr.soft_delete()

            # Soft delete its results
            results = (
                test_db.query(models.TestResult)
                .filter(models.TestResult.test_run_id == test_run_id)
                .all()
            )
            for result in results:
                result.soft_delete()

        test_db.commit()

        # Bulk restore test runs (should cascade to results)
        results = recycle_service.bulk_restore_with_cascade(
            test_db, models.TestRun, test_run_ids, organization_id=test_org_id
        )

        # Verify results
        assert len(results["restored"]) == 2
        assert len(results["failed"]) == 0
        assert len(results["not_found"]) == 0

        # Expire session cache to see restored items
        test_db.expire_all()

        # Verify test runs and their results are restored
        for test_run_id in test_run_ids:
            # Check test run
            tr = test_db.query(models.TestRun).filter(models.TestRun.id == test_run_id).first()
            assert tr is not None
            assert tr.deleted_at is None

            # Check its results
            result_list = (
                test_db.query(models.TestResult)
                .filter(models.TestResult.test_run_id == test_run_id)
                .all()
            )
            assert len(result_list) == 2
            for result in result_list:
                assert result.deleted_at is None
