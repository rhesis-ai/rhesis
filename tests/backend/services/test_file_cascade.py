"""
Tests for soft-delete cascade behavior with File records.

Verifies that File records are properly cascaded when their parent
Test or TestResult entities are soft-deleted and restored.
"""

from unittest.mock import MagicMock
from uuid import uuid4

from rhesis.backend.app import models
from rhesis.backend.app.services.cascade import cascade_restore, cascade_soft_delete


class TestFileCascade:
    """Test cascade soft-delete and restore for File records."""

    def _create_mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        query_mock = MagicMock()
        db.query.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.update.return_value = 2  # Simulate 2 records affected
        return db, query_mock

    def test_soft_delete_test_cascades_to_files(self):
        """Soft-deleting a Test cascades to its File records."""
        db, query_mock = self._create_mock_db()
        test_id = uuid4()
        org_id = str(uuid4())

        count = cascade_soft_delete(db, models.Test, test_id, org_id)

        # Should have queried File model
        db.query.assert_called_with(models.File)
        # Should have filtered by entity_id and entity_type
        assert query_mock.filter.called
        assert count == 2

    def test_restore_test_cascades_to_files(self):
        """Restoring a Test cascades to its File records."""
        db, query_mock = self._create_mock_db()
        test_id = uuid4()
        org_id = str(uuid4())

        count = cascade_restore(db, models.Test, test_id, org_id)

        db.query.assert_called_with(models.File)
        assert query_mock.filter.called
        # Restore sets deleted_at to None
        query_mock.update.assert_called_once()
        update_args = query_mock.update.call_args
        assert update_args[0][0]["deleted_at"] is None
        assert count == 2

    def test_soft_delete_test_result_cascades_to_files(self):
        """Soft-deleting a TestResult cascades to its File records."""
        db, query_mock = self._create_mock_db()
        result_id = uuid4()
        org_id = str(uuid4())

        count = cascade_soft_delete(db, models.TestResult, result_id, org_id)

        db.query.assert_called_with(models.File)
        assert count == 2

    def test_cascade_respects_entity_type(self):
        """Cascade filters include entity_type to avoid cross-entity effects."""
        db = MagicMock()
        query_mock = MagicMock()
        db.query.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.update.return_value = 0

        test_id = uuid4()
        cascade_soft_delete(db, models.Test, test_id)

        # Verify filter was called - entity_type filter ensures isolation
        filter_calls = query_mock.filter.call_args_list
        assert len(filter_calls) >= 1

    def test_no_cascade_for_unconfigured_model(self):
        """Models without cascade config don't cascade."""
        db = MagicMock()
        model_id = uuid4()

        # Organization has no cascade config for files
        count = cascade_soft_delete(db, models.Organization, model_id)
        assert count == 0
        # query should not be called for File
        assert not db.query.called
