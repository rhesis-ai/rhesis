"""Unit tests for the Explorer in-memory tree.

Ported from the SDK's ``tests/sdk/adaptive_testing/test_schemas.py`` when
``TestTreeNode``/``TopicNode`` moved into ``app.schemas.explorer`` and
``TestTreeData``/``TopicTree`` into ``app.services.explorer.tree``. Only the surface the
backend actually calls is covered — the unused SDK methods were dropped in the same move.
"""

import pytest

from rhesis.backend.app.schemas.explorer import TestTreeNode, TopicNode
from rhesis.backend.app.services.explorer.tree import TestTreeData, TopicTree


class TestTestTreeNode:
    """Tests for the TestTreeNode model."""

    def test_default_values(self):
        """Should have correct default values."""
        node = TestTreeNode(input="test")
        assert node.topic == ""
        assert node.output == ""
        assert node.label == ""
        assert node.labeler == ""
        assert node.to_eval is True
        assert node.model_score == 0.0
        assert node.metrics is None

    def test_auto_generates_unique_id(self):
        """Should auto-generate unique IDs."""
        node1 = TestTreeNode(input="test1")
        node2 = TestTreeNode(input="test2")
        assert node1.id != node2.id
        assert len(node1.id) == 32  # UUID hex length

    def test_create_with_all_fields(self):
        """Should create node with all fields specified."""
        node = TestTreeNode(
            id="custom-id",
            topic="Safety",
            input="Is this safe?",
            output="Yes",
            label="pass",
            labeler="user",
            to_eval=False,
            model_score=0.95,
            metrics={"answer_relevancy": {"score": 0.95, "is_successful": True}},
        )
        assert node.id == "custom-id"
        assert node.topic == "Safety"
        assert node.input == "Is this safe?"
        assert node.output == "Yes"
        assert node.label == "pass"
        assert node.labeler == "user"
        assert node.to_eval is False
        assert node.model_score == 0.95
        assert node.metrics == {"answer_relevancy": {"score": 0.95, "is_successful": True}}

    def test_missing_input_uses_default(self):
        """Should use empty string as default for input."""
        node = TestTreeNode()
        assert node.input == ""

    def test_topic_preserved_as_given(self):
        """Topic is stored exactly as provided, spaces and all."""
        node = TestTreeNode(input="test", topic="Safety Topic/Sub Topic")
        assert node.topic == "Safety Topic/Sub Topic"

    @pytest.mark.parametrize("label", ["", "topic_marker", "pass", "fail", "error"])
    def test_accepts_every_persisted_label(self, label):
        """All labels the services write must be constructible.

        ``error`` is written by ``evaluation.py`` when a metric raises; before it was added
        to the Literal, any tree read after a failed evaluation raised ValidationError.
        """
        assert TestTreeNode(input="test", label=label).label == label

    def test_rejects_unknown_label(self):
        """Labels outside the Literal are still rejected."""
        with pytest.raises(ValueError):
            TestTreeNode(input="test", label="banana")


class TestTestTreeData:
    """Tests for the TestTreeData collection."""

    @pytest.fixture
    def sample_nodes(self):
        return [
            TestTreeNode(id="node1", input="input1"),
            TestTreeNode(id="node2", input="input2"),
            TestTreeNode(id="node3", input="input3"),
        ]

    def test_init_empty(self):
        """Should initialize with no nodes."""
        assert list(TestTreeData()) == []

    def test_iter_returns_same_nodes_in_order(self, sample_nodes):
        """Should iterate over the same node objects in insertion order."""
        data = TestTreeData(sample_nodes)
        nodes = list(data)
        assert len(nodes) == len(sample_nodes)
        for iterated, original in zip(nodes, sample_nodes):
            assert iterated is original

    def test_init_deduplicates_by_id(self):
        """Nodes are keyed by id, so a repeated id keeps only the last one."""
        data = TestTreeData(
            [
                TestTreeNode(id="dup", input="first"),
                TestTreeNode(id="dup", input="second"),
            ]
        )
        nodes = list(data)
        assert len(nodes) == 1
        assert nodes[0].input == "second"

    def test_topics_property_returns_topic_tree(self):
        """Should expose a TopicTree view."""
        data = TestTreeData()
        assert isinstance(data.topics, TopicTree)

    def test_topics_property_cached(self):
        """Should return the same TopicTree instance on repeated access."""
        data = TestTreeData()
        assert data.topics is data.topics

    def test_get_tests_excludes_topic_markers(self):
        """Should return only non-marker nodes."""
        data = TestTreeData(
            [
                TestTreeNode(id="m1", topic="Safety", label="topic_marker"),
                TestTreeNode(id="t1", topic="Safety", input="test1", label="pass"),
                TestTreeNode(id="t2", topic="Safety", input="test2", label="fail"),
            ]
        )
        tests = data.get_tests()
        assert {t.id for t in tests} == {"t1", "t2"}


class TestTopicTree:
    """Tests for the TopicTree view."""

    @pytest.fixture
    def data_with_topics(self):
        nodes = [
            TestTreeNode(id="m1", topic="Safety", label="topic_marker"),
            TestTreeNode(id="m2", topic="Safety/Violence", label="topic_marker"),
            TestTreeNode(id="m3", topic="Safety/Privacy", label="topic_marker"),
            TestTreeNode(id="m4", topic="Performance", label="topic_marker"),
            TestTreeNode(id="t1", topic="Safety", input="test1", label="pass"),
            TestTreeNode(id="t2", topic="Safety/Violence", input="test2", label="fail"),
            TestTreeNode(id="t3", topic="Safety/Violence", input="test3", label="pass"),
        ]
        return TestTreeData(nodes)

    def test_get_existing_topic(self, data_with_topics):
        """Should return a TopicNode for an existing path."""
        topic = data_with_topics.topics.get("Safety")
        assert topic is not None
        assert topic.path == "Safety"

    def test_get_nonexistent_topic(self, data_with_topics):
        """Should return None when no topic_marker exists for the path."""
        assert data_with_topics.topics.get("NonExistent") is None

    def test_get_ignores_paths_that_only_have_tests(self, data_with_topics):
        """A path with tests but no marker is not a topic."""
        data = TestTreeData([TestTreeNode(id="t1", topic="Orphan", input="x", label="pass")])
        assert data.topics.get("Orphan") is None

    def test_get_all_topics(self, data_with_topics):
        """Should return every marker path once."""
        paths = {t.path for t in data_with_topics.topics.get_all()}
        assert paths == {"Safety", "Safety/Violence", "Safety/Privacy", "Performance"}

    def test_get_all_excludes_suggestions(self):
        """Should exclude __suggestions__ pseudo-topics."""
        data = TestTreeData(
            [
                TestTreeNode(id="m1", topic="Safety", label="topic_marker"),
                TestTreeNode(id="m2", topic="Safety/__suggestions__", label="topic_marker"),
            ]
        )
        paths = {t.path for t in data.topics.get_all()}
        assert paths == {"Safety"}

    def test_get_tests_direct(self, data_with_topics):
        """Should return direct tests only when recursive=False."""
        tree = data_with_topics.topics
        tests = tree.get_tests(tree.get("Safety"), recursive=False)
        assert [t.id for t in tests] == ["t1"]

    def test_get_tests_recursive(self, data_with_topics):
        """Should include subtopic tests when recursive=True."""
        tree = data_with_topics.topics
        tests = tree.get_tests(tree.get("Safety"), recursive=True)
        assert {t.id for t in tests} == {"t1", "t2", "t3"}

    def test_get_tests_all(self, data_with_topics):
        """Should return all tests when topic is None."""
        assert len(data_with_topics.topics.get_tests(None)) == 3

    def test_get_tests_excludes_suggestions(self):
        """Should exclude tests in __suggestions__ topics."""
        data = TestTreeData(
            [
                TestTreeNode(id="m1", topic="Safety", label="topic_marker"),
                TestTreeNode(id="t1", topic="Safety", input="test1", label="pass"),
                TestTreeNode(id="t2", topic="Safety/__suggestions__", input="s", label=""),
            ]
        )
        tests = data.topics.get_tests(None)
        assert [t.id for t in tests] == ["t1"]

    def test_rename_nested_topic(self, data_with_topics):
        """Should replace the last path segment and move its tests."""
        tree = data_with_topics.topics
        new_topic = tree.rename(tree.get("Safety/Violence"), "Aggression")

        assert new_topic.path == "Safety/Aggression"
        assert tree.get("Safety/Violence") is None
        assert tree.get("Safety/Aggression") is not None
        assert len(tree.get_tests(new_topic)) == 2

    def test_rename_root_level_topic(self):
        """Should rename a root-level topic."""
        data = TestTreeData(
            [
                TestTreeNode(id="m1", topic="Safety", label="topic_marker"),
                TestTreeNode(id="t1", topic="Safety", input="test", label="pass"),
            ]
        )
        tree = data.topics
        new_topic = tree.rename(tree.get("Safety"), "Security")

        assert new_topic.path == "Security"
        assert tree.get("Safety") is None
        assert tree.get("Security") is not None

    def test_move_topic(self, data_with_topics):
        """Should move a topic to an unrelated path."""
        tree = data_with_topics.topics
        new_topic = tree.move(tree.get("Safety/Violence"), "Performance/Violence")

        assert new_topic.path == "Performance/Violence"
        assert tree.get("Safety/Violence") is None
        assert tree.get("Performance/Violence") is not None

    def test_move_topic_updates_descendants(self):
        """Should re-path child topics and their tests."""
        data = TestTreeData(
            [
                TestTreeNode(id="m1", topic="A", label="topic_marker"),
                TestTreeNode(id="m2", topic="A/B", label="topic_marker"),
                TestTreeNode(id="m3", topic="A/B/C", label="topic_marker"),
                TestTreeNode(id="m4", topic="X", label="topic_marker"),
                TestTreeNode(id="t1", topic="A/B/C", input="test", label="pass"),
            ]
        )
        tree = data.topics
        tree.move(tree.get("A/B"), "X/B")

        assert tree.get("A/B") is None
        assert tree.get("A/B/C") is None
        assert tree.get("X/B") is not None
        assert tree.get("X/B/C") is not None
        assert len(tree.get_tests(tree.get("X/B/C"))) == 1


class TestTopicNode:
    """Tests for the TopicNode model."""

    def test_name_is_leaf_segment(self):
        assert TopicNode(path="Safety/Violence").name == "Violence"

    def test_name_root_level(self):
        assert TopicNode(path="Safety").name == "Safety"

    def test_name_empty_path(self):
        assert TopicNode(path="").name == ""

    def test_parent_path(self):
        assert TopicNode(path="Safety/Violence/Weapons").parent_path == "Safety/Violence"

    def test_parent_path_root_level_is_none(self):
        assert TopicNode(path="Safety").parent_path is None

    def test_depth_counts_separators(self):
        assert TopicNode(path="Safety").depth == 0
        assert TopicNode(path="Safety/Violence").depth == 1
        assert TopicNode(path="Safety/Violence/Weapons").depth == 2

    def test_depth_empty_path_is_root(self):
        assert TopicNode(path="").depth == -1

    def test_is_hashable(self):
        """Frozen model, so it can be used in sets and dict keys."""
        assert len({TopicNode(path="Safety"), TopicNode(path="Safety")}) == 1

    def test_get_all_parents(self):
        """Should return parents from immediate parent up to the root."""
        parents = TopicNode(path="A/B/C").get_all_parents()
        assert [p.path for p in parents] == ["A/B", "A"]

    def test_get_all_parents_root_level(self):
        assert TopicNode(path="A").get_all_parents() == []

    def test_serialized_fields(self):
        """The computed fields are part of the API response shape."""
        assert TopicNode(path="Safety/Violence").model_dump() == {
            "path": "Safety/Violence",
            "name": "Violence",
            "parent_path": "Safety",
            "depth": 1,
        }
