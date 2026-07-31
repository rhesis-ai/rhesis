from typing import Optional

from pydantic import UUID4

from rhesis.backend.app.schemas import Base


# Category schemas
class CategoryBase(Base):
    name: str


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(CategoryBase):
    name: Optional[str] = None


class Category(CategoryBase):
    pass


class CategoryDetail(Category):
    id: UUID4
    name: Optional[str] = None
