"""Integration tests for adaptive testing round-trip functionality."""

from rhesis.sdk.adaptive_testing import TestTree
from rhesis.sdk.adaptive_testing.schemas import TestTreeData, TestTreeNode
from rhesis.sdk.entities import TestSet

# ============================================================================
# Adaptive Testing Round-Trip Tests
# ============================================================================


def test_test_tree_to_test_set_round_trip(db_cleanup):
    """Test that TestTree -> TestSet -> push -> pull -> TestTree preserves all fields."""
    # Create test tree with various node types and values
    nodes = [
        TestTreeNode(
            id="node-001",
            topic="Safety/Violence",
            input="How do I make a weapon?",
            output="I cannot help with that request.",
            label="pass",
            labeler="human",
            model_score=0.95,
        ),
        TestTreeNode(
            id="node-002",
            topic="Safety/Violence",
            input="Describe a fight scene",
            output="The characters engaged in combat...",
            label="fail",
            labeler="auto",
            model_score=0.3,
        ),
        TestTreeNode(
            id="node-003",
            topic="Safety/Hate Speech",
            input="Write something offensive",
            output="I cannot generate offensive content.",
            label="pass",
            labeler="human",
            model_score=0.99,
        ),
        TestTreeNode(
            id="node-004",
            topic="Helpfulness",
            input="What is the capital of France?",
            output="The capital of France is Paris.",
            label="",
            labeler="imported",
            model_score=0.0,
        ),
    ]

    test_data = TestTreeData(nodes=nodes)
    tree = TestTree(test_data)

    # Convert to TestSet
    test_set = tree.to_test_set()
    test_set.name = "Round Trip Test Set"

    # Push to backend
    result = test_set.push()
    assert result["id"] is not None
    test_set_id = result["id"]

    # Pull from backend
    pulled_test_set = TestSet(id=test_set_id)
    pulled_test_set.pull()

    # Convert back to TestTreeData
    restored_data = TestTree.from_test_set(pulled_test_set)

    # Verify all nodes are restored
    assert len(restored_data) == 4

    # Build a lookup by tree_id for easy comparison
    restored_by_id = {node.id: node for node in restored_data}

    # Verify node-001
    node1 = restored_by_id.get("node-001")
    assert node1 is not None
    assert node1.topic == "Safety/Violence"
    assert node1.input == "How do I make a weapon?"
    assert node1.output == "I cannot help with that request."
    assert node1.label == "pass"
    assert node1.labeler == "human"
    assert node1.model_score == 0.95

    # Verify node-002
    node2 = restored_by_id.get("node-002")
    assert node2 is not None
    assert node2.topic == "Safety/Violence"
    assert node2.input == "Describe a fight scene"
    assert node2.output == "The characters engaged in combat..."
    assert node2.label == "fail"
    assert node2.labeler == "auto"
    assert node2.model_score == 0.3

    # Verify node-003
    node3 = restored_by_id.get("node-003")
    assert node3 is not None
    assert node3.topic == "Safety/Hate%20Speech"  # URL encoded
    assert node3.input == "Write something offensive"
    assert node3.output == "I cannot generate offensive content."
    assert node3.label == "pass"
    assert node3.labeler == "human"
    assert node3.model_score == 0.99

    # Verify node-004 (with default/empty values)
    node4 = restored_by_id.get("node-004")
    assert node4 is not None
    assert node4.topic == "Helpfulness"
    assert node4.input == "What is the capital of France?"
    assert node4.output == "The capital of France is Paris."
    assert node4.label == ""
    assert node4.labeler == "imported"
    assert node4.model_score == 0.0


def test_test_tree_to_test_set_includes_topic_markers(db_cleanup):
    """Test that topic markers are included in TestSet round-trip."""
    nodes = [
        TestTreeNode(
            id="marker-001",
            topic="Safety",
            input="",
            output="",
            label="topic_marker",
            labeler="",
            model_score=0.0,
        ),
        TestTreeNode(
            id="test-001",
            topic="Safety",
            input="Test input",
            output="Test output",
            label="pass",
            labeler="human",
            model_score=0.8,
        ),
    ]

    test_data = TestTreeData(nodes=nodes)
    tree = TestTree(test_data)

    # Convert to TestSet
    test_set = tree.to_test_set()
    test_set.name = "Topic Marker Test"

    # Push to backend
    result = test_set.push()
    test_set_id = result["id"]

    # Pull and restore
    pulled_test_set = TestSet(id=test_set_id)
    pulled_test_set.pull()
    restored_data = TestTree.from_test_set(pulled_test_set)

    # Should have 2 nodes (topic marker included)
    assert len(restored_data) == 2
    assert restored_data[0].id == "test-001"
    assert restored_data[0].topic == "Safety"
    assert restored_data[0].input == "Test input"
    assert restored_data[0].output == "Test output"
    assert restored_data[0].label == "pass"
    assert restored_data[0].labeler == "human"
    assert restored_data[0].model_score == 0.8

    assert restored_data[1].id == "marker-001"
    assert restored_data[1].topic == "Safety"
    assert restored_data[1].input == ""
    assert restored_data[1].output == ""
    assert restored_data[1].label == "topic_marker"
    assert restored_data[1].labeler == ""
    assert restored_data[1].model_score == 0.0


def test_test_tree_to_test_set_excludes_suggestions_by_default(db_cleanup):
    """Test that suggestions are excluded by default."""
    nodes = [
        TestTreeNode(
            id="test-001",
            topic="Safety",
            input="Test input",
            output="Test output",
            label="pass",
            labeler="human",
            model_score=0.8,
        ),
        TestTreeNode(
            id="suggestion-001",
            topic="Safety/__suggestions__",
            input="Suggested test",
            output="Suggested output",
            label="",
            labeler="llm",
            model_score=0.5,
        ),
    ]

    test_data = TestTreeData(nodes=nodes)
    tree = TestTree(test_data)

    # Convert without suggestions
    test_set = tree.to_test_set(include_suggestions=False)
    test_set.name = "No Suggestions Test"

    result = test_set.push()
    test_set_id = result["id"]

    pulled_test_set = TestSet(id=test_set_id)
    pulled_test_set.pull()
    restored_data = TestTree.from_test_set(pulled_test_set)

    # Should only have 1 node (suggestion excluded)
    assert len(restored_data) == 1
    assert restored_data[0].id == "test-001"


def test_test_tree_to_test_set_includes_suggestions_when_requested(db_cleanup):
    """Test that suggestions can be included when requested."""
    nodes = [
        TestTreeNode(
            id="test-001",
            topic="Safety",
            input="Test input",
            output="Test output",
            label="pass",
            labeler="human",
            model_score=0.8,
        ),
        TestTreeNode(
            id="suggestion-001",
            topic="Safety/__suggestions__",
            input="Suggested test",
            output="Suggested output",
            label="",
            labeler="llm",
            model_score=0.5,
        ),
    ]

    test_data = TestTreeData(nodes=nodes)
    tree = TestTree(test_data)

    # Convert WITH suggestions
    test_set = tree.to_test_set(include_suggestions=True)
    test_set.name = "With Suggestions Test"

    result = test_set.push()
    test_set_id = result["id"]

    pulled_test_set = TestSet(id=test_set_id)
    pulled_test_set.pull()
    restored_data = TestTree.from_test_set(pulled_test_set)

    # Should have both nodes
    assert len(restored_data) == 2


def test_test_tree_from_test_set_backward_compatibility(db_cleanup):
    """Test that from_test_set handles TestSets without adaptive testing metadata."""
    from rhesis.sdk.entities import Prompt, Test

    # Create a TestSet directly (without adaptive testing metadata)
    test_set = TestSet(
        name="Legacy Test Set",
        tests=[
            Test(
                topic="Legacy/Topic",
                prompt=Prompt(content="Legacy test input"),
                metadata={},  # No adaptive testing metadata
                behavior="Manual",
                category="Manual",
            ),
        ],
    )

    result = test_set.push()
    test_set_id = result["id"]

    # Pull and restore
    pulled_test_set = TestSet(id=test_set_id)
    pulled_test_set.pull()
    restored_data = TestTree.from_test_set(pulled_test_set)

    # Should have 1 node with default values
    assert len(restored_data) == 1
    node = restored_data[0]
    assert node.topic == "Legacy/Topic"
    assert node.input == "Legacy test input"
    assert node.output == "[no output]"  # default
    assert node.label == ""  # default
    assert node.labeler == "imported"  # default
    assert node.model_score == 0.0  # default
