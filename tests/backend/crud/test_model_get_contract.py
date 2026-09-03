"""
get_model's soft-delete contract is deliberately different from this repo's other
single-item getters: it's used across services/tasks as an internal "resolve the
configured model, fall back if unavailable" helper, so it must keep collapsing
"missing" and "deleted" into a plain None instead of raising ItemDeletedException
-- see the module docstring on rhesis.backend.app.crud.model for why.
"""

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.crud import model as model_crud
from rhesis.backend.app.schemas.model import ModelCreate


@pytest.mark.unit
class TestGetModelSoftDeleteContract:
    def test_get_model_returns_none_for_deleted(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        model = model_crud.create_model(
            db=test_db,
            model=ModelCreate(
                name="Soft Delete Model",
                model_name="test-model",
                endpoint="https://test.example.com",
                key="test-key",
            ),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        model_id = model.id

        model_crud.delete_model(
            test_db, model_id, organization_id=test_org_id, user_id=authenticated_user_id
        )

        result = model_crud.get_model(test_db, model_id, organization_id=test_org_id)
        assert result is None

    def test_get_model_requires_organization_id(
        self, test_db: Session, test_org_id: str, authenticated_user_id: str
    ):
        model = model_crud.create_model(
            db=test_db,
            model=ModelCreate(
                name="Org Filter Model",
                model_name="test-model",
                endpoint="https://test.example.com",
                key="test-key",
            ),
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )

        with pytest.raises(ValueError, match="organization_id is required"):
            model_crud.get_model(test_db, model.id)
