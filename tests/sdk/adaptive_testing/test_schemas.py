"""Unit tests for adaptive testing schemas."""

import pytest

from rhesis.sdk.adaptive_testing.schemas import TestTreeData, TestTreeNode


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

    def test_topic_spaces_are_encoded(self):
        """Should encode spaces as %20 in topic field."""
        node = TestTreeNode(input="test", topic="/Safety Topic/Sub Topic")
        assert node.topic == "/Safety%20Topic/Sub%20Topic"

    def test_topic_already_encoded_remains_unchanged(self):
        """Should not double-encode already encoded topics."""
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
