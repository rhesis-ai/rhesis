from typing import Any

from pydantic import BaseModel, Field

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity
from rhesis.sdk.utils import generate_nano_id

ENDPOINT = Endpoints.CATEGORIES


class CategoryConfig(BaseModel):
    name: str
    description: str
    nano_id: str = Field(default_factory=generate_nano_id)


class Category(BaseEntity):
    endpoint = ENDPOINT

    def __init__(self, **fields: Any) -> None:
        super().__init__(**fields)


class Categories(BaseCollection):
    endpoint = ENDPOINT
