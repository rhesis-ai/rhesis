from typing import Dict, Optional

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
    id: Optional[str] = None

    def count_tokens(self, encoding_name: str = "cl100k_base") -> Dict[str, int]:
        pass


class Tests(BaseCollection):
    endpoint = ENDPOINT
