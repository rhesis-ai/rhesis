import urllib.parse
import uuid
from functools import cached_property
from typing import Iterator, List, Optional

from pydantic import BaseModel, Field, computed_field, field_validator


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
    def topics(self) -> "TopicTree":
        """Get the TopicTree view for this test tree."""
        if not hasattr(self, "_topic_tree"):
            self._topic_tree = TopicTree(self)
        return self._topic_tree

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

    def topic_has_direct_tests(self, target_topic: str) -> bool:
        """Check if a topic has direct tests (non-topic-marker nodes)."""
        return any(node.topic == target_topic and node.label != "topic_marker" for node in self)

    def topic_has_subtopics(self, target_topic: str) -> bool:
        """Check if a topic has subtopics."""
        prefix = target_topic + "/" if target_topic else ""
        return any(
            node.topic != target_topic
            and node.topic.startswith(prefix)
            and node.label == "topic_marker"
            for node in self
        )

    def append(self, nodes: List["TestTreeNode"]) -> None:
        """Add nodes to the collection."""
        for node in nodes:
            self._nodes[node.id] = node

    def remove(self, node_id: str) -> None:
        """Remove a node by ID."""
        if node_id in self._nodes:
            del self._nodes[node_id]


class Topic(BaseModel):
    """Represents a hierarchical topic in the test tree."""

    path: str  # Full path like "Safety/Violence" (URL-encoded)

    model_config = {"frozen": True}  # Make it hashable

    @computed_field
    @cached_property
    def name(self) -> str:
        """The leaf name, e.g., 'Violence' (still URL-encoded)"""
        if not self.path:
            return ""
        return self.path.rsplit("/", 1)[-1]

    @computed_field
    @cached_property
    def parent_path(self) -> Optional[str]:
        """Parent path or None for root-level topics"""
        if "/" in self.path:
            return self.path.rsplit("/", 1)[0]
        return None

    @computed_field
    @cached_property
    def depth(self) -> int:
        """How deep in the hierarchy (0 = root level)"""
        if not self.path:
            return -1  # Root itself
        return self.path.count("/")

    @property
    def display_name(self) -> str:
        """Human-readable name with URL encoding decoded"""
        return urllib.parse.unquote(self.name)

    @property
    def display_path(self) -> str:
        """Human-readable full path with URL encoding decoded"""
        return urllib.parse.unquote(self.path)

    def is_ancestor_of(self, other: "Topic") -> bool:
        """Returns True if self is an ancestor of other"""
        if not self.path:
            return bool(other.path)  # Empty path is ancestor of everything
        return other.path.startswith(self.path + "/")

    def is_descendant_of(self, other: "Topic") -> bool:
        """Returns True if self is a descendant of other"""
        return other.is_ancestor_of(self)

    def is_direct_child_of(self, other: Optional["Topic"]) -> bool:
        """Returns True if self is a direct child of other"""
        if other is None:
            # Direct child of root = no "/" in path
            return "/" not in self.path
        return self.parent_path == other.path

    def child_path(self, child_name: str) -> str:
        """Get the path for a child topic"""
        if self.path:
            return f"{self.path}/{child_name}"
        return child_name

    @classmethod
    def from_display_name(cls, display_path: str) -> "Topic":
        """Create a Topic from a human-readable path (encodes spaces etc.)"""
        encoded = urllib.parse.quote(display_path, safe="/")
        return cls(path=encoded)

    @classmethod
    def root(cls) -> "Topic":
        """Get the root topic (empty path)"""
        return cls(path="")

    def __str__(self) -> str:
        return self.path

    def __repr__(self) -> str:
        return f"Topic(path={self.path!r})"


class TopicTree:
    """A view over TestTreeData that provides topic-oriented operations.

    This doesn't store topics separately - it derives them from topic_marker nodes
    in the underlying TestTreeData.
    """

    def __init__(self, test_tree_data: "TestTreeData"):
        self._data = test_tree_data
        self._topic_cache: dict[str, Topic] = {}

    def invalidate_cache(self):
        """Call when TestTreeData changes (add/remove/move nodes)"""
        self._topic_cache.clear()

    def _get_or_create_topic(self, path: str) -> Topic:
        """Get cached Topic or create new one"""
        if path not in self._topic_cache:
            self._topic_cache[path] = Topic(path=path)
        return self._topic_cache[path]

    def _is_real_topic(self, path: str) -> bool:
        """Filter out suggestion pseudo-topics"""
        return "__suggestions__" not in path

    # --- Query methods ---

    def get(self, path: str) -> Topic | None:
        """Get a topic by path, or None if no topic_marker exists for it."""
        for node in self._data:
            if node.topic == path and node.label == "topic_marker":
                return self._get_or_create_topic(path)
        return None

    def get_all(self) -> list[Topic]:
        """Get all topics (excludes __suggestions__ pseudo-topics)."""
        topics = []
        seen = set()
        for node in self._data:
            if (
                node.label == "topic_marker"
                and self._is_real_topic(node.topic)
                and node.topic not in seen
            ):
                seen.add(node.topic)
                topics.append(self._get_or_create_topic(node.topic))
        return topics

    def get_children(self, parent: Topic | None = None) -> list[Topic]:
        """Get direct child topics of the given topic (or root-level if None)."""
        parent_path = parent.path if parent else ""
        children = []
        seen = set()

        for node in self._data:
            if node.label != "topic_marker":
                continue
            if not self._is_real_topic(node.topic):
                continue

            # Check if it's a child of parent
            if parent_path:
                if not node.topic.startswith(parent_path + "/"):
                    continue
                remainder = node.topic[len(parent_path) + 1 :]
            else:
                remainder = node.topic

            # Direct child = no "/" in remainder
            if "/" not in remainder and node.topic not in seen:
                seen.add(node.topic)
                children.append(self._get_or_create_topic(node.topic))

        return children

    def get_ancestors(self, topic: Topic) -> list[Topic]:
        """Get all ancestors from root to parent (not including topic itself)."""
        ancestors = []
        current_path = topic.parent_path
        while current_path:
            ancestor = self.get(current_path)
            if ancestor:
                ancestors.insert(0, ancestor)  # Insert at front to maintain order
            # Move up even if no topic_marker (implicit topics)
            if "/" in current_path:
                current_path = current_path.rsplit("/", 1)[0]
            else:
                break
        return ancestors

    def get_tests(
        self, topic: Topic | None = None, recursive: bool = False
    ) -> list["TestTreeNode"]:
        """Get test nodes (non-topic-markers) under a topic."""
        tests = []
        topic_path = topic.path if topic else ""

        for node in self._data:
            if node.label == "topic_marker":
                continue
            if "__suggestions__" in node.topic:
                continue

            if not topic_path:
                # No topic filter - get all
                tests.append(node)
            elif recursive:
                # Include topic and all descendants
                if node.topic == topic_path or node.topic.startswith(topic_path + "/"):
                    tests.append(node)
            else:
                # Direct children only
                if node.topic == topic_path:
                    tests.append(node)

        return tests

    def has_direct_tests(self, topic: Topic) -> bool:
        """Check if topic has direct tests (not in subtopics)."""
        for node in self._data:
            if (
                node.topic == topic.path
                and node.label != "topic_marker"
                and "__suggestions__" not in node.topic
            ):
                return True
        return False

    def has_subtopics(self, topic: Topic) -> bool:
        """Check if topic has any child topics."""
        return len(self.get_children(topic)) > 0

    # --- Mutation methods ---

    def create(self, path: str, labeler: str = "user") -> Topic:
        """Create a new topic by adding a topic_marker node.

        Returns the Topic (creates topic_marker node in TestTreeData).
        """
        # Check if already exists
        existing = self.get(path)
        if existing:
            return existing

        # Create the topic_marker node
        node = TestTreeNode(
            topic=path,
            label="topic_marker",
            input="",
            output="",
            labeler=labeler,
            to_eval=False,
        )
        self._data[node.id] = node
        self.invalidate_cache()

        return self._get_or_create_topic(path)

    def delete(self, topic: Topic, recursive: bool = False) -> list[str]:
        """Delete a topic and optionally its contents.

        Returns list of deleted node IDs.
        """
        deleted_ids = []

        for node in list(self._data):  # list() to allow mutation during iteration
            should_delete = False

            if node.topic == topic.path:
                # Direct match - always delete
                should_delete = True
            elif recursive and node.topic.startswith(topic.path + "/"):
                # Descendant - delete if recursive
                should_delete = True

            if should_delete:
                deleted_ids.append(node.id)
                del self._data._nodes[node.id]

        self.invalidate_cache()
        return deleted_ids

    def rename(self, topic: Topic, new_name: str) -> Topic:
        """Rename a topic (changes the last segment of path).

        Updates all nodes under this topic.
        """
        if "/" in topic.path:
            new_path = topic.path.rsplit("/", 1)[0] + "/" + new_name
        else:
            new_path = new_name

        return self.move(topic, new_path)

    def move(self, topic: Topic, new_path: str) -> Topic:
        """Move a topic to a new path.

        Updates all nodes under this topic.
        """
        old_path = topic.path

        for node in self._data:
            if node.topic == old_path:
                node.topic = new_path
            elif node.topic.startswith(old_path + "/"):
                node.topic = new_path + node.topic[len(old_path) :]

        self.invalidate_cache()
        return self._get_or_create_topic(new_path)

    def get_topic_marker_id(self, topic: Topic) -> str | None:
        """Get the node ID of the topic_marker for this topic."""
        for node in self._data:
            if node.topic == topic.path and node.label == "topic_marker":
                return node.id
        return None
