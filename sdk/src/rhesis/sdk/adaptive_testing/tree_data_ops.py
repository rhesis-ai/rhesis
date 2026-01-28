from rhesis.sdk.adaptive_testing.schemas import TestTreeData

nan = float("nan")


def remove_scores(test_tree_data: TestTreeData) -> TestTreeData:
    """Remove all scores from the test tree data."""
    for node in test_tree_data:
        node.model_score = nan
    return test_tree_data
