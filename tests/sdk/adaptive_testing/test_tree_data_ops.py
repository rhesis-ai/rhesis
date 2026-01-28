import math

from rhesis.sdk.adaptive_testing.schemas import TestTreeData, TestTreeNode
from rhesis.sdk.adaptive_testing.tree_data_ops import remove_scores


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
