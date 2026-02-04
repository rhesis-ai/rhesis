import urllib.parse
import uuid
from functools import cached_property
from typing import Iterator, List, Literal, Optional

from pydantic import BaseModel, Field, computed_field, field_validator


class TestTreeNode(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    topic: str = ""
    input: str = ""
    output: str = ""
    label: Literal["", "topic_marker", "pass", "fail"] = ""
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

    def _ensure_topic_markers(self, topic_path: str, labeler: str = "system") -> None:
        """Ensure topic markers exist for a topic path and all its ancestors."""
        if not topic_path:
            return

        # Get all existing topic marker paths
        existing_markers = {node.topic for node in self if node.label == "topic_marker"}

        # Build list of all paths that need markers (from root to leaf)
        paths_to_create = []
        current = topic_path
        while current:
            if current not in existing_markers:
                paths_to_create.append(current)
            if "/" in current:
                current = current.rsplit("/", 1)[0]
            else:
                break

        # Create markers from root to leaf (reverse order)
        for path in reversed(paths_to_create):
            marker = TestTreeNode(
                topic=path,
                label="topic_marker",
                input="",
                output="",
                labeler=labeler,
                to_eval=False,
            )
            self._nodes[marker.id] = marker

        # Invalidate topic tree cache if it exists
        if hasattr(self, "_topic_tree"):
            self._topic_tree.invalidate_cache()

    def add_test(self, test: "TestTreeNode") -> "TestTreeNode":
        """Add a test to the collection.

        Automatically creates topic markers for the test's topic and all
        ancestor topics if they don't exist.

        Args:
            test: The test node to add (must not be a topic_marker)

        Returns:
            The added test node.

        Raises:
            ValueError: If the node is a topic_marker.
        """
        if test.label == "topic_marker":
            raise ValueError("Use topics.create() to add topic markers")

        # Ensure topic markers exist
        if test.topic:
            self._ensure_topic_markers(test.topic)

        self._nodes[test.id] = test
        return test

    def update_test(
        self,
        test_id: str,
        *,
        topic: str | None = None,
        input: str | None = None,
        output: str | None = None,
        label: Literal["", "pass", "fail"] | None = None,
        to_eval: bool | None = None,
        model_score: float | None = None,
    ) -> "TestTreeNode":
        """Update a test in the collection.

        If the topic is changed, automatically creates topic markers for the
        new topic and all ancestor topics if they don't exist.

        Args:
            test_id: The ID of the test to update.
            topic: New topic path (optional).
            input: New input value (optional).
            output: New output value (optional).
            label: New label (optional).
            to_eval: New to_eval value (optional).
            model_score: New model_score value (optional).

        Returns:
            The updated test node.

        Raises:
            KeyError: If the test_id doesn't exist.
            ValueError: If trying to update a topic_marker.
        """
        if test_id not in self._nodes:
            raise KeyError(f"Test with id '{test_id}' not found")

        test = self._nodes[test_id]
        if test.label == "topic_marker":
            raise ValueError("Cannot update topic_marker with update_test()")

        # Update fields if provided
        if topic is not None:
            test.topic = topic
            self._ensure_topic_markers(topic)
        if input is not None:
            test.input = input
        if output is not None:
            test.output = output
        if label is not None:
            test.label = label
        if to_eval is not None:
            test.to_eval = to_eval
        if model_score is not None:
            test.model_score = model_score

        return test

    def delete_test(self, test_id: str) -> bool:
        """Delete a test from the collection.

        Args:
            test_id: The ID of the test to delete.

        Returns:
            True if the test was deleted, False if it didn't exist.

        Raises:
            ValueError: If trying to delete a topic_marker.
        """
        if test_id not in self._nodes:
            return False

        test = self._nodes[test_id]
        if test.label == "topic_marker":
            raise ValueError("Use topics.delete() to remove topic markers")

        del self._nodes[test_id]
        return True

    def validate(self) -> dict:
        """Validate the test tree structure.

        This method checks that for every topic used by tests, there exists a
        corresponding topic_marker node. It also checks all parent topics in
        the hierarchy.

        Returns
        -------
        dict
            A dictionary with validation results:
            - 'valid': bool - True if all topics have markers
            - 'missing_markers': list[str] - List of topic paths missing markers
            - 'topics_with_tests': list[str] - All topics that have tests
            - 'topics_with_markers': list[str] - All topics that have markers

        Examples
        --------
        >>> data = TestTreeData(nodes)
        >>> result = data.validate()
        >>> if not result['valid']:
        ...     print(f"Missing markers for: {result['missing_markers']}")
        """
        # Collect all topics that have tests (excluding topic_marker nodes)
        topics_with_tests = set()
        for node in self:
            if node.label != "topic_marker" and node.topic:
                # Add this topic and all parent topics
                topic_path = node.topic
                while topic_path:
                    topics_with_tests.add(topic_path)
                    # Get parent topic
                    if "/" in topic_path:
                        topic_path = topic_path.rsplit("/", 1)[0]
                    else:
                        break

        # Collect all topics that have markers
        topics_with_markers = set()
        for node in self:
            if node.label == "topic_marker" and node.topic:
                topics_with_markers.add(node.topic)

        # Find topics missing markers
        missing_markers = topics_with_tests - topics_with_markers

        return {
            "valid": len(missing_markers) == 0,
            "missing_markers": sorted(list(missing_markers)),
            "topics_with_tests": sorted(list(topics_with_tests)),
            "topics_with_markers": sorted(list(topics_with_markers)),
        }


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

    def delete(self, topic: Topic, move_tests_to_parent: bool = True) -> list[str]:
        """Delete a topic.

        Args:
            topic: The topic to delete
            move_tests_to_parent: If True (default), move direct tests to parent
                topic and lift subtopics up one level. If False, delete the
                topic and all its contents.

        Returns:
            List of deleted node IDs.
        """
        deleted_ids = []
        parent_path = topic.parent_path or ""

        if move_tests_to_parent:
            # Move tests to parent and lift subtopics up one level
            for node in self._data:
                if node.topic == topic.path:
                    if node.label == "topic_marker":
                        continue  # Will delete this after the loop
                    else:
                        # Move test to parent
                        node.topic = parent_path
                elif node.topic.startswith(topic.path + "/"):
                    # Lift subtopic/test up one level
                    # e.g., Safety/Violence/Weapons -> Safety/Weapons
                    remainder = node.topic[len(topic.path) + 1 :]
                    node.topic = f"{parent_path}/{remainder}" if parent_path else remainder

            # Delete the topic_marker
            for node in list(self._data):
                if node.topic == topic.path and node.label == "topic_marker":
                    deleted_ids.append(node.id)
                    del self._data._nodes[node.id]
                    break
        else:
            # Delete everything under this topic
            for node in list(self._data):
                if node.topic == topic.path or node.topic.startswith(topic.path + "/"):
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
