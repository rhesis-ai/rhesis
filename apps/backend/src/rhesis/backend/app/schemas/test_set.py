from typing import Any, Dict, List, Optional

from pydantic import UUID4, BaseModel

from rhesis.backend.app.schemas import Base
from rhesis.backend.app.schemas.tag import Tag

# TestSet schemas
class TestSetBase(Base):
    name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    slug: Optional[str] = None
    status_id: Optional[UUID4] = None
    tags: Optional[List[Tag]] = []
    license_type_id: Optional[UUID4] = None
    attributes: Optional[dict] = None
    user_id: Optional[UUID4] = None
    owner_id: Optional[UUID4] = None
    assignee_id: Optional[UUID4] = None
    priority: Optional[int] = 0
    is_published: Optional[bool] = False
    organization_id: Optional[UUID4] = None
    visibility: Optional[str] = None
    status_id: Optional[UUID4] = None


class TestSetCreate(TestSetBase):
    pass


class TestSetUpdate(TestSetBase):
    name: str = None


class TestSet(TestSetBase):
    pass


# Bulk creation models
class TestPrompt(BaseModel):
    content: str
    language_code: str = "en"


class TestData(BaseModel):
    prompt: TestPrompt
    behavior: str
    category: str
    topic: str
    metadata: Dict[str, Any] = {}


class TestSetBulkCreate(BaseModel):
    name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    tests: List[TestData]


class TestSetBulkResponse(BaseModel):
    id: UUID4
    name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    status_id: Optional[UUID4] = None
    license_type_id: Optional[UUID4] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    visibility: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class TestSetBulkAssociateRequest(BaseModel):
    test_ids: List[UUID4]


class TestSetBulkAssociateResponse(BaseModel):
    success: bool
    total_tests: int
    message: str
    metadata: Dict[str, Any] = {
        "new_associations": None,
        "existing_associations": None,
        "invalid_associations": None,
        "existing_test_ids": None,
        "invalid_test_ids": None,
    }

    class Config:
        from_attributes = True


class TestSetBulkDisassociateRequest(BaseModel):
    test_ids: List[UUID4]


class TestSetBulkDisassociateResponse(BaseModel):
    success: bool
    total_tests: int
    removed_associations: int
    message: str
