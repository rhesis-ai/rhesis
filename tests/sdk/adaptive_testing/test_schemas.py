"""Unit tests for adaptive testing schemas."""

import pytest

from rhesis.sdk.adaptive_testing.schemas import (
    TestTreeData,
    TestTreeNode,
    TopicNode,
    TopicTree,
)


class TestTestTreeNode:
    """Tests for TestTreeNode model."""

    def test_create_with_required_input(self):
        """Should create node with only required input field."""
        node = TestTreeNode(input="test prompt")
        assert node.input == "test prompt"

    def test_default_values(self):
        """Should have correct default values."""
        node = TestTreeNode(input="test")
        assert node.topic == ""
        assert node.output == ""
        assert node.label == ""
        assert node.labeler == ""
        assert node.to_eval is True
        assert node.model_score == 0.0

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
            topic="/Safety",
            input="Is this safe?",
            output="Yes",
            label="pass",
            labeler="user",
            to_eval=False,
            model_score=0.95,
        )
        assert node.id == "custom-id"
        assert node.topic == "/Safety"
        assert node.input == "Is this safe?"
        assert node.output == "Yes"
        assert node.label == "pass"
        assert node.labeler == "user"
        assert node.to_eval is False
        assert node.model_score == 0.95

    def test_missing_input_uses_default(self):
        """Should use empty string as default for input."""
        node = TestTreeNode()
        assert node.input == ""

    def test_topic_spaces_preserved(self):
        """Topic field preserves spaces (no URL encoding)."""
        node = TestTreeNode(input="test", topic="/Safety Topic/Sub Topic")
        assert node.topic == "/Safety Topic/Sub Topic"

    def test_topic_preserved_as_given(self):
        """Topic is stored exactly as provided."""
        node = TestTreeNode(input="test", topic="/Safety%20Topic")
        assert node.topic == "/Safety%20Topic"


class TestTestTreeData:
    """Tests for TestTreeData collection."""

    @pytest.fixture
    def sample_nodes(self):
        """Create sample nodes for testing."""
        return [
            TestTreeNode(id="node1", input="input1"),
            TestTreeNode(id="node2", input="input2"),
            TestTreeNode(id="node3", input="input3"),
        ]

    def test_init_empty(self):
        """Should initialize with no nodes."""
        data = TestTreeData()
        assert len(data) == 0

    def test_init_with_nodes(self, sample_nodes):
        """Should initialize with provided nodes."""
        data = TestTreeData(sample_nodes)
        assert len(data) == 3

    def test_len(self, sample_nodes):
        """Should return correct length."""
        data = TestTreeData(sample_nodes)
        assert len(data) == 3

    def test_iter_returns_nodes(self, sample_nodes):
        """Should iterate over the same node objects in insertion order."""
        data = TestTreeData(sample_nodes)
        nodes = list(data)
        assert len(nodes) == len(sample_nodes)
        for iterated, original in zip(nodes, sample_nodes):
            assert iterated is original

    def test_index_property(self, sample_nodes):
        """Should return list of node IDs."""
        data = TestTreeData(sample_nodes)
        assert set(data.index) == {"node1", "node2", "node3"}

    def test_shape_property(self, sample_nodes):
        """Should return (num_nodes, 5) tuple."""
        data = TestTreeData(sample_nodes)
        assert data.shape == (3, 5)

    def test_shape_empty(self):
        """Should return (0, 5) for empty data."""
        data = TestTreeData()
        assert data.shape == (0, 5)

    def test_getitem_by_int(self, sample_nodes):
        """Should get node by integer index."""
        data = TestTreeData(sample_nodes)
        assert data[0] == sample_nodes[0]
        assert data[1] == sample_nodes[1]
        assert data[2] == sample_nodes[2]

    def test_getitem_by_str(self, sample_nodes):
        """Should get node by string ID."""
        data = TestTreeData(sample_nodes)
        assert data["node1"] == sample_nodes[0]

    def test_setitem_by_int(self, sample_nodes):
        """Should set node by integer index."""
        data = TestTreeData(sample_nodes)
        data[0] = TestTreeNode(id="node1", input="input1")
        assert data[0] == TestTreeNode(id="node1", input="input1")

    def test_setitem_by_str(self, sample_nodes):
        """Should set node by string ID."""
        data = TestTreeData(sample_nodes)
        data["node1"] = TestTreeNode(id="node1", input="input1")

    def test_getitem_invalid_key_type(self, sample_nodes):
        """Should raise ValueError for invalid key type."""
        data = TestTreeData(sample_nodes)
        with pytest.raises(ValueError, match="Invalid key type"):
            data[3.14]  # type: ignore

    def test_setitem_invalid_key_type(self, sample_nodes):
        """Should raise ValueError for invalid key type."""
        data = TestTreeData(sample_nodes)
        with pytest.raises(ValueError, match="Invalid key type"):
            data[3.14] = TestTreeNode(id="x", input="x")  # type: ignore

    def test_topics_property_returns_topic_tree(self):
        """Should return a TopicTree instance."""
        data = TestTreeData()
        assert isinstance(data.topics, TopicTree)

    def test_topics_property_cached(self):
        """Should return the same TopicTree instance on multiple accesses."""
        data = TestTreeData()
        tree1 = data.topics
        tree2 = data.topics
        assert tree1 is tree2

    def test_get_topics_returns_topic_markers(self):
        """Should return only topic_marker nodes."""
        nodes = [
            TestTreeNode(id="marker1", topic="Safety", label="topic_marker"),
            TestTreeNode(id="marker2", topic="Safety/Violence", label="topic_marker"),
            TestTreeNode(id="test1", topic="Safety", input="test", label="pass"),
        ]
        data = TestTreeData(nodes)
        topics = data.get_topics()
        assert len(topics) == 2
        assert all(t.label == "topic_marker" for t in topics)

    def test_get_tests_returns_non_markers(self):
        """Should return only non-topic_marker nodes."""
        nodes = [
            TestTreeNode(id="marker1", topic="Safety", label="topic_marker"),
            TestTreeNode(id="test1", topic="Safety", input="test1", label="pass"),
            TestTreeNode(id="test2", topic="Safety", input="test2", label="fail"),
        ]
        data = TestTreeData(nodes)
        tests = data.get_tests()
        assert len(tests) == 2
        assert all(t.label != "topic_marker" for t in tests)

    def test_topic_has_direct_tests_true(self):
        """Should return True when topic has direct tests."""
        nodes = [
            TestTreeNode(id="marker1", topic="Safety", label="topic_marker"),
            TestTreeNode(id="test1", topic="Safety", input="test", label="pass"),
        ]
        data = TestTreeData(nodes)
        assert data.topic_has_direct_tests("Safety") is True

    def test_topic_has_direct_tests_false(self):
        """Should return False when topic has no direct tests."""
        nodes = [
            TestTreeNode(id="marker1", topic="Safety", label="topic_marker"),
            TestTreeNode(id="test1", topic="Safety/Violence", input="test", label="pass"),
        ]
        data = TestTreeData(nodes)
        assert data.topic_has_direct_tests("Safety") is False

    def test_topic_has_subtopics_true(self):
        """Should return True when topic has subtopics."""
        nodes = [
            TestTreeNode(id="marker1", topic="Safety", label="topic_marker"),
            TestTreeNode(id="marker2", topic="Safety/Violence", label="topic_marker"),
        ]
        data = TestTreeData(nodes)
        assert data.topic_has_subtopics("Safety") is True

    def test_topic_has_subtopics_false(self):
        """Should return False when topic has no subtopics."""
        nodes = [
            TestTreeNode(id="marker1", topic="Safety", label="topic_marker"),
        ]
        data = TestTreeData(nodes)
        assert data.topic_has_subtopics("Safety") is False


class TestTestTreeDataAddTest:
    """Tests for TestTreeData.add_test() method."""

    def test_add_test_basic(self):
        """Should add a test to the collection."""
        data = TestTreeData()
        test = TestTreeNode(id="test1", topic="Safety", input="test", label="pass")
        result = data.add_test(test)
        assert result is test
        assert len(data) == 2  # test + auto-created topic marker
        assert data["test1"] == test

    def test_add_test_creates_topic_marker(self):
        """Should create topic marker for the test's topic."""
        data = TestTreeData()
        test = TestTreeNode(id="test1", topic="Safety", input="test", label="pass")
        data.add_test(test)
        markers = data.get_topics()
        assert len(markers) == 1
        assert markers[0].topic == "Safety"

    def test_add_test_creates_ancestor_markers(self):
        """Should create topic markers for all ancestor topics."""
        data = TestTreeData()
        test = TestTreeNode(id="test1", topic="Safety/Violence/Weapons", input="test", label="pass")
        data.add_test(test)
        markers = data.get_topics()
        marker_topics = {m.topic for m in markers}
        assert "Safety" in marker_topics
        assert "Safety/Violence" in marker_topics
        assert "Safety/Violence/Weapons" in marker_topics

    def test_add_test_rejects_topic_marker(self):
        """Should raise ValueError when adding a topic_marker."""
        data = TestTreeData()
        marker = TestTreeNode(id="marker", topic="Safety", label="topic_marker")
        with pytest.raises(ValueError, match="Use topics.create"):
            data.add_test(marker)

    def test_add_test_no_duplicate_markers(self):
        """Should not create duplicate topic markers."""
        data = TestTreeData()
        test1 = TestTreeNode(id="test1", topic="Safety", input="test1", label="pass")
        test2 = TestTreeNode(id="test2", topic="Safety", input="test2", label="fail")
        data.add_test(test1)
        data.add_test(test2)
        markers = data.get_topics()
        assert len(markers) == 1

    def test_add_test_empty_topic(self):
        """Should handle test with empty topic."""
        data = TestTreeData()
        test = TestTreeNode(id="test1", topic="", input="test", label="pass")
        data.add_test(test)
        assert len(data) == 1  # No marker created for empty topic
        assert data["test1"] == test


class TestTestTreeDataUpdateTest:
    """Tests for TestTreeData.update_test() method."""

    @pytest.fixture
    def data_with_test(self):
        """Create TestTreeData with a test."""
        nodes = [
            TestTreeNode(id="marker1", topic="Safety", label="topic_marker"),
            TestTreeNode(
                id="test1",
                topic="Safety",
                input="original input",
                output="original output",
                label="pass",
                to_eval=True,
                model_score=0.5,
            ),
        ]
        return TestTreeData(nodes)

    def test_update_test_input(self, data_with_test):
        """Should update input field."""
        result = data_with_test.update_test("test1", input="new input")
        assert result.input == "new input"

    def test_update_test_output(self, data_with_test):
        """Should update output field."""
        result = data_with_test.update_test("test1", output="new output")
        assert result.output == "new output"

    def test_update_test_label(self, data_with_test):
        """Should update label field."""
        result = data_with_test.update_test("test1", label="fail")
        assert result.label == "fail"

    def test_update_test_to_eval(self, data_with_test):
        """Should update to_eval field."""
        result = data_with_test.update_test("test1", to_eval=False)
        assert result.to_eval is False

    def test_update_test_model_score(self, data_with_test):
        """Should update model_score field."""
        result = data_with_test.update_test("test1", model_score=0.9)
        assert result.model_score == 0.9

    def test_update_test_topic_creates_markers(self, data_with_test):
        """Should create topic markers when changing topic."""
        data_with_test.update_test("test1", topic="NewTopic/SubTopic")
        markers = data_with_test.get_topics()
        marker_topics = {m.topic for m in markers}
        assert "NewTopic" in marker_topics
        assert "NewTopic/SubTopic" in marker_topics

    def test_update_test_not_found(self, data_with_test):
        """Should raise KeyError for non-existent test."""
        with pytest.raises(KeyError, match="not found"):
            data_with_test.update_test("nonexistent", input="test")

    def test_update_test_rejects_topic_marker(self, data_with_test):
        """Should raise ValueError when updating a topic_marker."""
        with pytest.raises(ValueError, match="Cannot update topic_marker"):
            data_with_test.update_test("marker1", input="test")

    def test_update_test_multiple_fields(self, data_with_test):
        """Should update multiple fields at once."""
        result = data_with_test.update_test(
            "test1", input="new input", output="new output", label="fail"
        )
        assert result.input == "new input"
        assert result.output == "new output"
        assert result.label == "fail"


class TestTestTreeDataDeleteTest:
    """Tests for TestTreeData.delete_test() method."""

    def test_delete_test_success(self):
        """Should delete a test and return True."""
        nodes = [
            TestTreeNode(id="test1", topic="Safety", input="test", label="pass"),
        ]
        data = TestTreeData(nodes)
        result = data.delete_test("test1")
        assert result is True
        assert len(data) == 0

    def test_delete_test_not_found(self):
        """Should return False for non-existent test."""
        data = TestTreeData()
        result = data.delete_test("nonexistent")
        assert result is False

    def test_delete_test_rejects_topic_marker(self):
        """Should raise ValueError when deleting a topic_marker."""
        nodes = [
            TestTreeNode(id="marker1", topic="Safety", label="topic_marker"),
        ]
        data = TestTreeData(nodes)
        with pytest.raises(ValueError, match="Use topics.delete"):
            data.delete_test("marker1")


class TestTopicNode:
    """Tests for TopicNode model."""

    def test_create_topic(self):
        """Should create a topic with a path."""
        topic = TopicNode(path="Safety/Violence")
        assert topic.path == "Safety/Violence"

    def test_name_property(self):
        """Should return the leaf name."""
        topic = TopicNode(path="Safety/Violence/Weapons")
        assert topic.name == "Weapons"

    def test_name_property_root_level(self):
        """Should return full path for root-level topics."""
        topic = TopicNode(path="Safety")
        assert topic.name == "Safety"

    def test_name_property_empty(self):
        """Should return empty string for empty path."""
        topic = TopicNode(path="")
        assert topic.name == ""

    def test_parent_path_property(self):
        """Should return parent path."""
        topic = TopicNode(path="Safety/Violence/Weapons")
        assert topic.parent_path == "Safety/Violence"

    def test_parent_path_root_level(self):
        """Should return None for root-level topics."""
        topic = TopicNode(path="Safety")
        assert topic.parent_path is None

    def test_depth_property(self):
        """Should return correct depth."""
        assert TopicNode(path="Safety").depth == 0
        assert TopicNode(path="Safety/Violence").depth == 1
        assert TopicNode(path="Safety/Violence/Weapons").depth == 2

    def test_depth_property_empty(self):
        """Should return -1 for empty path (root)."""
        topic = TopicNode(path="")
        assert topic.depth == -1

    def test_display_name_returns_last_segment(self):
        """display_name is the last segment of the path."""
        topic = TopicNode(path="Safety Topic/Sub Topic")
        assert topic.display_name == "Sub Topic"

    def test_display_path_returns_path(self):
        """display_path returns the full path as stored."""
        topic = TopicNode(path="Safety Topic/Sub Topic")
        assert topic.display_path == "Safety Topic/Sub Topic"

    def test_is_ancestor_of_true(self):
        """Should return True when topic is ancestor of other."""
        parent = TopicNode(path="Safety")
        child = TopicNode(path="Safety/Violence")
        grandchild = TopicNode(path="Safety/Violence/Weapons")
        assert parent.is_ancestor_of(child) is True
        assert parent.is_ancestor_of(grandchild) is True
        assert child.is_ancestor_of(grandchild) is True

    def test_is_ancestor_of_false(self):
        """Should return False when topic is not ancestor of other."""
        topic1 = TopicNode(path="Safety")
        topic2 = TopicNode(path="Performance")
        assert topic1.is_ancestor_of(topic2) is False
        assert topic1.is_ancestor_of(topic1) is False  # Not ancestor of itself

    def test_is_ancestor_of_empty_path(self):
        """Empty path should be ancestor of everything."""
        root = TopicNode(path="")
        child = TopicNode(path="Safety")
        assert root.is_ancestor_of(child) is True
        assert root.is_ancestor_of(root) is False

    def test_is_descendant_of(self):
        """Should return True when topic is descendant of other."""
        parent = TopicNode(path="Safety")
        child = TopicNode(path="Safety/Violence")
        assert child.is_descendant_of(parent) is True
        assert parent.is_descendant_of(child) is False

    def test_is_direct_child_of_true(self):
        """Should return True for direct children."""
        parent = TopicNode(path="Safety")
        child = TopicNode(path="Safety/Violence")
        assert child.is_direct_child_of(parent) is True

    def test_is_direct_child_of_false_grandchild(self):
        """Should return False for grandchildren."""
        grandparent = TopicNode(path="Safety")
        grandchild = TopicNode(path="Safety/Violence/Weapons")
        assert grandchild.is_direct_child_of(grandparent) is False

    def test_is_direct_child_of_none_root_level(self):
        """Should return True for root-level topics with None parent."""
        topic = TopicNode(path="Safety")
        assert topic.is_direct_child_of(None) is True

    def test_is_direct_child_of_none_nested(self):
        """Should return False for nested topics with None parent."""
        topic = TopicNode(path="Safety/Violence")
        assert topic.is_direct_child_of(None) is False

    def test_child_path(self):
        """Should construct child path correctly."""
        parent = TopicNode(path="Safety")
        assert parent.child_path("Violence") == "Safety/Violence"

    def test_child_path_empty_parent(self):
        """Should handle empty parent path."""
        root = TopicNode(path="")
        assert root.child_path("Safety") == "Safety"

    def test_from_display_name(self):
        """Should create topic from display path as-is."""
        topic = TopicNode.from_display_name("Safety Topic/Sub Topic")
        assert topic.path == "Safety Topic/Sub Topic"

    def test_root_classmethod(self):
        """Should create root topic with empty path."""
        root = TopicNode.root()
        assert root.path == ""

    def test_str(self):
        """Should return path as string representation."""
        topic = TopicNode(path="Safety/Violence")
        assert str(topic) == "Safety/Violence"

    def test_repr(self):
        """Should return proper repr."""
        topic = TopicNode(path="Safety")
        assert repr(topic) == "TopicNode(path='Safety')"

    def test_topic_is_hashable(self):
        """TopicNode should be hashable (frozen model)."""
        topic = TopicNode(path="Safety")
        topic_set = {topic}
        assert topic in topic_set


class TestTopicTree:
    """Tests for TopicTree class."""

    @pytest.fixture
    def data_with_topics(self):
        """Create TestTreeData with topics and tests."""
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
        """Should return TopicNode for existing path."""
        tree = data_with_topics.topics
        topic = tree.get("Safety")
        assert topic is not None
        assert topic.path == "Safety"

    def test_get_nonexistent_topic(self, data_with_topics):
        """Should return None for non-existent path."""
        tree = data_with_topics.topics
        assert tree.get("NonExistent") is None

    def test_get_all_topics(self, data_with_topics):
        """Should return all topics."""
        tree = data_with_topics.topics
        topics = tree.get_all()
        paths = {t.path for t in topics}
        assert paths == {"Safety", "Safety/Violence", "Safety/Privacy", "Performance"}

    def test_get_all_excludes_suggestions(self):
        """Should exclude __suggestions__ pseudo-topics."""
        nodes = [
            TestTreeNode(id="m1", topic="Safety", label="topic_marker"),
            TestTreeNode(id="m2", topic="Safety/__suggestions__", label="topic_marker"),
        ]
        data = TestTreeData(nodes)
        topics = data.topics.get_all()
        paths = {t.path for t in topics}
        assert "Safety" in paths
        assert "Safety/__suggestions__" not in paths

    def test_get_children_root_level(self, data_with_topics):
        """Should return root-level topics when parent is None."""
        tree = data_with_topics.topics
        children = tree.get_children(None)
        paths = {c.path for c in children}
        assert paths == {"Safety", "Performance"}

    def test_get_children_of_topic(self, data_with_topics):
        """Should return direct children of a topic."""
        tree = data_with_topics.topics
        parent = tree.get("Safety")
        children = tree.get_children(parent)
        paths = {c.path for c in children}
        assert paths == {"Safety/Violence", "Safety/Privacy"}

    def test_get_children_no_children(self, data_with_topics):
        """Should return empty list when no children."""
        tree = data_with_topics.topics
        leaf = tree.get("Safety/Violence")
        children = tree.get_children(leaf)
        assert children == []

    def test_get_ancestors(self, data_with_topics):
        """Should return all ancestors from root to parent."""
        tree = data_with_topics.topics
        topic = tree.get("Safety/Violence")
        ancestors = tree.get_ancestors(topic)
        assert len(ancestors) == 1
        assert ancestors[0].path == "Safety"

    def test_get_ancestors_root_level(self, data_with_topics):
        """Should return empty list for root-level topics."""
        tree = data_with_topics.topics
        topic = tree.get("Safety")
        ancestors = tree.get_ancestors(topic)
        assert ancestors == []

    def test_get_tests_direct(self, data_with_topics):
        """Should return direct tests only (recursive=False)."""
        tree = data_with_topics.topics
        topic = tree.get("Safety")
        tests = tree.get_tests(topic, recursive=False)
        assert len(tests) == 1
        assert tests[0].id == "t1"

    def test_get_tests_recursive(self, data_with_topics):
        """Should return all tests including subtopics (recursive=True)."""
        tree = data_with_topics.topics
        topic = tree.get("Safety")
        tests = tree.get_tests(topic, recursive=True)
        assert len(tests) == 3
        ids = {t.id for t in tests}
        assert ids == {"t1", "t2", "t3"}

    def test_get_tests_all(self, data_with_topics):
        """Should return all tests when topic is None."""
        tree = data_with_topics.topics
        tests = tree.get_tests(None)
        assert len(tests) == 3

    def test_get_tests_excludes_suggestions(self):
        """Should exclude tests in __suggestions__ topics."""
        nodes = [
            TestTreeNode(id="m1", topic="Safety", label="topic_marker"),
            TestTreeNode(id="t1", topic="Safety", input="test1", label="pass"),
            TestTreeNode(id="t2", topic="Safety/__suggestions__", input="suggestion", label=""),
        ]
        data = TestTreeData(nodes)
        tests = data.topics.get_tests(None)
        assert len(tests) == 1
        assert tests[0].id == "t1"

    def test_has_direct_tests_true(self, data_with_topics):
        """Should return True when topic has direct tests."""
        tree = data_with_topics.topics
        topic = tree.get("Safety")
        assert tree.has_direct_tests(topic) is True

    def test_has_direct_tests_false(self, data_with_topics):
        """Should return False when topic has no direct tests."""
        tree = data_with_topics.topics
        topic = tree.get("Safety/Privacy")
        assert tree.has_direct_tests(topic) is False

    def test_has_subtopics_true(self, data_with_topics):
        """Should return True when topic has subtopics."""
        tree = data_with_topics.topics
        topic = tree.get("Safety")
        assert tree.has_subtopics(topic) is True

    def test_has_subtopics_false(self, data_with_topics):
        """Should return False when topic has no subtopics."""
        tree = data_with_topics.topics
        topic = tree.get("Safety/Violence")
        assert tree.has_subtopics(topic) is False

    def test_add_topic_new(self):
        """Should create a new topic."""
        data = TestTreeData()
        tree = data.topics
        topic = tree.add_topic("NewTopic")
        assert topic.path == "NewTopic"
        assert tree.get("NewTopic") is not None

    def test_add_topic_existing(self, data_with_topics):
        """Should return existing topic without creating duplicate."""
        tree = data_with_topics.topics
        original_count = len(data_with_topics)
        topic = tree.add_topic("Safety")
        assert topic.path == "Safety"
        assert len(data_with_topics) == original_count

    def test_delete_topic_with_move(self, data_with_topics):
        """Should delete topic and move tests to parent."""
        tree = data_with_topics.topics
        topic = tree.get("Safety/Violence")
        deleted_ids = tree.delete(topic, move_tests_to_parent=True)

        # Topic marker should be deleted
        assert tree.get("Safety/Violence") is None
        assert len(deleted_ids) == 1

        # Tests should be moved to parent
        parent = tree.get("Safety")
        tests = tree.get_tests(parent, recursive=False)
        assert len(tests) == 3  # Original 1 + 2 moved

    def test_delete_topic_without_move(self):
        """Should delete topic and all its contents."""
        nodes = [
            TestTreeNode(id="m1", topic="Safety", label="topic_marker"),
            TestTreeNode(id="m2", topic="Safety/Violence", label="topic_marker"),
            TestTreeNode(id="t1", topic="Safety/Violence", input="test", label="pass"),
        ]
        data = TestTreeData(nodes)
        tree = data.topics
        topic = tree.get("Safety/Violence")
        deleted_ids = tree.delete(topic, move_tests_to_parent=False)

        assert len(deleted_ids) == 2  # marker + test
        assert tree.get("Safety/Violence") is None
        assert len(data) == 1  # Only Safety marker remains

    def test_rename_topic(self, data_with_topics):
        """Should rename topic and update all nodes."""
        tree = data_with_topics.topics
        topic = tree.get("Safety/Violence")
        new_topic = tree.rename(topic, "Aggression")

        assert new_topic.path == "Safety/Aggression"
        assert tree.get("Safety/Violence") is None
        assert tree.get("Safety/Aggression") is not None

        # Tests should be moved
        tests = tree.get_tests(new_topic)
        assert len(tests) == 2

    def test_rename_root_level_topic(self):
        """Should rename root-level topic."""
        nodes = [
            TestTreeNode(id="m1", topic="Safety", label="topic_marker"),
            TestTreeNode(id="t1", topic="Safety", input="test", label="pass"),
        ]
        data = TestTreeData(nodes)
        tree = data.topics
        topic = tree.get("Safety")
        new_topic = tree.rename(topic, "Security")

        assert new_topic.path == "Security"
        assert tree.get("Safety") is None
        assert tree.get("Security") is not None

    def test_move_topic(self, data_with_topics):
        """Should move topic to new path."""
        tree = data_with_topics.topics
        topic = tree.get("Safety/Violence")
        new_topic = tree.move(topic, "Performance/Violence")

        assert new_topic.path == "Performance/Violence"
        assert tree.get("Safety/Violence") is None
        assert tree.get("Performance/Violence") is not None

    def test_move_topic_updates_children(self):
        """Should update all child topics and tests when moving."""
        nodes = [
            TestTreeNode(id="m1", topic="A", label="topic_marker"),
            TestTreeNode(id="m2", topic="A/B", label="topic_marker"),
            TestTreeNode(id="m3", topic="A/B/C", label="topic_marker"),
            TestTreeNode(id="m4", topic="X", label="topic_marker"),
            TestTreeNode(id="t1", topic="A/B/C", input="test", label="pass"),
        ]
        data = TestTreeData(nodes)
        tree = data.topics
        topic = tree.get("A/B")
        tree.move(topic, "X/B")

        assert tree.get("A/B") is None
        assert tree.get("A/B/C") is None
        assert tree.get("X/B") is not None
        assert tree.get("X/B/C") is not None

        # Test should be moved too
        tests = tree.get_tests(tree.get("X/B/C"))
        assert len(tests) == 1

    def test_get_topic_marker_id(self, data_with_topics):
        """Should return the node ID of the topic marker."""
        tree = data_with_topics.topics
        topic = tree.get("Safety")
        marker_id = tree.get_topic_marker_id(topic)
        assert marker_id == "m1"

    def test_get_topic_marker_id_not_found(self, data_with_topics):
        """Should return None for non-existent topic."""
        tree = data_with_topics.topics
        topic = TopicNode(path="NonExistent")
        marker_id = tree.get_topic_marker_id(topic)
        assert marker_id is None

    def test_invalidate_cache(self, data_with_topics):
        """Should clear the topic cache."""
        tree = data_with_topics.topics
        # Access to populate cache
        _ = tree.get("Safety")
        assert len(tree._topic_cache) > 0

        tree.invalidate_cache()
        assert len(tree._topic_cache) == 0
