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


@pytest.mark.unit
@pytest.mark.crud
class TestUpdateTestSetAttributesSoftDeleteHandling:
    """update_test_set_attributes must still no-op when a linked test set is deleted.

    Regression test: crud.get_test_set now raises ItemDeletedException instead of
    returning None, so update_test_set_attributes (called by crud.update_test for
    every test set a test belongs to) must catch that itself -- otherwise updating
    a test would fail with a 410 just because an unrelated linked test set was
    soft-deleted.
    """

    def test_update_test_succeeds_when_linked_test_set_is_deleted(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        from rhesis.backend.app.models.test import test_test_set_association

        compliance = models.Requirement(
            name="Compliance",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        robustness = models.Requirement(
            name="Robustness",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add_all([compliance, robustness])
        test_db.flush()

        db_test = models.Test(
            requirement_id=compliance.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_set = models.TestSet(
            name="Deleted Linked Test Set",
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        test_db.add_all([db_test, test_set])
        test_db.flush()

        test_db.execute(
            test_test_set_association.insert().values(
                test_id=db_test.id,
                test_set_id=test_set.id,
                organization_id=test_org_id,
                user_id=authenticated_user_id,
            )
        )
        test_db.commit()

        crud.delete_test_set(
            test_db, test_set.id, organization_id=test_org_id, user_id=authenticated_user_id
        )

        result = crud.update_test(
            db=test_db,
            test_id=db_test.id,
            test={"requirement_id": robustness.id},
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        assert result is not None
        assert result.requirement_id == robustness.id
