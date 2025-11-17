from typing import Optional

from rhesis.sdk.client import Endpoints
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity
from rhesis.sdk.entities.prompt import Prompt

ENDPOINT = Endpoints.TESTS


class Test(BaseEntity):
    endpoint = ENDPOINT

    category: str
    topic: str
    behavior: str
    prompt: Prompt
    metadata: dict
    id: Optional[str] = None


class Tests(BaseCollection):
    endpoint = ENDPOINT
    entity_class = Test
