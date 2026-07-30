"""In-memory view over an Explorer test set's tests.

``TestTreeData`` holds the flat node collection built by :mod:`.utils`; ``TopicTree`` derives
the topic hierarchy from the ``topic_marker`` nodes inside it. Both are read-only helpers —
persistence lives in the service modules and ``crud``.
"""

from typing import Iterator, List, Optional

from rhesis.backend.app.schemas.explorer import TestTreeNode, TopicNode


class TestTreeData:
    """Collection of TestTreeNodes keyed by node id."""

    def __init__(self, nodes: Optional[List[TestTreeNode]] = None):
        self._nodes: dict[str, TestTreeNode] = {}
        if nodes:
            for node in nodes:
                self._nodes[node.id] = node

    def __iter__(self) -> Iterator[TestTreeNode]:
        return iter(self._nodes.values())

    @property
    def topics(self) -> "TopicTree":
        """Get the TopicTree view for this test tree."""
        if not hasattr(self, "_topic_tree"):
            self._topic_tree = TopicTree(self)
        return self._topic_tree

    def get_tests(self) -> List[TestTreeNode]:
        """Get all actual test nodes (non-topic markers)."""
        return [node for node in self if node.label != "topic_marker"]


class TopicTree:
    """A view over TestTreeData that provides topic-oriented operations.

    This doesn't store topics separately - it derives them from topic_marker nodes
    in the underlying TestTreeData.
    """

    def __init__(self, test_tree_data: "TestTreeData"):
        self._data = test_tree_data
        self._topic_cache: dict[str, TopicNode] = {}

    def _get_or_create_topic(self, path: str) -> TopicNode:
        """Get cached TopicNode or create new one"""
        if path not in self._topic_cache:
            self._topic_cache[path] = TopicNode(path=path)
        return self._topic_cache[path]

    def _is_real_topic(self, path: str) -> bool:
        """Filter out suggestion pseudo-topics"""
        return "__suggestions__" not in path

    # --- Query methods ---

    def get(self, path: str) -> TopicNode | None:
        """Get a topic by path, or None if no topic_marker exists for it."""
        for node in self._data:
            if node.topic == path and node.label == "topic_marker":
                return self._get_or_create_topic(path)
        return None

    def get_all(self) -> list[TopicNode]:
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

    def get_tests(
        self, topic: TopicNode | None = None, recursive: bool = False
    ) -> list[TestTreeNode]:
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

    # --- Mutation methods ---

    def rename(self, topic: TopicNode, new_name: str) -> TopicNode:
        """Rename a topic (changes the last segment of path).

        Updates all nodes under this topic.
        """
        if "/" in topic.path:
            new_path = topic.path.rsplit("/", 1)[0] + "/" + new_name
        else:
            new_path = new_name

        return self.move(topic, new_path)

    def move(self, topic: TopicNode, new_path: str) -> TopicNode:
        """Move a topic to a new path.

        Updates all nodes under this topic.
        """
        old_path = topic.path

        for node in self._data:
            if node.topic == old_path:
                node.topic = new_path
            elif node.topic.startswith(old_path + "/"):
                node.topic = new_path + node.topic[len(old_path) :]

        return self._get_or_create_topic(new_path)
