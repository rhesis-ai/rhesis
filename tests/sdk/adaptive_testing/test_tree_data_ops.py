import math

from rhesis.sdk.adaptive_testing.schemas import TestTreeData, TestTreeNode
from rhesis.sdk.adaptive_testing.tree_data_ops import (
    remove_scores,
    return_eval_ids,
    set_evaluation_status,
)


def test_remove_scores():
    """Test that the remove_scores function removes all scores from the test tree data."""
    test_tree_data = TestTreeData(
        nodes=[
            TestTreeNode(id="node1", input="input1", output="output1", model_score=0.5),
            TestTreeNode(id="node2", input="input2", output="output2", model_score=0.6),
        ]
    )
    test_tree_data = remove_scores(test_tree_data)

    assert math.isnan(test_tree_data[0].model_score)
    assert math.isnan(test_tree_data[1].model_score)


def test_set_evaluation_status():
    """Test that the set_evaluation_status function sets the evaluation status for all nodes in the test tree data."""
    test_tree_data = TestTreeData(
        nodes=[
            TestTreeNode(id="node1", input="input1", output="output1", to_eval=True),
            TestTreeNode(id="node2", input="input2", output="output2", to_eval=False),
        ]
    )
    test_tree_data = set_evaluation_status(test_tree_data, False)
    assert test_tree_data[0].to_eval is False
    assert test_tree_data[1].to_eval is False
    test_tree_data = set_evaluation_status(test_tree_data, True)
    assert test_tree_data[0].to_eval is True
    assert test_tree_data[1].to_eval is True


def test_return_eval_ids():
    """Test that the return_eval_ids function returns the ids of the nodes that need to be evaluated."""
    test_tree_data = TestTreeData(
        nodes=[
            TestTreeNode(id="node1", input="input1", output="output1", to_eval=True),
            TestTreeNode(id="node2", input="input2", output="output2", to_eval=False),
            TestTreeNode(id="node3", input="input3", output="output3", to_eval=True),
            TestTreeNode(id="node4", input="input4", output="output4", to_eval=False),
        ]
    )
    assert return_eval_ids(test_tree_data) == ["node1", "node3"]


def test_get_topics():
    """Test that get_topics returns only topic marker nodes."""
    test_tree_data = TestTreeData(
        nodes=[
            TestTreeNode(id="topic1", topic="sentiment", label="topic_marker", input="", output=""),
            TestTreeNode(
                id="test1", topic="sentiment", label="", input="I love this!", output="positive"
            ),
            TestTreeNode(
                id="topic2", topic="sentiment/positive", label="topic_marker", input="", output=""
            ),
            TestTreeNode(
                id="test2",
                topic="sentiment/positive",
                label="",
                input="Great product!",
                output="positive",
            ),
        ]
    )

    topics = test_tree_data.get_topics()

    assert len(topics) == 2
    assert all(node.label == "topic_marker" for node in topics)
    assert {node.id for node in topics} == {"topic1", "topic2"}


def test_get_tests():
    """Test that get_tests returns only actual test nodes (non-topic markers)."""
    test_tree_data = TestTreeData(
        nodes=[
            TestTreeNode(id="topic1", topic="sentiment", label="topic_marker", input="", output=""),
            TestTreeNode(
                id="test1", topic="sentiment", label="", input="I love this!", output="positive"
            ),
            TestTreeNode(
                id="topic2", topic="sentiment/positive", label="topic_marker", input="", output=""
            ),
            TestTreeNode(
                id="test2",
                topic="sentiment/positive",
                label="",
                input="Great product!",
                output="positive",
            ),
        ]
    )

    tests = test_tree_data.get_tests()

    assert len(tests) == 2
    assert all(node.label != "topic_marker" for node in tests)
    assert {node.id for node in tests} == {"test1", "test2"}
