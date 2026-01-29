import uuid
from typing import Iterator, List, Optional

from pydantic import BaseModel, Field, field_validator


class TestTreeNode(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    topic: str = ""
    input: str = ""
    output: str = ""
    label: str = ""
    labeler: str = ""
    to_eval: bool = True
    model_score: float = 0.0

    @field_validator("topic", mode="before")
    @classmethod
    def encode_topic_spaces(cls, v: str) -> str:
        """Replace spaces with %20 in topic paths."""
        if isinstance(v, str):
            return v.replace(" ", "%20")
        return v


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

    def __getitem__(self, key: int | str) -> TestTreeNode:
        if isinstance(key, int):
            keys = list(self._nodes.keys())
            return self._nodes[keys[key]]
        elif isinstance(key, str):
            return self._nodes[key]
        else:
            raise ValueError(f"Invalid key type: {type(key)}")

    def __setitem__(self, key: int | str, value: TestTreeNode) -> None:
        if isinstance(key, int):
            keys = list(self._nodes.keys())
            self._nodes[keys[key]] = value
        elif isinstance(key, str):
            self._nodes[key] = value
        else:
            raise ValueError(f"Invalid key type: {type(key)}")

    def get_topics(self) -> List["TestTreeNode"]:
        """Get all topic marker nodes."""
        return [node for node in self if node.label == "topic_marker"]

    def get_tests(self) -> List["TestTreeNode"]:
        """Get all actual test nodes (non-topic markers)."""
        return [node for node in self if node.label != "topic_marker"]
