"""
🧪 Test Run Cascade Deletion Testing

Test suite to verify that soft deleting a test run cascades to all associated test results.

Functions tested:
- delete_test_run: Soft delete test run with cascading to test results

Run with: python -m pytest tests/backend/crud/test_test_run_cascade_delete.py -v
"""

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.database import without_soft_delete_filter


@pytest.fixture
def db_test_run_with_results(
    test_db: Session, db_test_run, db_test_configuration, db_user, test_organization, db_status
):
    """
    🧪 Create a test run with 5 test results

    Returns tuple of (test_run, test_result_ids)
    """
    test_result_ids = []
    for i in range(5):
        test_result = models.TestResult(
            test_run_id=db_test_run.id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
            test_output={"result": f"output_{i}"},
            test_metrics={"score": i * 0.2},
        )
        test_db.add(test_result)
        test_db.flush()
        test_result_ids.append(test_result.id)

    test_db.commit()
    return db_test_run, test_result_ids


@pytest.fixture
def db_test_run_large_batch(
    test_db: Session, db_test_run, db_test_configuration, db_user, test_organization, db_status
):
    """
    🧪 Create a test run with 150 test results (exceeds batch size of 100)
    """
    for i in range(150):
        test_result = models.TestResult(
            test_run_id=db_test_run.id,
            test_configuration_id=db_test_configuration.id,
            user_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
            test_output={"result": f"output_{i}"},
            test_metrics={"score": i * 0.01},
        )
        test_db.add(test_result)

    test_db.commit()
    return db_test_run


@pytest.mark.unit
@pytest.mark.crud
class TestTestRunCascadeDelete:
    """🧪 Test test run cascade deletion operations"""

    def test_delete_test_run_cascades_to_test_results(
        self,
        test_db: Session,
        db_test_run_with_results,
        test_org_id: str,
        authenticated_user_id: str,
    ):
        """Test that soft deleting a test run cascades to all associated test results"""
        test_run, test_result_ids = db_test_run_with_results
        test_run_id = test_run.id

        # Verify test results exist before deletion
        results_before = (
            test_db.query(models.TestResult)
            .filter(models.TestResult.test_run_id == test_run_id)
            .count()
        )
        assert results_before == 5

        # Soft delete the test run (should cascade to test results)
        deleted_test_run = crud.delete_test_run(
            db=test_db,
            test_run_id=test_run_id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        # Verify test run was soft deleted
        assert deleted_test_run is not None
        assert deleted_test_run.id == test_run_id
        assert deleted_test_run.deleted_at is not None

        # Verify all test results were also soft deleted
        with without_soft_delete_filter():
            for test_result_id in test_result_ids:
                result = (
                    test_db.query(models.TestResult)
                    .filter(models.TestResult.id == test_result_id)
                    .first()
                )
                assert result is not None, f"Test result {test_result_id} should still exist in DB"
                assert result.deleted_at is not None, (
                    f"Test result {test_result_id} should be soft deleted"
                )

    def test_delete_test_run_with_no_test_results(
        self, test_db: Session, db_test_run, test_org_id: str, authenticated_user_id: str
    ):
        """Test that soft deleting a test run works even if it has no test results"""
        test_run_id = db_test_run.id

        # Soft delete the test run
        deleted_test_run = crud.delete_test_run(
            db=test_db,
            test_run_id=test_run_id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        # Verify test run was soft deleted
        assert deleted_test_run is not None
        assert deleted_test_run.deleted_at is not None

    def test_delete_test_run_large_batch(
        self,
        test_db: Session,
        db_test_run_large_batch,
        test_org_id: str,
        authenticated_user_id: str,
    ):
        """Test that soft deleting a test run handles large batches of test results (> 100)"""
        test_run = db_test_run_large_batch
        test_run_id = test_run.id

        # Verify 150 test results exist before deletion
        results_before = (
            test_db.query(models.TestResult)
            .filter(models.TestResult.test_run_id == test_run_id)
            .count()
        )
        assert results_before == 150

        # Soft delete the test run
        deleted_test_run = crud.delete_test_run(
            db=test_db,
            test_run_id=test_run_id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        # Verify test run was soft deleted
        assert deleted_test_run is not None
        assert deleted_test_run.deleted_at is not None

        # Verify all 150 test results were soft deleted
        with without_soft_delete_filter():
            deleted_results_count = (
                test_db.query(models.TestResult)
                .filter(
                    models.TestResult.test_run_id == test_run_id,
                    models.TestResult.deleted_at.isnot(None),
                )
                .count()
            )
            assert deleted_results_count == 150
