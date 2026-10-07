"""
Tests for soft-delete cascade requirement with File records.

Verifies that File records are properly cascaded when their parent
Test or TestResult entities are soft-deleted and restored.

``Test`` and ``TestResult`` each cascade to more than one child now -- files and
annotations -- so these assert that ``File`` is *among* the children reached and
derive the row count from the registry, rather than assuming it is the only one.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from rhesis.backend.app import models
from rhesis.backend.app.config.cascade_config import get_cascade_relationships
from rhesis.backend.app.crud.cascade import cascade_restore, cascade_soft_delete

# How many ids the patched ``bulk_update`` reports per child relationship.
ROWS_PER_CHILD = 2


def _children(model, *, for_restore: bool = False) -> list:
    flag = "cascade_restore" if for_restore else "cascade_delete"
    return [rel for rel in get_cascade_relationships(model) if getattr(rel, flag)]


def _patched_bulk_update(rows: int = ROWS_PER_CHILD):
    return patch(
        "rhesis.backend.app.crud.cascade.bulk_update",
        side_effect=lambda *args, **kwargs: [uuid4() for _ in range(rows)],
    )


def _updated_models(bulk_update) -> list:
    return [call.args[1] for call in bulk_update.call_args_list]


class TestFileCascade:
    """Test cascade soft-delete and restore for File records."""

    def test_soft_delete_test_cascades_to_files(self):
        """Soft-deleting a Test cascades to its File records."""
        with _patched_bulk_update() as bulk_update:
            count = cascade_soft_delete(MagicMock(), models.Test, uuid4(), str(uuid4()))

        # File is among the children reached, alongside annotations.
        assert models.File in _updated_models(bulk_update)
        # Each child is filtered by its foreign key (and entity_type where polymorphic).
        assert all(call.args[2] for call in bulk_update.call_args_list)
        assert count == ROWS_PER_CHILD * len(_children(models.Test))

    def test_restore_test_cascades_to_files(self):
        """Restoring a Test cascades to its File records."""
        with _patched_bulk_update() as bulk_update:
            count = cascade_restore(MagicMock(), models.Test, uuid4(), str(uuid4()))

        children = _children(models.Test, for_restore=True)
        assert models.File in _updated_models(bulk_update)
        # Restore sets deleted_at to None, once per child relationship.
        assert bulk_update.call_count == len(children)
        for call in bulk_update.call_args_list:
            assert call.args[3]["deleted_at"] is None
        assert count == ROWS_PER_CHILD * len(children)

    def test_soft_delete_test_result_cascades_to_files(self):
        """Soft-deleting a TestResult cascades to its File records."""
        with _patched_bulk_update() as bulk_update:
            count = cascade_soft_delete(MagicMock(), models.TestResult, uuid4(), str(uuid4()))

        assert models.File in _updated_models(bulk_update)
        assert count == ROWS_PER_CHILD * len(_children(models.TestResult))

    def test_cascade_respects_entity_type(self):
        """Cascade filters include entity_type to avoid cross-entity effects."""
        with _patched_bulk_update(rows=0) as bulk_update:
            cascade_soft_delete(MagicMock(), models.Test, uuid4())

        file_call = next(c for c in bulk_update.call_args_list if c.args[1] is models.File)
        criteria = " ".join(str(c) for c in file_call.args[2])
        assert "entity_type" in criteria

    def test_no_cascade_for_unconfigured_model(self):
        """Models without cascade config don't cascade."""
        with _patched_bulk_update() as bulk_update:
            count = cascade_soft_delete(MagicMock(), models.Organization, uuid4())
        assert count == 0
        assert not bulk_update.called
