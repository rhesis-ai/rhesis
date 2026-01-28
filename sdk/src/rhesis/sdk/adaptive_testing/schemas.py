import uuid
from typing import Iterator, List, Optional

from pydantic import BaseModel, Field


class TestTreeNode(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    topic: str = ""
    input: str
    output: str = ""
    label: str = ""
    labeler: str = ""
    to_eval: bool = True
    model_score: float = 0.0


class TestTreeData:
    """Collection of TestTreeNodes with pandas-like interface."""

    def __init__(self, nodes: Optional[List[TestTreeNode]] = None):
        self._nodes: dict[str, TestTreeNode] = {}
        if nodes:
            for node in nodes:
                self._nodes[node.id] = node

    def __len__(self) -> int:
        return len(self._nodes)

    def __iter__(self) -> Iterator[TestTreeNode]:
        return iter(self._nodes.values())

    @property
    def index(self):
        return list(self._nodes.keys())

    @property
    def shape(self) -> tuple[int, int]:
        return (len(self._nodes), 5)  # 5

    def __getitem__(self, key: int) -> TestTreeNode:
        keys = list(self._nodes.keys())
        return self._nodes[keys[key]]
