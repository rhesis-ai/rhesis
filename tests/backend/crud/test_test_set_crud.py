"""
TestSet CRUD Operations Testing

Regression coverage for get_test_set / get_test_set_by_nano_id_or_slug's soft-delete
contract: a deleted test set must raise ItemDeletedException, like every other
entity's single-item fetch, instead of silently collapsing into "not found".

Run with: python -m pytest tests/backend/crud/test_test_set_crud.py -v
"""

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException


@pytest.mark.unit
@pytest.mark.crud
class TestTestSetSoftDeleteContract:
    """A soft-deleted test set must raise ItemDeletedException, not return None."""

    def test_get_test_set_raises_for_deleted(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        test_set = models.TestSet(
            name="Soft Delete Test Set",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(test_set)
        test_db.commit()
        test_db.refresh(test_set)
        test_set_id = test_set.id

        crud.delete_test_set(
            test_db, test_set_id, organization_id=test_org_id, user_id=authenticated_user_id
        )

        with pytest.raises(ItemDeletedException):
            crud.get_test_set(test_db, test_set_id, organization_id=test_org_id)

    def test_get_test_set_by_nano_id_or_slug_raises_for_deleted(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        test_set = models.TestSet(
            name="Soft Delete Test Set By Slug",
            slug="soft-delete-test-set-by-slug",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add(test_set)
        test_db.commit()
        test_db.refresh(test_set)
        test_set_id = test_set.id
        slug = test_set.slug

        crud.delete_test_set(
            test_db, test_set_id, organization_id=test_org_id, user_id=authenticated_user_id
        )

        with pytest.raises(ItemDeletedException):
            crud.get_test_set_by_nano_id_or_slug(test_db, slug, organization_id=test_org_id)

    def test_get_test_set_returns_none_for_nonexistent(self, test_db: Session, test_org_id: str):
        import uuid

        result = crud.get_test_set(test_db, uuid.uuid4(), organization_id=test_org_id)
        assert result is None
